"""
Earnings Call & Transcript Analysis System

Implements comprehensive earnings call analysis to extract management sentiment,
guidance, and key insights from quarterly earnings calls.
"""
from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import yfinance as yf
from bs4 import BeautifulSoup

from app.cache.redis_cache import get_cache_manager
from app.config import get_settings
from app.tools.llm_orchestrator import get_llm_orchestrator, TaskType, TaskComplexity
from app.utils.session_manager import get_http_client_manager

try:
    import nltk
    from textblob import TextBlob
    NLP_PROCESSING_AVAILABLE = True
except ImportError:
    NLP_PROCESSING_AVAILABLE = False

logger = logging.getLogger(__name__)

if NLP_PROCESSING_AVAILABLE:
    for resource in [('tokenizers/punkt', 'punkt'), ('corpora/stopwords', 'stopwords')]:
        try:
            nltk.data.find(resource[0])
        except LookupError:
            nltk.download(resource[1])

# --- Sentiment word lists ---
_POSITIVE_WORDS = ['strong', 'growth', 'increase', 'improve', 'positive', 'excellent', 'outstanding',
                   'robust', 'solid', 'momentum', 'optimistic', 'confident', 'excited', 'pleased',
                   'successful', 'profitable', 'efficient', 'innovative', 'leading', 'competitive',
                   'record', 'best', 'exceed', 'beat', 'outperform', 'accelerate', 'expand']
_NEGATIVE_WORDS = ['challenge', 'difficult', 'concern', 'decline', 'decrease', 'negative', 'weak',
                   'struggle', 'pressure', 'uncertainty', 'volatile', 'risk', 'headwind', 'cautious',
                   'disappointed', 'challenging', 'uncertain', 'miss', 'below', 'disappointing',
                   'concerning', 'worrisome', 'troubling']
_DEFENSIVE_WORDS = ["however", "but", "although", "despite", "nevertheless", "on the other hand",
                    "it's important to note", "we should clarify", "to be clear", "let me emphasize",
                    "i want to be clear", "let me clarify", "to clarify", "just to be clear"]
_DEFENSIVE_PHRASES = ["i can't comment on that", "we don't provide guidance on",
                      "that's not something we discuss", "i'd rather not speculate",
                      "we're not prepared to discuss", "that's confidential",
                      "i can't go into details", "we'll have to see", "it's too early to tell",
                      "we're not ready to comment"]

# --- Guidance extraction patterns ---
_GUIDANCE_PATTERNS = {
    "revenue": [r'revenue.*guidance.*?(\$[\d,\.]+[BMK]?)', r'guidance.*revenue.*?(\$[\d,\.]+[BMK]?)',
                r'expect.*revenue.*?(\$[\d,\.]+[BMK]?)', r'forecast.*revenue.*?(\$[\d,\.]+[BMK]?)',
                r'revenue.*range.*?(\$[\d,\.]+[BMK]?.*?\$[\d,\.]+[BMK]?)'],
    "earnings": [r'eps.*guidance.*?(\$[\d,\.]+)', r'guidance.*eps.*?(\$[\d,\.]+)',
                 r'expect.*eps.*?(\$[\d,\.]+)', r'earnings.*guidance.*?(\$[\d,\.]+[BMK]?)'],
    "margins": [r'margin.*guidance.*?(\d+\.?\d*%)', r'guidance.*margin.*?(\d+\.?\d*%)',
                r'expect.*margin.*?(\d+\.?\d*%)', r'gross.*margin.*?(\d+\.?\d*%)',
                r'operating.*margin.*?(\d+\.?\d*%)'],
    "capex": [r'capex.*guidance.*?(\$[\d,\.]+[BMK]?)', r'capital.*expenditure.*?(\$[\d,\.]+[BMK]?)',
              r'investment.*guidance.*?(\$[\d,\.]+[BMK]?)'],
    "growth": [r'growth.*rate.*?(\d+\.?\d*%)', r'year.*over.*year.*?(\d+\.?\d*%)',
               r'yoy.*growth.*?(\d+\.?\d*%)', r'growth.*guidance.*?(\d+\.?\d*%)'],
}

_TOPIC_KEYWORDS = {
    'revenue': ['revenue', 'sales', 'top line', 'income'],
    'profitability': ['profit', 'margin', 'earnings', 'profitability', 'bottom line'],
    'growth': ['growth', 'expansion', 'scaling', 'increasing'],
    'market': ['market', 'market share', 'competitive', 'competition'],
    'innovation': ['innovation', 'technology', 'digital', 'transformation'],
    'operations': ['operations', 'efficiency', 'productivity', 'cost'],
    'strategy': ['strategy', 'strategic', 'initiative', 'plan'],
    'risk': ['risk', 'challenge', 'headwind', 'uncertainty'],
    'guidance': ['guidance', 'outlook', 'forecast', 'expectation'],
    'investment': ['investment', 'capex', 'capital', 'spending'],
}

_MONTH_MAP = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
              'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}
_QUARTER_MONTH = {'Q1': 1, 'Q2': 4, 'Q3': 7, 'Q4': 10}


class CallType(Enum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    CONFERENCE = "conference"
    INVESTOR_DAY = "investor_day"


@dataclass
class EarningsCall:
    ticker: str
    call_date: datetime
    call_type: CallType
    quarter: str
    fiscal_year: int
    transcript_url: str
    audio_url: Optional[str] = None
    transcript_text: Optional[str] = None
    participants: List[str] = field(default_factory=list)
    duration_minutes: Optional[int] = None
    call_id: Optional[str] = None


@dataclass
class CallAnalysis:
    ticker: str
    call_date: datetime
    quarter: str
    overall_sentiment: float
    management_tone: str
    confidence_score: float
    revenue_guidance: Optional[Dict[str, Any]] = None
    earnings_guidance: Optional[Dict[str, Any]] = None
    margin_guidance: Optional[Dict[str, Any]] = None
    capex_guidance: Optional[Dict[str, Any]] = None
    analyst_questions: List[str] = field(default_factory=list)
    management_responses: List[str] = field(default_factory=list)
    defensiveness_score: float = 0.0
    topics_avoided: List[str] = field(default_factory=list)
    key_topics: List[str] = field(default_factory=list)
    concerns_raised: List[str] = field(default_factory=list)
    new_initiatives: List[str] = field(default_factory=list)
    call_quality_score: float = 0.0
    information_density: float = 0.0
    transparency_score: float = 0.0
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    data_sources: List[str] = field(default_factory=list)


# --- Helper functions ---

def _date_from_title(title: str) -> Optional[datetime]:
    """Extract date from transcript title using common patterns."""
    try:
        for pattern in [r'(\w+)\s+(\d{4})', r'(\d{4})-(\d{2})-(\d{2})', r'(\w+)\s+(\d{1,2}),\s+(\d{4})']:
            m = re.search(pattern, title)
            if m:
                g = m.groups()
                if len(g) == 2:
                    qm = _QUARTER_MONTH.get(g[0].upper())
                    if qm:
                        return datetime(int(g[1]), qm, 15)
                elif len(g) == 3:
                    if '-' in title:
                        return datetime(int(g[0]), int(g[1]), int(g[2]))
                    month = _MONTH_MAP.get(g[0].lower(), 1)
                    return datetime(int(g[2]), month, int(g[1]))
    except Exception:
        pass
    return None


def _quarter_from_title(title: str) -> str:
    m = re.search(r'(Q[1-4])\s+(\d{4})', title, re.IGNORECASE)
    return f"{m.group(1).upper()} {m.group(2)}" if m else "Unknown"


def _quarter_from_month(month: int, year: int) -> str:
    q = 1 + (month - 1) // 3
    return f"Q{q} {year}"


def _parse_date(date_str: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return None


async def _get_or_init_cache(source: Any) -> Any:
    if source.cache is None:
        source.cache = await get_cache_manager()
    return source.cache


async def _cached_transcripts(cache: Any, cache_key: str) -> Optional[List[EarningsCall]]:
    result = await cache.get(cache_key)
    if result is not None:
        return [EarningsCall(**c) for c in result]
    return None


async def _cache_transcripts(cache: Any, cache_key: str, transcripts: List[EarningsCall],
                              ttl: int = 2592000) -> None:
    await cache.set(cache_key, [c.__dict__ for c in transcripts], ttl=ttl)


def _sentiment_score(text: str) -> float:
    text_lower = text.lower()
    total = len(text.split())
    if not total:
        return 0.0
    pos = sum(1 for w in _POSITIVE_WORDS if w in text_lower)
    neg = sum(1 for w in _NEGATIVE_WORDS if w in text_lower)
    def_count = sum(1 for w in _DEFENSIVE_WORDS if w in text_lower)
    score = (pos - neg) / max(total / 100, 1)
    score = max(-1.0, min(1.0, score))
    def_factor = min(def_count / max(total / 200, 1), 0.5)
    return score * (1 - def_factor)


def _extract_guidance(text: str) -> Dict[str, Any]:
    guidance: Dict[str, Any] = {}
    for key, patterns in _GUIDANCE_PATTERNS.items():
        matches = []
        for p in patterns:
            matches.extend(re.findall(p, text, re.IGNORECASE))
        if not matches:
            continue
        if key == "revenue":
            guidance["revenue"] = {"amount": matches[0], "confidence": min(len(matches) / 3.0, 1.0)}
        elif key == "earnings":
            eps = matches[0] if matches[0].startswith('$') else f"${matches[0]}"
            guidance["earnings"] = {"eps": eps, "confidence": min(len(matches) / 3.0, 1.0)}
        elif key == "margins":
            guidance["margins"] = {"gross_margin": matches[0], "confidence": min(len(matches) / 3.0, 1.0)}
        elif key == "capex":
            guidance["capex"] = {"amount": matches[0], "confidence": min(len(matches) / 3.0, 1.0)}
        elif key == "growth" and "revenue" in guidance:
            guidance["revenue"]["growth_rate"] = matches[0]
    return guidance


def _analyze_qa(text: str) -> Dict[str, Any]:
    text_lower = text.lower()
    def_count = sum(1 for p in _DEFENSIVE_PHRASES if p in text_lower)
    total = len(text.split())
    defensiveness = min(def_count / max(total / 1000, 1), 1.0)
    questions = []
    for p in [r'question.*?[:?]', r'analyst.*?[:?]', r'operator.*?[:?]']:
        questions.extend(re.findall(p, text, re.IGNORECASE)[:3])
    avoided = ["Future guidance", "Competitive positioning", "Market outlook"] if defensiveness > 0.3 else []
    return {"questions": questions[:5], "responses": [], "defensiveness": defensiveness, "topics_avoided": avoided}


def _extract_topics(text: str) -> Dict[str, Any]:
    text_lower = text.lower()
    scores = {t: sum(text_lower.count(k) for k in kws) for t, kws in _TOPIC_KEYWORDS.items()}
    top_topics = [t for t, s in sorted(scores.items(), key=lambda x: x[1], reverse=True) if s > 0][:7]

    concern_kws = ['challenge', 'concern', 'risk', 'headwind', 'pressure', 'uncertainty',
                   'volatile', 'difficult', 'struggle', 'decline', 'weak', 'miss',
                   'below', 'disappointing', 'concerning', 'worrisome', 'troubling']
    initiative_kws = ['new initiative', 'strategic initiative', 'launch', 'introduce', 'expand',
                      'acquisition', 'partnership', 'investment', 'development',
                      'innovation', 'transformation', 'digital', 'technology']

    concerns = [f"Management mentioned {k}" for k in concern_kws if k in text_lower][:5]
    initiatives = [f"New {k} mentioned" for k in initiative_kws if k in text_lower][:5]
    return {"topics": top_topics, "concerns": concerns, "initiatives": initiatives}


def _quality_metrics(text: str) -> Dict[str, float]:
    words = len(text.split())
    sentences = text.split('.')
    transparency = sum(1 for w in ["guidance", "outlook", "forecast", "expect", "plan"] if w in text.lower())
    return {
        "quality": min(1.0, words / 5000),
        "density": min(1.0, (words / max(len(sentences), 1)) / 20),
        "transparency": min(1.0, transparency / 10)
    }


def _sentiment_drivers(text: str) -> List[str]:
    drivers = []
    text_lower = text.lower()
    if any(w in text_lower for w in ['revenue', 'sales', 'top line']):
        if any(w in text_lower for w in ['strong', 'growth', 'increase', 'beat']):
            drivers.append("Strong revenue performance")
        elif any(w in text_lower for w in ['weak', 'decline', 'miss', 'below']):
            drivers.append("Revenue challenges")
    if any(w in text_lower for w in ['profit', 'margin', 'earnings']):
        if any(w in text_lower for w in ['strong', 'improve', 'expand', 'beat']):
            drivers.append("Improved profitability")
        elif any(w in text_lower for w in ['pressure', 'decline', 'compress']):
            drivers.append("Profitability pressure")
    if any(w in text_lower for w in ['growth', 'expansion']):
        drivers.append("Growth initiatives")
    if any(w in text_lower for w in ['innovation', 'technology', 'digital']):
        drivers.append("Innovation focus")
    return drivers[:3]


# --- Transcript Sources ---

class TranscriptSource(ABC):
    cache = None

    @abstractmethod
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        pass


class SeekingAlphaSource(TranscriptSource):
    base_url = "https://seekingalpha.com"
    session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
            )
        return self.session

    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        cache = await _get_or_init_cache(self)
        cache_key = f"seeking_alpha_transcripts:{ticker}:{days_back}"
        if cached := await _cached_transcripts(cache, cache_key):
            return cached
        try:
            session = await self._get_session()
            await asyncio.sleep(1.0)
            async with session.get(f"{self.base_url}/symbol/{ticker}/earnings/transcripts") as resp:
                if resp.status != 200:
                    return []
                soup = BeautifulSoup(await resp.text(), 'html.parser')
                transcripts = []
                for link in soup.find_all('a', href=re.compile(r'/article/\d+.*transcript'))[:10]:
                    title = link.get_text(strip=True)
                    call_date = _date_from_title(title)
                    if call_date and (datetime.now() - call_date).days <= days_back:
                        transcripts.append(EarningsCall(
                            ticker=ticker, call_date=call_date, call_type=CallType.EARNINGS,
                            quarter=_quarter_from_title(title), fiscal_year=call_date.year,
                            transcript_url=f"{self.base_url}{link['href']}",
                            call_id=link['href'].split('/')[-1]
                        ))
                await _cache_transcripts(cache, cache_key, transcripts)
                return transcripts
        except Exception as e:
            logger.error(f"SeekingAlpha fetch error for {ticker}: {e}")
            await cache.set(cache_key, [], ttl=604800)
            return []

    def get_source_name(self) -> str:
        return "Seeking Alpha"


class SECEdgarTranscriptSource(TranscriptSource):
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        logger.info(f"SEC EDGAR transcript source not yet implemented for {ticker}")
        return []

    def get_source_name(self) -> str:
        return "SEC EDGAR"


class APINinjaTranscriptSource(TranscriptSource):
    def __init__(self):
        settings = get_settings()
        self.base_url = "https://api.api-ninjas.com/v1"
        self.api_key = settings.api_ninja_key
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        return await get_http_client_manager().get_or_create_session(
            "api_ninja_earnings",
            headers={'X-Api-Key': self.api_key, 'User-Agent': 'EquiSense AI Research Tool'}
        )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        if not self.api_key:
            return []
        cache = await _get_or_init_cache(self)
        cache_key = f"api_ninja_transcripts:{ticker}:{days_back}"
        if (cached := await cache.get(cache_key)) is not None:
            return [EarningsCall(**c) for c in cached]

        try:
            session = await self._get_session()
            api_ticker = ticker.replace('.NS', '').replace('.BO', '')
            logger.warning(f"MAKING API CALL to API Ninja for {ticker}")
            await asyncio.sleep(1.0)
            async with session.get(f"{self.base_url}/earningstranscript",
                                   params={"ticker": api_ticker, "limit": 5}) as resp:
                if resp.status in (401, 403, 429) or resp.status != 200:
                    await cache.set(cache_key, [], ttl=604800)
                    return []
                data = await resp.json()
                if not data or not isinstance(data, dict):
                    await cache.set(cache_key, [], ttl=2592000)
                    return []

                call_date = _parse_date(data.get("date", ""))
                if not call_date:
                    return []
                content = data.get("transcript", "")
                if not content or len(content.strip()) < 100:
                    return []
                q, yr = data.get("quarter", ""), data.get("year", "")
                quarter = f"Q{q} {yr}" if q and yr else _quarter_from_month(call_date.month, call_date.year)
                transcripts = [EarningsCall(
                    ticker=ticker, call_date=call_date, call_type=CallType.EARNINGS,
                    quarter=quarter, fiscal_year=call_date.year, transcript_url="",
                    transcript_text=content, duration_minutes=60
                )]
                await _cache_transcripts(cache, cache_key, transcripts)
                return transcripts
        except asyncio.TimeoutError:
            await (await _get_or_init_cache(self)).set(cache_key, [], ttl=604800)
            return []
        except Exception as e:
            logger.error(f"API Ninja error for {ticker}: {e}")
            await (await _get_or_init_cache(self)).set(cache_key, [], ttl=604800)
            return []

    def get_source_name(self) -> str:
        return "API Ninja"


class MockTranscriptSource(TranscriptSource):
    _MAJOR_US = {'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA'}

    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        if ticker.upper() not in self._MAJOR_US:
            return []
        cache = await _get_or_init_cache(self)
        cache_key = f"mock_transcripts:{ticker}:{days_back}"
        if cached := await _cached_transcripts(cache, cache_key):
            return cached
        transcripts = []
        for i in range(3):
            call_date = datetime.now() - timedelta(days=90 * (i + 1))
            quarter = f"Q{(i % 4) + 1} {call_date.year}"
            company = ticker.replace('.NS', '')
            content = f"""
{company} Earnings Call Transcript - {quarter}
Operator: Good morning and welcome to {company}'s quarterly earnings call.
CEO: We're pleased to report strong results for {quarter}. Revenue grew by 15% year-over-year,
driven by strong demand across all segments. We remain optimistic about our growth prospects.
CFO: Operating margins improved to 25%, and we generated strong cash flow.
We're maintaining our guidance for the full year.
Q&A Session:
Analyst: Can you comment on the competitive landscape?
CEO: We see strong competitive positioning. Our focus on innovation differentiates us in the market.
Analyst: What about guidance for next quarter?
CFO: We expect continued growth in the mid-teens range, consistent with long-term targets.
""".strip()
            transcripts.append(EarningsCall(
                ticker=ticker, call_date=call_date, call_type=CallType.EARNINGS,
                quarter=quarter, fiscal_year=call_date.year,
                transcript_url=f"https://mock-transcripts.com/{ticker}/{quarter}",
                transcript_text=content, participants=["CEO", "CFO", "Analysts"], duration_minutes=60
            ))
        await _cache_transcripts(cache, cache_key, transcripts, ttl=3600)
        return transcripts

    def get_source_name(self) -> str:
        return "Mock Data"


class FMPTranscriptSource(TranscriptSource):
    def __init__(self):
        settings = get_settings()
        self.base_url = "https://financialmodelingprep.com/api/v3"
        self.api_key = settings.fmp_api_key
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self.session

    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        if not self.api_key:
            return []
        cache = await _get_or_init_cache(self)
        cache_key = f"fmp_transcripts:{ticker}:{days_back}"
        if cached := await _cached_transcripts(cache, cache_key):
            return cached
        try:
            now = datetime.now()
            session = await self._get_session()
            await asyncio.sleep(0.5)
            params = {"apikey": self.api_key,
                      "from": (now - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                      "to": now.strftime("%Y-%m-%d")}
            async with session.get(f"{self.base_url}/earning_call_transcript/{ticker}", params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                if not data or not isinstance(data, list):
                    return []
                transcripts = []
                for item in data:
                    call_date = _parse_date(item.get("date", ""))
                    if not call_date:
                        continue
                    content = item.get("content", "")
                    if not content or len(content.strip()) < 100:
                        continue
                    quarter = item.get("quarter") or _quarter_from_month(call_date.month, call_date.year)
                    transcripts.append(EarningsCall(
                        ticker=ticker, call_date=call_date, call_type=CallType.EARNINGS,
                        quarter=quarter, fiscal_year=call_date.year,
                        transcript_url=item.get("transcript_url", ""),
                        transcript_text=content, audio_url=item.get("audio_url", ""),
                        duration_minutes=item.get("duration_minutes", 60)
                    ))
                await _cache_transcripts(cache, cache_key, transcripts)
                return transcripts
        except Exception as e:
            logger.error(f"FMP error for {ticker}: {e}")
            await (await _get_or_init_cache(self)).set(cache_key, [], ttl=604800)
            return []

    def get_source_name(self) -> str:
        return "FMP"


class AlphaStreetSource(TranscriptSource):
    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.alpha_street_api_key
        self.base_url = "https://api.alphastreet.com/v1"
        self.session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {'User-Agent': 'EquiSense AI/1.0'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), headers=headers)
        return self.session

    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        if not self.api_key:
            return []
        cache = await _get_or_init_cache(self)
        cache_key = f"alpha_street_transcripts:{ticker}:{days_back}"
        if cached := await _cached_transcripts(cache, cache_key):
            return cached
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/earnings-calls",
                                   params={'symbol': ticker, 'limit': 10, 'days_back': days_back}) as resp:
                if resp.status != 200:
                    return []
                transcripts = []
                for d in (await resp.json()).get('calls', []):
                    try:
                        call_date = datetime.fromisoformat(d['date'].replace('Z', '+00:00'))
                        transcripts.append(EarningsCall(
                            ticker=ticker, call_date=call_date, call_type=CallType.EARNINGS,
                            quarter=d.get('quarter', 'Unknown'), fiscal_year=call_date.year,
                            transcript_url=d.get('transcript_url', ''), audio_url=d.get('audio_url'),
                            transcript_text=d.get('transcript'), participants=d.get('participants', []),
                            duration_minutes=d.get('duration_minutes'), call_id=d.get('id')
                        ))
                    except Exception:
                        continue
                await _cache_transcripts(cache, cache_key, transcripts)
                return transcripts
        except Exception as e:
            logger.error(f"AlphaStreet error for {ticker}: {e}")
            await (await _get_or_init_cache(self)).set(cache_key, [], ttl=604800)
            return []

    def get_source_name(self) -> str:
        return "Alpha Street"


# --- Main Analyzer ---

class EarningsCallAnalyzer:
    def __init__(self):
        self.cache = None
        self.sources: List[TranscriptSource] = []
        self.llm_orchestrator = get_llm_orchestrator()
        self._sessions_to_close: List[aiohttp.ClientSession] = []

    async def _initialize_sources(self):
        if self.cache is None:
            self.cache = await get_cache_manager()
        self.sources = [
            APINinjaTranscriptSource(),
            MockTranscriptSource(),
            FMPTranscriptSource(),
            SeekingAlphaSource(),
            AlphaStreetSource(),
        ]
        for s in self.sources:
            s.cache = self.cache

    async def cleanup_sessions(self):
        for s in self._sessions_to_close:
            if not s.closed:
                await s.close()
        self._sessions_to_close.clear()
        for source in self.sources:
            if hasattr(source, 'close'):
                await source.close()

    def _is_cache_fresh(self, cached: Dict[str, Any], ticker: str) -> bool:
        try:
            date_str = cached.get("analysis_date")
            if not date_str:
                return False
            age = (datetime.now() - datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)).days
            if age < 7:
                return True
            if age <= 30 and datetime.now().month not in [1, 4, 7, 10]:
                return True
            return False
        except Exception:
            return False

    async def analyze_earnings_calls(self, ticker: str, days_back: int = 90, max_calls: int = 5) -> Dict[str, Any]:
        if self.cache is None:
            self.cache = await get_cache_manager()
        if not self.sources:
            await self._initialize_sources()

        cache_key = f"earnings_call_analysis:{ticker}:{days_back}:{max_calls}"
        if cached := await self.cache.get(cache_key):
            if self._is_cache_fresh(cached, ticker):
                return cached
            await self.cache.delete(cache_key)

        try:
            all_transcripts, sources_used = [], []
            for source in self.sources:
                try:
                    transcripts = await source.get_transcripts(ticker, days_back)
                    if transcripts:
                        all_transcripts.extend(transcripts)
                        sources_used.append(source.get_source_name())
                        if len(all_transcripts) >= max_calls and source.get_source_name() == "FMP":
                            break
                except Exception as e:
                    logger.warning(f"Error from {source.get_source_name()}: {e}")

            unique = list({(t.call_date.date(), t.quarter): t
                           for t in sorted(all_transcripts, key=lambda x: x.call_date)}.values())
            unique.sort(key=lambda x: x.call_date, reverse=True)
            recent = unique[:max_calls]

            if not recent:
                return {"ticker": ticker, "total_calls": 0, "analysis_period": f"{days_back} days",
                        "sources_used": sources_used, "message": "No earnings call transcripts found",
                        "analysis_date": datetime.now().isoformat()}

            analyses = []
            for t in recent:
                try:
                    analyses.append(await self._analyze_single_call(t))
                except Exception as e:
                    logger.warning(f"Error analyzing call {t.call_id}: {e}")

            result = self._aggregate_analyses(analyses)
            result.update({"ticker": ticker, "total_calls": len(recent),
                           "analysis_period": f"{days_back} days",
                           "sources_used": sources_used, "analysis_date": datetime.now().isoformat()})
            await self.cache.set(cache_key, result, ttl=2592000)
            return result
        except Exception as e:
            logger.error(f"Error analyzing earnings calls for {ticker}: {e}")
            return {"ticker": ticker, "error": str(e), "analysis_date": datetime.now().isoformat()}
        finally:
            await self.cleanup_sessions()

    async def _analyze_single_call(self, transcript: EarningsCall) -> CallAnalysis:
        if not transcript.transcript_text:
            transcript.transcript_text = await self._fetch_transcript_text(transcript)
        if not transcript.transcript_text:
            return CallAnalysis(ticker=transcript.ticker, call_date=transcript.call_date,
                                quarter=transcript.quarter, overall_sentiment=0.0,
                                management_tone="unknown", confidence_score=0.0)
        text = transcript.transcript_text
        score = _sentiment_score(text)
        tone = ("optimistic" if score > 0.2 else "bullish" if score > 0.1
                else "cautious" if score < -0.2 else "defensive" if score < -0.1 else "neutral")
        guidance = _extract_guidance(text)
        qa = _analyze_qa(text)
        topics = _extract_topics(text)
        quality = _quality_metrics(text)
        return CallAnalysis(
            ticker=transcript.ticker, call_date=transcript.call_date, quarter=transcript.quarter,
            overall_sentiment=score, management_tone=tone,
            confidence_score=min(len(text) / 10000.0, 1.0),
            revenue_guidance=guidance.get("revenue"), earnings_guidance=guidance.get("earnings"),
            margin_guidance=guidance.get("margins"), capex_guidance=guidance.get("capex"),
            analyst_questions=qa["questions"], management_responses=qa["responses"],
            defensiveness_score=qa["defensiveness"], topics_avoided=qa["topics_avoided"],
            key_topics=topics["topics"], concerns_raised=topics["concerns"],
            new_initiatives=topics["initiatives"], call_quality_score=quality["quality"],
            information_density=quality["density"], transparency_score=quality["transparency"],
            data_sources=[transcript.transcript_url]
        )

    async def _fetch_transcript_text(self, transcript: EarningsCall) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(transcript.transcript_url) as resp:
                    if resp.status != 200:
                        return None
                    soup = BeautifulSoup(await resp.text(), 'html.parser')
                    for sel in ['.transcript-content', '.article-content', '.transcript',
                                '[data-testid="transcript-content"]', '.content']:
                        if content := soup.select_one(sel):
                            return content.get_text(separator='\n', strip=True)
        except Exception as e:
            logger.warning(f"Error fetching transcript text: {e}")
        return None

    def _aggregate_analyses(self, analyses: List[CallAnalysis]) -> Dict[str, Any]:
        if not analyses:
            return {}
        avg = lambda attr: sum(getattr(a, attr) for a in analyses) / len(analyses)
        guidance_summary: Dict[str, List] = {"revenue": [], "earnings": [], "margins": [], "capex": []}
        all_topics, all_concerns, all_initiatives = [], [], []
        for a in analyses:
            if a.revenue_guidance: guidance_summary["revenue"].append(a.revenue_guidance)
            if a.earnings_guidance: guidance_summary["earnings"].append(a.earnings_guidance)
            if a.margin_guidance: guidance_summary["margins"].append(a.margin_guidance)
            if a.capex_guidance: guidance_summary["capex"].append(a.capex_guidance)
            all_topics.extend(a.key_topics)
            all_concerns.extend(a.concerns_raised)
            all_initiatives.extend(a.new_initiatives)
        return {
            "aggregated_sentiment": {
                "overall_sentiment": avg("overall_sentiment"),
                "confidence_score": avg("confidence_score"),
                "defensiveness_score": avg("defensiveness_score"),
                "call_quality": avg("call_quality_score"),
            },
            "guidance_summary": guidance_summary,
            "key_topics": [t for t, _ in Counter(all_topics).most_common(5)],
            "common_concerns": [t for t, _ in Counter(all_concerns).most_common(3)],
            "new_initiatives": [t for t, _ in Counter(all_initiatives).most_common(3)],
            "individual_analyses": [
                {"quarter": a.quarter, "call_date": a.call_date.isoformat(),
                 "sentiment": a.overall_sentiment, "tone": a.management_tone,
                 "defensiveness": a.defensiveness_score, "quality_score": a.call_quality_score}
                for a in analyses
            ]
        }


# --- Global instance and public API ---

_global_analyzer: Optional[EarningsCallAnalyzer] = None


async def get_global_analyzer() -> EarningsCallAnalyzer:
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = EarningsCallAnalyzer()
        await _global_analyzer._initialize_sources()
    return _global_analyzer


async def analyze_earnings_calls(ticker: str, days_back: int = 90, max_calls: int = 5) -> Dict[str, Any]:
    """Main function to analyze earnings calls for a ticker."""
    analyzer = await get_global_analyzer()
    try:
        return await analyzer.analyze_earnings_calls(ticker, days_back, max_calls)
    except Exception as e:
        logger.error(f"Error in analyze_earnings_calls for {ticker}: {e}")
        return {
            "status": "error", "transcripts": [],
            "analysis": {
                "management_sentiment": {"overall_sentiment": 0.0, "confidence_score": 0.0},
                "guidance_analysis": {},
                "key_insights": {"topics_discussed": [], "concerns_raised": [], "new_initiatives": []},
                "summary_insights": f"Error analyzing earnings calls for {ticker}: {e}",
                "confidence_score": 0.0
            }
        }
