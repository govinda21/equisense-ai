"""
Earnings Call & Transcript Analysis System

Implements comprehensive earnings call analysis to extract management sentiment,
guidance, and key insights from quarterly earnings calls.

Features:
- Multi-source transcript integration
- Sentiment analysis and tone detection
- Guidance extraction and tracking
- Q&A session analysis
- Management defensiveness scoring
- Key topic extraction and visualization
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import os
from abc import ABC, abstractmethod
import json

import aiohttp
from bs4 import BeautifulSoup
from app.utils.session_manager import get_http_client_manager, create_managed_session
# Optional imports for NLP processing
try:
    import nltk
    from textblob import TextBlob
    NLP_PROCESSING_AVAILABLE = True
except ImportError:
    NLP_PROCESSING_AVAILABLE = False
    logger.warning("NLP processing libraries not available. Advanced sentiment analysis will be disabled.")

import yfinance as yf

from app.cache.redis_cache import get_cache_manager
from app.tools.llm_orchestrator import get_llm_orchestrator, TaskType, TaskComplexity

logger = logging.getLogger(__name__)

# Download required NLTK data (only if available)
if NLP_PROCESSING_AVAILABLE:
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords')


class CallType(Enum):
    """Types of earnings calls"""
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    CONFERENCE = "conference"
    INVESTOR_DAY = "investor_day"


@dataclass
class EarningsCall:
    """Earnings call data structure"""
    ticker: str
    call_date: datetime
    call_type: CallType
    quarter: str  # e.g., "Q1 2024"
    fiscal_year: int
    transcript_url: str
    audio_url: Optional[str] = None
    transcript_text: Optional[str] = None
    participants: List[str] = field(default_factory=list)
    duration_minutes: Optional[int] = None
    call_id: Optional[str] = None


@dataclass
class CallAnalysis:
    """Earnings call analysis results"""
    ticker: str
    call_date: datetime
    quarter: str
    
    # Sentiment Analysis
    overall_sentiment: float  # -1 to 1
    management_tone: str  # "bullish", "cautious", "defensive", "optimistic"
    confidence_score: float  # 0 to 1
    
    # Guidance Analysis
    revenue_guidance: Optional[Dict[str, Any]] = None
    earnings_guidance: Optional[Dict[str, Any]] = None
    margin_guidance: Optional[Dict[str, Any]] = None
    capex_guidance: Optional[Dict[str, Any]] = None
    
    # Q&A Analysis
    analyst_questions: List[str] = field(default_factory=list)
    management_responses: List[str] = field(default_factory=list)
    defensiveness_score: float = 0.0  # 0 to 1
    topics_avoided: List[str] = field(default_factory=list)
    
    # Key Topics
    key_topics: List[str] = field(default_factory=list)
    concerns_raised: List[str] = field(default_factory=list)
    new_initiatives: List[str] = field(default_factory=list)
    
    # Performance Metrics
    call_quality_score: float = 0.0  # 0 to 1
    information_density: float = 0.0  # 0 to 1
    transparency_score: float = 0.0  # 0 to 1
    
    # Metadata
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    data_sources: List[str] = field(default_factory=list)


class TranscriptSource(ABC):
    """Abstract base class for transcript sources"""
    
    @abstractmethod
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get earnings call transcripts for a ticker"""
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Get source name"""
        pass


class SeekingAlphaSource(TranscriptSource):
    """Seeking Alpha transcript source"""
    
    def __init__(self):
        self.base_url = "https://seekingalpha.com"
        self.cache = None  # Will be initialized in get_transcripts
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
            )
        return self.session
    
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get Seeking Alpha transcripts"""
        cache_key = f"seeking_alpha_transcripts:{ticker}:{days_back}"
        
        # Initialize cache if needed
        if self.cache is None:
            self.cache = await get_cache_manager()
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved Seeking Alpha transcripts from cache for {ticker}")
            return [EarningsCall(**call) for call in cached_result]
        
        try:
            session = await self._get_session()
            
            # Search for earnings calls
            search_url = f"{self.base_url}/symbol/{ticker}/earnings/transcripts"
            
            # Rate limiting
            await asyncio.sleep(1.0)
            
            async with session.get(search_url) as response:
                if response.status != 200:
                    logger.warning(f"Seeking Alpha returned {response.status} for {ticker}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract transcript links
                transcripts = []
                transcript_links = soup.find_all('a', href=re.compile(r'/article/\d+.*transcript'))
                
                for link in transcript_links[:10]:  # Limit to recent 10
                    try:
                        transcript_url = f"{self.base_url}{link['href']}"
                        title = link.get_text(strip=True)
                        
                        # Extract date from title or URL
                        call_date = self._extract_date_from_title(title)
                        
                        if call_date and (datetime.now() - call_date).days <= days_back:
                            earnings_call = EarningsCall(
                                ticker=ticker,
                                call_date=call_date,
                                call_type=CallType.EARNINGS,
                                quarter=self._extract_quarter_from_title(title),
                                fiscal_year=call_date.year,
                                transcript_url=transcript_url,
                                participants=[],
                                call_id=link['href'].split('/')[-1]
                            )
                            transcripts.append(earnings_call)
                    
                    except Exception as e:
                        logger.warning(f"Error parsing Seeking Alpha transcript link: {e}")
                        continue
                
                # Cache results for 4 hours
                await self.cache.set(cache_key, [call.__dict__ for call in transcripts], ttl=2592000)  # 30 days
                
                logger.info(f"Retrieved {len(transcripts)} Seeking Alpha transcripts for {ticker}")
                return transcripts
        
        except Exception as e:
            logger.error(f"Error fetching Seeking Alpha transcripts for {ticker}: {e}")
            # Cache empty result to prevent repeated failed calls
            await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
            return []
    
    def _extract_date_from_title(self, title: str) -> Optional[datetime]:
        """Extract date from transcript title"""
        try:
            # Common patterns: "Q1 2024 Earnings Call Transcript", "2024-01-15 Earnings Call"
            patterns = [
                r'(\w+)\s+(\d{4})',  # Q1 2024
                r'(\d{4})-(\d{2})-(\d{2})',  # 2024-01-15
                r'(\w+)\s+(\d{1,2}),\s+(\d{4})',  # January 15, 2024
            ]
            
            for pattern in patterns:
                match = re.search(pattern, title)
                if match:
                    if len(match.groups()) == 2:  # Q1 2024
                        quarter, year = match.groups()
                        # Convert quarter to approximate date
                        quarter_num = {'Q1': 1, 'Q2': 4, 'Q3': 7, 'Q4': 10}.get(quarter.upper(), 1)
                        return datetime(int(year), quarter_num, 15)
                    elif len(match.groups()) == 3:
                        if '-' in title:  # 2024-01-15
                            year, month, day = match.groups()
                            return datetime(int(year), int(month), int(day))
                        else:  # January 15, 2024
                            month_name, day, year = match.groups()
                            month = {
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }.get(month_name.lower(), 1)
                            return datetime(int(year), month, int(day))
            
            return None
            
        except Exception:
            return None
    
    def _extract_quarter_from_title(self, title: str) -> str:
        """Extract quarter from title"""
        match = re.search(r'(Q[1-4])\s+(\d{4})', title, re.IGNORECASE)
        if match:
            return f"{match.group(1).upper()} {match.group(2)}"
        return "Unknown"
    
    def get_source_name(self) -> str:
        return "Seeking Alpha"


class SECEdgarTranscriptSource(TranscriptSource):
    """SEC EDGAR API transcript source for earnings calls"""
    
    def __init__(self):
        self.base_url = "https://data.sec.gov/api/xbrl/companyfacts"
        self.cache = None  # Will be initialized in get_transcripts
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'EquiSense AI Research Tool (contact@equisense.ai)',
                    'Accept': 'application/json'
                }
            )
        return self.session
    
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get SEC EDGAR transcripts (placeholder implementation)"""
        # SEC EDGAR doesn't directly provide earnings call transcripts
        # This would require parsing 8-K filings for earnings call transcripts
        # For now, return empty list
        logger.info(f"SEC EDGAR transcript source not yet implemented for {ticker}")
        return []
    
    def get_source_name(self) -> str:
        return "SEC EDGAR"


class APINinjaTranscriptSource(TranscriptSource):
    """API Ninja earnings call transcript source"""
    
    def __init__(self):
        from app.config import get_settings
        settings = get_settings()
        self.base_url = "https://api.api-ninjas.com/v1"
        self.api_key = settings.api_ninja_key
        self.cache = None  # Will be initialized in get_transcripts
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create managed aiohttp session"""
        http_manager = get_http_client_manager()
        return await http_manager.get_or_create_session(
            "api_ninja_earnings",
            headers={
                'X-Api-Key': self.api_key,
                'User-Agent': 'EquiSense AI Research Tool (contact@equisense.ai)'
            }
        )
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get API Ninja earnings call transcripts"""
        print(f"🔍 DEBUG: get_transcripts called for {ticker}")
        
        if not self.api_key:
            logger.warning("API Ninja API key not provided")
            return []
            
        cache_key = f"api_ninja_transcripts:{ticker}:{days_back}"
        
        # Initialize cache if needed - use shared cache from main analyzer
        if self.cache is None:
            print(f"🔍 DEBUG: Initializing cache for {ticker}")
            self.cache = await get_cache_manager()
            print(f"🔍 DEBUG: Cache initialized: {self.cache}")
        
        # Check cache first with longer TTL for earnings calls
        print(f"🔍 DEBUG: Getting cache for key: {cache_key}")
        cached_result = await self.cache.get(cache_key)
        print(f"🔍 DEBUG: Cache result: {cached_result}, Type: {type(cached_result)}")
        logger.info(f"🔍 DEBUG: Cache key: {cache_key}, Cached result: {cached_result}, Type: {type(cached_result)}")
        if cached_result is not None:
            logger.info(f"✅ CACHE HIT: Retrieved API Ninja transcripts from cache for {ticker}")
            return [EarningsCall(**call) for call in cached_result]
        
        logger.info(f"❌ CACHE MISS: No cached API Ninja transcripts for {ticker}, making API call")
        
        try:
            session = await self._get_session()
            
            # API Ninja earnings call transcript endpoint
            url = f"{self.base_url}/earningstranscript"
            
            # Convert ticker format for API Ninja (remove .NS/.BO suffixes)
            api_ticker = ticker.replace('.NS', '').replace('.BO', '')
            
            params = {
                "ticker": api_ticker,
                "limit": 5  # Get last 5 transcripts
            }
            
            # Rate limiting - API Ninja allows 50 requests per day on free tier
            logger.warning(f"🚨 MAKING API CALL to API Ninja for {ticker} - this counts against your daily limit!")
            await asyncio.sleep(1.0)
            
            async with session.get(url, params=params) as response:
                if response.status == 401:
                    logger.warning(f"API Ninja authentication failed for {ticker}")
                    # Cache empty result to prevent repeated failed calls
                    await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
                    return []
                elif response.status == 403:
                    logger.warning(f"API Ninja access forbidden for {ticker}")
                    # Cache empty result to prevent repeated failed calls
                    await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
                    return []
                elif response.status == 429:
                    logger.warning(f"API Ninja rate limit exceeded for {ticker}")
                    # Cache empty result to prevent repeated failed calls
                    await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
                    return []
                elif response.status != 200:
                    logger.warning(f"API Ninja returned {response.status} for {ticker}")
                    # Cache empty result to prevent repeated failed calls
                    await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
                    return []
                
                data = await response.json()
                
                # API Ninja returns a single dict, not a list
                if not data or not isinstance(data, dict):
                    logger.info(f"No transcripts found for {ticker} on API Ninja")
                    # Cache empty result to prevent repeated calls
                    await self.cache.set(cache_key, [], ttl=2592000)  # Cache empty result for 30 days
                    return []
                
                transcripts = []
                # Handle single transcript response
                item = data
                try:
                    # Parse API Ninja response format
                    call_date_str = item.get("date", "")
                    if not call_date_str:
                        logger.info(f"No date found in API Ninja response for {ticker}")
                        return []
                        
                    # Parse date - API Ninja format varies
                    try:
                        call_date = datetime.strptime(call_date_str, "%Y-%m-%d")
                    except ValueError:
                        try:
                            call_date = datetime.strptime(call_date_str, "%Y-%m-%dT%H:%M:%S")
                        except ValueError:
                            logger.warning(f"Could not parse date {call_date_str} for {ticker}")
                            return []
                    
                    # Extract transcript content
                    transcript_content = item.get("transcript", "")
                    if not transcript_content or len(transcript_content.strip()) < 100:
                        logger.info(f"No transcript content found for {ticker}")
                        return []
                    
                    # Extract quarter information
                    quarter = item.get("quarter", "")
                    year = item.get("year", "")
                    if quarter and year:
                        quarter = f"Q{quarter} {year}"
                    else:
                        # Try to extract quarter from date
                        month = call_date.month
                        if month <= 3:
                            quarter = f"Q1 {call_date.year}"
                        elif month <= 6:
                            quarter = f"Q2 {call_date.year}"
                        elif month <= 9:
                            quarter = f"Q3 {call_date.year}"
                        else:
                            quarter = f"Q4 {call_date.year}"
                    
                    earnings_call = EarningsCall(
                        ticker=ticker,
                        call_date=call_date,
                        call_type=CallType.EARNINGS,
                        quarter=quarter,
                        fiscal_year=call_date.year,
                        transcript_url="",  # API Ninja doesn't provide URL
                        transcript_text=transcript_content,
                        participants=[],  # API Ninja doesn't provide participant details
                        audio_url="",  # API Ninja doesn't provide audio URL
                        duration_minutes=60  # Default duration
                    )
                    transcripts.append(earnings_call)
                    
                except Exception as e:
                    logger.warning(f"Error parsing API Ninja transcript for {ticker}: {e}")
                    return []
                
                logger.info(f"Retrieved {len(transcripts)} transcripts from API Ninja for {ticker}")
                
                # Cache the results (8 hours - longer cache for API limit preservation)
                await self.cache.set(cache_key, [call.__dict__ for call in transcripts], ttl=2592000)  # 30 days
                
                return transcripts
                
        except asyncio.TimeoutError:
            logger.warning(f"API Ninja timeout for {ticker}")
            # Cache empty result to prevent repeated failed calls
            await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
            return []
        except Exception as e:
            logger.error(f"Error fetching API Ninja transcripts for {ticker}: {e}")
            # Cache empty result to prevent repeated failed calls
            await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
            return []
    
    def get_source_name(self) -> str:
        return "API Ninja"


class MockTranscriptSource(TranscriptSource):
    """Mock transcript source for testing purposes"""
    
    def __init__(self):
        self.cache = None
    
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Generate mock transcripts for testing"""
        # Initialize cache if needed
        if self.cache is None:
            self.cache = await get_cache_manager()
        
        cache_key = f"mock_transcripts:{ticker}:{days_back}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved mock transcripts from cache for {ticker}")
            return [EarningsCall(**call) for call in cached_result]
        
        # Mock data is only for testing purposes - not for real investment decisions
        # Only provide mock data for US stocks that have real API data available
        major_us_stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA']
        if ticker.upper() not in major_us_stocks:
            logger.info(f"Mock data not available for {ticker} - real data sources required for investment decisions")
            return []
        
        mock_transcripts = []
        base_date = datetime.now()
        
        for i in range(3):  # Generate 3 mock transcripts
            call_date = base_date - timedelta(days=90 * (i + 1))
            quarter = f"Q{(i % 4) + 1} {call_date.year}"
            
            # Generate realistic mock transcript content
            is_indian_stock = '.NS' in ticker.upper()
            company_name = ticker.replace('.NS', '') if is_indian_stock else ticker
            
            if is_indian_stock:
                transcript_content = f"""
                {company_name} Earnings Call Transcript - {quarter}
                
                Operator: Good morning and welcome to {company_name}'s quarterly earnings call.
                
                CEO: Thank you for joining us today. We're pleased to report strong results for {quarter}.
                Revenue grew by 12% year-over-year, driven by strong domestic demand and export growth.
                We remain optimistic about India's economic growth and our positioning in key sectors.
                
                CFO: Our financial performance was solid this quarter. Operating margins improved to 18%,
                and we generated strong cash flow. We're maintaining our guidance for the full year.
                Our debt levels remain manageable and we continue to invest in capacity expansion.
                
                Q&A Session:
                Analyst: Can you comment on the competitive landscape in India?
                CEO: We continue to see strong competitive positioning. Our focus on operational excellence
                and customer service differentiates us in the Indian market.
                
                Analyst: What about guidance for next quarter?
                CFO: We expect continued growth in the low-teens range, consistent with our long-term targets.
                We're monitoring commodity price fluctuations and their impact on margins.
                """
            else:
                transcript_content = f"""
                {ticker} Earnings Call Transcript - {quarter}
                
                Operator: Good morning and welcome to {ticker}'s quarterly earnings call.
                
                CEO: Thank you for joining us today. We're pleased to report strong results for {quarter}.
                Revenue grew by 15% year-over-year, driven by strong demand across all segments.
                We remain optimistic about our growth prospects and are investing heavily in innovation.
                
                CFO: Our financial performance was solid this quarter. Operating margins improved to 25%,
                and we generated strong cash flow. We're maintaining our guidance for the full year.
                
                Q&A Session:
                Analyst: Can you comment on the competitive landscape?
                CEO: We continue to see strong competitive positioning. Our focus on innovation
                and customer experience differentiates us in the market.
                
                Analyst: What about guidance for next quarter?
                CFO: We expect continued growth in the mid-teens range, consistent with our long-term targets.
                """
            
            earnings_call = EarningsCall(
                ticker=ticker,
                call_date=call_date,
                call_type=CallType.EARNINGS,
                quarter=quarter,
                fiscal_year=call_date.year,
                transcript_url=f"https://mock-transcripts.com/{ticker}/{quarter}",
                transcript_text=transcript_content.strip(),
                participants=["CEO", "CFO", "Analysts"],
                audio_url="",
                duration_minutes=60
            )
            mock_transcripts.append(earnings_call)
        
        # Cache the results (1 hour for mock data)
        await self.cache.set(cache_key, [call.__dict__ for call in mock_transcripts], ttl=3600)
        
        logger.info(f"Generated {len(mock_transcripts)} mock transcripts for {ticker}")
        return mock_transcripts
    
    def get_source_name(self) -> str:
        return "Mock Data"


class FMPTranscriptSource(TranscriptSource):
    """Financial Modeling Prep (FMP) API transcript source"""
    
    def __init__(self):
        from app.config import get_settings
        settings = get_settings()
        self.base_url = "https://financialmodelingprep.com/api/v3"
        self.api_key = settings.fmp_api_key
        self.cache = None  # Will be initialized in get_transcripts
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
            )
        return self.session
    
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get FMP API transcripts"""
        if not self.api_key:
            logger.warning("FMP API key not provided")
            return []
            
        cache_key = f"fmp_transcripts:{ticker}:{days_back}"
        
        # Initialize cache if needed
        if self.cache is None:
            self.cache = await get_cache_manager()
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved FMP transcripts from cache for {ticker}")
            return [EarningsCall(**call) for call in cached_result]
        
        try:
            session = await self._get_session()
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # FMP API endpoint for earnings call transcripts
            url = f"{self.base_url}/earning_call_transcript/{ticker}"
            params = {
                "apikey": self.api_key,
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d")
            }
            
            # Rate limiting - FMP allows 250 requests per day
            await asyncio.sleep(0.5)
            
            async with session.get(url, params=params) as response:
                if response.status == 401:
                    logger.warning(f"FMP API authentication failed for {ticker}")
                    return []
                elif response.status == 403:
                    logger.warning(f"FMP API access forbidden for {ticker}")
                    return []
                elif response.status == 429:
                    logger.warning(f"FMP API rate limit exceeded for {ticker}")
                    return []
                elif response.status != 200:
                    logger.warning(f"FMP API returned {response.status} for {ticker}")
                    return []
                
                data = await response.json()
                
                if not data or not isinstance(data, list):
                    logger.info(f"No transcripts found for {ticker} on FMP")
                    return []
                
                transcripts = []
                for item in data:
                    try:
                        # Parse FMP API response format
                        call_date_str = item.get("date", "")
                        if not call_date_str:
                            continue
                            
                        # Parse date - FMP format is usually YYYY-MM-DD
                        call_date = datetime.strptime(call_date_str, "%Y-%m-%d")
                        
                        # Extract transcript content
                        transcript_content = item.get("content", "")
                        if not transcript_content or len(transcript_content.strip()) < 100:
                            continue
                        
                        # Extract quarter information
                        quarter = item.get("quarter", "")
                        if not quarter:
                            # Try to extract quarter from date
                            month = call_date.month
                            if month <= 3:
                                quarter = f"Q1 {call_date.year}"
                            elif month <= 6:
                                quarter = f"Q2 {call_date.year}"
                            elif month <= 9:
                                quarter = f"Q3 {call_date.year}"
                            else:
                                quarter = f"Q4 {call_date.year}"
                        
                        earnings_call = EarningsCall(
                            ticker=ticker,
                            call_date=call_date,
                            call_type=CallType.EARNINGS,
                            quarter=quarter,
                            fiscal_year=call_date.year,
                            transcript_url=item.get("transcript_url", ""),
                            transcript_text=transcript_content,
                            participants=[],  # FMP doesn't provide participant details
                            audio_url=item.get("audio_url", ""),
                            duration_minutes=item.get("duration_minutes", 60)
                        )
                        transcripts.append(earnings_call)
                        
                    except Exception as e:
                        logger.warning(f"Error parsing FMP transcript for {ticker}: {e}")
                        continue
                
                logger.info(f"Retrieved {len(transcripts)} transcripts from FMP for {ticker}")
                
                # Cache the results (6 hours - longer cache for API limit preservation)
                await self.cache.set(cache_key, [call.__dict__ for call in transcripts], ttl=2592000)  # 30 days
                
                return transcripts
                
        except asyncio.TimeoutError:
            logger.warning(f"FMP API timeout for {ticker}")
            # Cache empty result to prevent repeated failed calls
            await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
            return []
        except Exception as e:
            logger.error(f"Error fetching FMP transcripts for {ticker}: {e}")
            # Cache empty result to prevent repeated failed calls
            await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
            return []
    
    def get_source_name(self) -> str:
        return "FMP"


class AlphaStreetSource(TranscriptSource):
    """Alpha Street transcript source (premium)"""
    
    def __init__(self, api_key: Optional[str] = None):
        from app.config import get_settings
        settings = get_settings()
        self.api_key = api_key or settings.alpha_street_api_key
        self.base_url = "https://api.alphastreet.com/v1"
        self.cache = None  # Will be initialized in get_transcripts
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            headers = {'User-Agent': 'EquiSense AI/1.0'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers=headers
            )
        return self.session
    
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get Alpha Street transcripts"""
        if not self.api_key:
            logger.warning("Alpha Street API key not provided")
            return []
        
        # Initialize cache if not already done
        if self.cache is None:
            self.cache = await get_cache_manager()
        
        cache_key = f"alpha_street_transcripts:{ticker}:{days_back}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved Alpha Street transcripts from cache for {ticker}")
            return [EarningsCall(**call) for call in cached_result]
        
        try:
            session = await self._get_session()
            
            # Get earnings calls
            url = f"{self.base_url}/earnings-calls"
            params = {
                'symbol': ticker,
                'limit': 10,
                'days_back': days_back
            }
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Alpha Street returned {response.status} for {ticker}")
                    return []
                
                data = await response.json()
                transcripts = []
                
                for call_data in data.get('calls', []):
                    try:
                        call_date = datetime.fromisoformat(call_data['date'].replace('Z', '+00:00'))
                        
                        earnings_call = EarningsCall(
                            ticker=ticker,
                            call_date=call_date,
                            call_type=CallType.EARNINGS,
                            quarter=call_data.get('quarter', 'Unknown'),
                            fiscal_year=call_date.year,
                            transcript_url=call_data.get('transcript_url', ''),
                            audio_url=call_data.get('audio_url'),
                            transcript_text=call_data.get('transcript'),
                            participants=call_data.get('participants', []),
                            duration_minutes=call_data.get('duration_minutes'),
                            call_id=call_data.get('id')
                        )
                        transcripts.append(earnings_call)
                    
                    except Exception as e:
                        logger.warning(f"Error parsing Alpha Street call data: {e}")
                        continue
                
                # Cache results for 4 hours
                await self.cache.set(cache_key, [call.__dict__ for call in transcripts], ttl=2592000)  # 30 days
                
                logger.info(f"Retrieved {len(transcripts)} Alpha Street transcripts for {ticker}")
                return transcripts
        
        except Exception as e:
            logger.error(f"Error fetching Alpha Street transcripts for {ticker}: {e}")
            # Cache empty result to prevent repeated failed calls
            await self.cache.set(cache_key, [], ttl=604800)  # Cache empty result for 7 days
            return []
    
    def get_source_name(self) -> str:
        return "Alpha Street"


class EarningsCallAnalyzer:
    """Main earnings call analysis system"""
    
    def __init__(self):
        self.cache = None  # Will be initialized in analyze_earnings_calls
        self.sources = []  # Will be initialized after cache is set
        self.llm_orchestrator = get_llm_orchestrator()
        self._sessions_to_close = []  # Track sessions for cleanup
    
    async def _initialize_sources(self):
        """Initialize sources with shared cache"""
        if self.cache is None:
            self.cache = await get_cache_manager()
        
        # Initialize sources with shared cache
        self.sources = [
            APINinjaTranscriptSource(),  # Primary source - API Ninja
            MockTranscriptSource(),      # Fallback for testing - generates realistic mock data
            FMPTranscriptSource(),       # FMP API (currently deprecated)
            SeekingAlphaSource(),        # Fallback source
            AlphaStreetSource()          # Premium fallback (if API key available)
        ]
        
        # Set shared cache for all sources
        for source in self.sources:
            source.cache = self.cache
    
    async def cleanup_sessions(self):
        """Clean up any open sessions"""
        for session in self._sessions_to_close:
            if not session.closed:
                await session.close()
        self._sessions_to_close.clear()
        
        # Also close sessions from all sources
        for source in self.sources:
            if hasattr(source, 'close'):
                await source.close()
    
    def _is_cache_fresh(self, cached_result: Dict[str, Any], ticker: str) -> bool:
        """
        Check if cached earnings call analysis is still fresh based on earnings release patterns
        
        Args:
            cached_result: Cached analysis result
            ticker: Stock ticker symbol
            
        Returns:
            True if cache is fresh, False if stale
        """
        try:
            # Get analysis date from cache
            analysis_date_str = cached_result.get("analysis_date")
            if not analysis_date_str:
                return False
            
            analysis_date = datetime.fromisoformat(analysis_date_str.replace('Z', '+00:00'))
            days_since_analysis = (datetime.now() - analysis_date.replace(tzinfo=None)).days
            
            # Smart cache invalidation rules:
            # 1. If analysis is less than 7 days old, always fresh
            if days_since_analysis < 7:
                return True
            
            # 2. If analysis is 7-30 days old, check if we're in earnings season
            if days_since_analysis <= 30:
                # Check if we're in a typical earnings release window (month 1, 4, 7, 10)
                current_month = datetime.now().month
                if current_month in [1, 4, 7, 10]:  # Earnings seasons
                    logger.info(f"🔄 Earnings season detected (month {current_month}), cache may be stale for {ticker}")
                    return False
                return True
            
            # 3. If analysis is older than 30 days, always stale
            return False
            
        except Exception as e:
            logger.warning(f"Error checking cache freshness for {ticker}: {e}")
            return False
    
    async def analyze_earnings_calls(
        self,
        ticker: str,
        days_back: int = 90,
        max_calls: int = 5
    ) -> Dict[str, Any]:
        """
        Analyze earnings calls for a ticker
        
        Args:
            ticker: Stock ticker symbol
            days_back: Number of days to look back
            max_calls: Maximum number of calls to analyze
            
        Returns:
            Comprehensive earnings call analysis
        """
        cache_key = f"earnings_call_analysis:{ticker}:{days_back}:{max_calls}"
        
        # Initialize cache and sources if needed
        if self.cache is None:
            self.cache = await get_cache_manager()
        
        # Initialize sources with shared cache
        if not self.sources:
            await self._initialize_sources()
        
        # Check cache first with smart invalidation for earnings calls
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            # Check if cache is still fresh based on earnings release patterns
            if self._is_cache_fresh(cached_result, ticker):
                logger.info(f"✅ CACHE HIT: Retrieved fresh earnings call analysis from cache for {ticker}")
                return cached_result
            else:
                logger.info(f"🔄 CACHE STALE: Earnings call analysis for {ticker} is outdated, refreshing...")
                # Delete stale cache entry
                await self.cache.delete(cache_key)
        
        logger.info(f"❌ CACHE MISS: No cached earnings call analysis for {ticker}, analyzing...")
        
        try:
            # Get transcripts from sources with intelligent fallback
            all_transcripts = []
            sources_used = []
            
            for source in self.sources:
                try:
                    logger.info(f"Trying {source.get_source_name()} for {ticker}")
                    transcripts = await source.get_transcripts(ticker, days_back)
                    
                    if transcripts:
                        all_transcripts.extend(transcripts)
                        sources_used.append(source.get_source_name())
                        logger.info(f"✓ Retrieved {len(transcripts)} transcripts from {source.get_source_name()}")
                        
                        # If we have enough transcripts from a good source, we can stop
                        if len(all_transcripts) >= max_calls and source.get_source_name() == "FMP":
                            logger.info(f"Sufficient transcripts found from FMP, stopping search")
                            break
                    else:
                        logger.info(f"✗ No transcripts found from {source.get_source_name()}")
                        
                except Exception as e:
                    logger.warning(f"Error getting transcripts from {source.get_source_name()}: {e}")
                    continue
            
            # Deduplicate and sort by date
            unique_transcripts = self._deduplicate_transcripts(all_transcripts)
            unique_transcripts.sort(key=lambda x: x.call_date, reverse=True)
            
            # Limit to most recent calls
            recent_transcripts = unique_transcripts[:max_calls]
            
            if not recent_transcripts:
                return {
                    "ticker": ticker,
                    "total_calls": 0,
                    "analysis_period": f"{days_back} days",
                    "sources_used": sources_used,
                    "message": "No earnings call transcripts found",
                    "analysis_date": datetime.now().isoformat()
                }
            
            # Analyze each call
            call_analyses = []
            for transcript in recent_transcripts:
                try:
                    analysis = await self._analyze_single_call(transcript)
                    call_analyses.append(analysis)
                except Exception as e:
                    logger.warning(f"Error analyzing call {transcript.call_id}: {e}")
                    continue
            
            # Aggregate analysis
            aggregated_analysis = self._aggregate_analyses(call_analyses)
            
            # Add metadata
            aggregated_analysis.update({
                "ticker": ticker,
                "total_calls": len(recent_transcripts),
                "analysis_period": f"{days_back} days",
                "sources_used": sources_used,
                "analysis_date": datetime.now().isoformat()
            })
            
            # Cache results for 6 hours
            await self.cache.set(cache_key, aggregated_analysis, ttl=2592000)  # 30 days
            
            # Log cache statistics
            cache_stats = self.cache.get_cache_stats()
            logger.info(f"📊 Cache Stats: {cache_stats['hit_rate']:.1f}% hit rate ({cache_stats['hits']} hits, {cache_stats['misses']} misses)")
            
            logger.info(f"Completed earnings call analysis for {ticker}: {len(call_analyses)} calls analyzed")
            return aggregated_analysis
        
        except Exception as e:
            logger.error(f"Error analyzing earnings calls for {ticker}: {e}")
            return {
                "ticker": ticker,
                "error": str(e),
                "analysis_date": datetime.now().isoformat()
            }
        finally:
            # Clean up any open sessions
            await self.cleanup_sessions()
    
    def _deduplicate_transcripts(self, transcripts: List[EarningsCall]) -> List[EarningsCall]:
        """Remove duplicate transcripts based on date and quarter"""
        seen = set()
        unique_transcripts = []
        
        for transcript in transcripts:
            # Create a key based on date and quarter
            key = (transcript.call_date.date(), transcript.quarter)
            
            if key not in seen:
                seen.add(key)
                unique_transcripts.append(transcript)
        
        return unique_transcripts
    
    async def _analyze_single_call(self, transcript: EarningsCall) -> CallAnalysis:
        """Analyze a single earnings call"""
        
        # Get transcript text if not already available
        if not transcript.transcript_text:
            transcript.transcript_text = await self._fetch_transcript_text(transcript)
        
        if not transcript.transcript_text:
            # Return empty analysis if no transcript text
            return CallAnalysis(
                ticker=transcript.ticker,
                call_date=transcript.call_date,
                quarter=transcript.quarter,
                overall_sentiment=0.0,
                management_tone="unknown",
                confidence_score=0.0
            )
        
        # Perform sentiment analysis
        sentiment_analysis = await self._analyze_sentiment(transcript.transcript_text)
        
        # Extract guidance
        guidance_analysis = await self._extract_guidance(transcript.transcript_text)
        
        # Analyze Q&A session
        qa_analysis = await self._analyze_qa_session(transcript.transcript_text)
        
        # Extract key topics
        topics_analysis = await self._extract_key_topics(transcript.transcript_text)
        
        # Calculate quality metrics
        quality_metrics = self._calculate_quality_metrics(transcript.transcript_text)
        
        return CallAnalysis(
            ticker=transcript.ticker,
            call_date=transcript.call_date,
            quarter=transcript.quarter,
            overall_sentiment=sentiment_analysis["sentiment"],
            management_tone=sentiment_analysis["tone"],
            confidence_score=sentiment_analysis["confidence"],
            revenue_guidance=guidance_analysis.get("revenue"),
            earnings_guidance=guidance_analysis.get("earnings"),
            margin_guidance=guidance_analysis.get("margins"),
            capex_guidance=guidance_analysis.get("capex"),
            analyst_questions=qa_analysis.get("questions", []),
            management_responses=qa_analysis.get("responses", []),
            defensiveness_score=qa_analysis.get("defensiveness", 0.0),
            topics_avoided=qa_analysis.get("topics_avoided", []),
            key_topics=topics_analysis.get("topics", []),
            concerns_raised=topics_analysis.get("concerns", []),
            new_initiatives=topics_analysis.get("initiatives", []),
            call_quality_score=quality_metrics["quality"],
            information_density=quality_metrics["density"],
            transparency_score=quality_metrics["transparency"],
            data_sources=[transcript.transcript_url]
        )
    
    async def _fetch_transcript_text(self, transcript: EarningsCall) -> Optional[str]:
        """Fetch transcript text from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(transcript.transcript_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract transcript text (varies by source)
                        transcript_text = ""
                        
                        # Common selectors for transcript content
                        selectors = [
                            '.transcript-content',
                            '.article-content',
                            '.transcript',
                            '[data-testid="transcript-content"]',
                            '.content'
                        ]
                        
                        for selector in selectors:
                            content = soup.select_one(selector)
                            if content:
                                transcript_text = content.get_text(separator='\n', strip=True)
                                break
                        
                        return transcript_text if transcript_text else None
        
        except Exception as e:
            logger.warning(f"Error fetching transcript text: {e}")
            return None
    
    async def _analyze_sentiment(self, transcript_text: str) -> Dict[str, Any]:
        """Analyze sentiment and tone of the transcript using local analysis"""
        try:
            # Use local sentiment analysis instead of external LLM
            sentiment_score = self._analyze_sentiment_local(transcript_text)
            
            # Determine management tone based on sentiment score
            if sentiment_score > 0.2:
                tone = "optimistic"
            elif sentiment_score > 0.1:
                tone = "bullish"
            elif sentiment_score < -0.2:
                tone = "cautious"
            elif sentiment_score < -0.1:
                tone = "defensive"
            else:
                tone = "neutral"
            
            # Calculate confidence based on transcript length and content quality
            confidence = min(len(transcript_text) / 10000.0, 1.0)  # Longer transcripts = higher confidence
            
            # Extract key sentiment drivers using local analysis
            drivers = self._extract_sentiment_drivers_local(transcript_text)
            
            return {
                "sentiment": sentiment_score,
                "tone": tone,
                "confidence": confidence,
                "drivers": drivers
            }
            
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {
                "sentiment": 0.0,
                "tone": "neutral",
                "confidence": 0.3,
                "drivers": ["Analysis unavailable"]
            }
    
    def _analyze_sentiment_local(self, text: str) -> float:
        """Analyze sentiment using local text analysis"""
        try:
            # Positive sentiment indicators
            positive_words = [
                'strong', 'growth', 'increase', 'improve', 'positive', 'excellent', 'outstanding',
                'robust', 'solid', 'momentum', 'optimistic', 'confident', 'excited', 'pleased',
                'successful', 'profitable', 'efficient', 'innovative', 'leading', 'competitive',
                'record', 'best', 'exceed', 'beat', 'outperform', 'accelerate', 'expand'
            ]
            
            # Negative sentiment indicators
            negative_words = [
                'challenge', 'difficult', 'concern', 'decline', 'decrease', 'negative', 'weak',
                'struggle', 'pressure', 'uncertainty', 'volatile', 'risk', 'headwind', 'cautious',
                'disappointed', 'concerned', 'challenging', 'pressure', 'uncertain', 'volatile',
                'miss', 'below', 'disappointing', 'concerning', 'worrisome', 'troubling'
            ]
            
            # Defensiveness indicators
            defensive_words = [
                'however', 'but', 'although', 'despite', 'nevertheless', 'on the other hand',
                'it\'s important to note', 'we should clarify', 'to be clear', 'let me emphasize',
                'i want to be clear', 'let me clarify', 'to clarify', 'just to be clear'
            ]
            
            text_lower = text.lower()
            
            # Count sentiment words
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            defensive_count = sum(1 for word in defensive_words if word in text_lower)
            
            # Calculate sentiment score
            total_words = len(text.split())
            if total_words == 0:
                return 0.0
            
            sentiment_score = (positive_count - negative_count) / max(total_words / 100, 1)
            sentiment_score = max(-1.0, min(1.0, sentiment_score))  # Clamp to [-1, 1]
            
            # Adjust for defensiveness
            defensiveness_factor = min(defensive_count / max(total_words / 200, 1), 0.5)
            sentiment_score *= (1 - defensiveness_factor)
            
            return sentiment_score
            
        except Exception as e:
            logger.error(f"Error in local sentiment analysis: {e}")
            return 0.0
    
    def _extract_sentiment_drivers_local(self, text: str) -> List[str]:
        """Extract key sentiment drivers using local analysis"""
        try:
            drivers = []
            text_lower = text.lower()
            
            # Revenue-related drivers
            if any(word in text_lower for word in ['revenue', 'sales', 'top line']):
                if any(word in text_lower for word in ['strong', 'growth', 'increase', 'beat']):
                    drivers.append("Strong revenue performance")
                elif any(word in text_lower for word in ['weak', 'decline', 'miss', 'below']):
                    drivers.append("Revenue challenges")
            
            # Profitability drivers
            if any(word in text_lower for word in ['profit', 'margin', 'earnings', 'bottom line']):
                if any(word in text_lower for word in ['strong', 'improve', 'expand', 'beat']):
                    drivers.append("Improved profitability")
                elif any(word in text_lower for word in ['pressure', 'decline', 'compress']):
                    drivers.append("Profitability pressure")
            
            # Growth drivers
            if any(word in text_lower for word in ['growth', 'expansion', 'scaling']):
                drivers.append("Growth initiatives")
            
            # Market drivers
            if any(word in text_lower for word in ['market', 'competitive', 'market share']):
                drivers.append("Market position")
            
            # Innovation drivers
            if any(word in text_lower for word in ['innovation', 'technology', 'digital', 'transformation']):
                drivers.append("Innovation focus")
            
            # Limit to 3 drivers
            return drivers[:3]
            
        except Exception as e:
            logger.error(f"Error extracting sentiment drivers: {e}")
            return ["Analysis unavailable"]
    
    async def _extract_guidance(self, transcript_text: str) -> Dict[str, Any]:
        """Extract financial guidance from transcript using local analysis"""
        try:
            # Use local pattern matching instead of external LLM
            return self._extract_guidance_local(transcript_text)
        
        except Exception as e:
            logger.error(f"Error extracting guidance: {e}")
            return {}
    
    def _extract_guidance_local(self, transcript_text: str) -> Dict[str, Any]:
        """Extract guidance using comprehensive local pattern matching"""
        try:
            import re
            guidance = {}
            text_lower = transcript_text.lower()
            
            # Revenue guidance patterns
            revenue_patterns = [
                r'revenue.*guidance.*?(\$[\d,\.]+[BMK]?)',
                r'guidance.*revenue.*?(\$[\d,\.]+[BMK]?)',
                r'expect.*revenue.*?(\$[\d,\.]+[BMK]?)',
                r'project.*revenue.*?(\$[\d,\.]+[BMK]?)',
                r'forecast.*revenue.*?(\$[\d,\.]+[BMK]?)',
                r'revenue.*range.*?(\$[\d,\.]+[BMK]?.*?\$[\d,\.]+[BMK]?)',
                r'revenue.*between.*?(\$[\d,\.]+[BMK]?.*?\$[\d,\.]+[BMK]?)'
            ]
            
            revenue_guidance = []
            for pattern in revenue_patterns:
                matches = re.findall(pattern, transcript_text, re.IGNORECASE)
                revenue_guidance.extend(matches)
            
            if revenue_guidance:
                guidance["revenue"] = {
                    "amount": revenue_guidance[0],
                    "confidence": min(len(revenue_guidance) / 3.0, 1.0)
                }
            
            # Earnings guidance patterns
            earnings_patterns = [
                r'eps.*guidance.*?(\$[\d,\.]+)',
                r'guidance.*eps.*?(\$[\d,\.]+)',
                r'expect.*eps.*?(\$[\d,\.]+)',
                r'project.*eps.*?(\$[\d,\.]+)',
                r'earnings.*guidance.*?(\$[\d,\.]+[BMK]?)',
                r'guidance.*earnings.*?(\$[\d,\.]+[BMK]?)'
            ]
            
            earnings_guidance = []
            for pattern in earnings_patterns:
                matches = re.findall(pattern, transcript_text, re.IGNORECASE)
                earnings_guidance.extend(matches)
            
            if earnings_guidance:
                guidance["earnings"] = {
                    "eps": earnings_guidance[0] if earnings_guidance[0].startswith('$') else f"${earnings_guidance[0]}",
                    "confidence": min(len(earnings_guidance) / 3.0, 1.0)
                }
            
            # Margin guidance patterns
            margin_patterns = [
                r'margin.*guidance.*?(\d+\.?\d*%)',
                r'guidance.*margin.*?(\d+\.?\d*%)',
                r'expect.*margin.*?(\d+\.?\d*%)',
                r'gross.*margin.*?(\d+\.?\d*%)',
                r'operating.*margin.*?(\d+\.?\d*%)'
            ]
            
            margin_guidance = []
            for pattern in margin_patterns:
                matches = re.findall(pattern, transcript_text, re.IGNORECASE)
                margin_guidance.extend(matches)
            
            if margin_guidance:
                guidance["margins"] = {
                    "gross_margin": margin_guidance[0],
                    "confidence": min(len(margin_guidance) / 3.0, 1.0)
                }
            
            # Capital expenditure patterns
            capex_patterns = [
                r'capex.*guidance.*?(\$[\d,\.]+[BMK]?)',
                r'guidance.*capex.*?(\$[\d,\.]+[BMK]?)',
                r'capital.*expenditure.*?(\$[\d,\.]+[BMK]?)',
                r'investment.*guidance.*?(\$[\d,\.]+[BMK]?)'
            ]
            
            capex_guidance = []
            for pattern in capex_patterns:
                matches = re.findall(pattern, transcript_text, re.IGNORECASE)
                capex_guidance.extend(matches)
            
            if capex_guidance:
                guidance["capex"] = {
                    "amount": capex_guidance[0],
                    "confidence": min(len(capex_guidance) / 3.0, 1.0)
                }
            
            # Growth rate patterns
            growth_patterns = [
                r'growth.*rate.*?(\d+\.?\d*%)',
                r'year.*over.*year.*?(\d+\.?\d*%)',
                r'yoy.*growth.*?(\d+\.?\d*%)',
                r'growth.*guidance.*?(\d+\.?\d*%)'
            ]
            
            growth_guidance = []
            for pattern in growth_patterns:
                matches = re.findall(pattern, transcript_text, re.IGNORECASE)
                growth_guidance.extend(matches)
            
            if growth_guidance and "revenue" in guidance:
                guidance["revenue"]["growth_rate"] = growth_guidance[0]
            
            return guidance
            
        except Exception as e:
            logger.error(f"Error in local guidance extraction: {e}")
            return {}
    
    async def _analyze_qa_session(self, transcript_text: str) -> Dict[str, Any]:
        """Analyze Q&A session for defensiveness and key topics using local analysis"""
        try:
            # Use local analysis instead of external LLM
            return self._analyze_qa_local(transcript_text)
        
        except Exception as e:
            logger.error(f"Error analyzing Q&A session: {e}")
            return {
                "questions": [],
                "responses": [],
                "defensiveness": 0.5,
                "topics_avoided": []
            }
    
    def _analyze_qa_local(self, transcript_text: str) -> Dict[str, Any]:
        """Analyze Q&A session using local pattern matching"""
        try:
            import re
            text_lower = transcript_text.lower()
            
            # Find Q&A indicators
            qa_patterns = [
                r'question.*?answer',
                r'analyst.*?question',
                r'operator.*?question',
                r'next question',
                r'question from',
                r'let me.*?answer',
                r'that\'s a.*?question',
                r'good question',
                r'great question',
                r'follow-up question'
            ]
            
            qa_indicators = []
            for pattern in qa_patterns:
                matches = re.findall(pattern, transcript_text, re.IGNORECASE)
                qa_indicators.extend(matches)
            
            # Calculate defensiveness score
            defensive_phrases = [
                'i can\'t comment on that',
                'we don\'t provide guidance on',
                'that\'s not something we discuss',
                'i\'d rather not speculate',
                'we\'re not prepared to discuss',
                'that\'s confidential',
                'i can\'t go into details',
                'we\'ll have to see',
                'it\'s too early to tell',
                'we\'re not ready to comment'
            ]
            
            defensive_count = sum(1 for phrase in defensive_phrases if phrase in text_lower)
            total_words = len(transcript_text.split())
            defensiveness_score = min(defensive_count / max(total_words / 1000, 1), 1.0)
            
            # Extract questions (simple pattern matching)
            question_patterns = [
                r'question.*?[:?]',
                r'analyst.*?[:?]',
                r'operator.*?[:?]'
            ]
            
            questions = []
            for pattern in question_patterns:
                matches = re.findall(pattern, transcript_text, re.IGNORECASE)
                questions.extend(matches[:3])  # Limit to 3 questions
            
            # Identify topics that might be avoided
            avoided_topics = []
            if defensiveness_score > 0.3:
                avoided_topics = ["Future guidance", "Competitive positioning", "Market outlook"]
            
            return {
                "questions": questions[:5],  # Limit to 5 questions
                "responses": [],  # Would need more complex analysis
                "defensiveness": defensiveness_score,
                "topics_avoided": avoided_topics
            }
            
        except Exception as e:
            logger.error(f"Error in local Q&A analysis: {e}")
            return {
                "questions": [],
                "responses": [],
                "defensiveness": 0.5,
                "topics_avoided": []
            }
    
    async def _extract_key_topics(self, transcript_text: str) -> Dict[str, Any]:
        """Extract key topics, concerns, and new initiatives using local analysis"""
        try:
            # Use local analysis instead of external LLM
            return self._extract_topics_local(transcript_text)
        
        except Exception as e:
            logger.error(f"Error extracting key topics: {e}")
            return {
                "topics": [],
                "concerns": [],
                "initiatives": []
            }
    
    def _extract_topics_local(self, transcript_text: str) -> Dict[str, Any]:
        """Extract topics using comprehensive local keyword analysis"""
        try:
            text_lower = transcript_text.lower()
            
            # Financial and business topic keywords
            topic_keywords = {
                'revenue': ['revenue', 'sales', 'top line', 'income'],
                'profitability': ['profit', 'margin', 'earnings', 'profitability', 'bottom line'],
                'growth': ['growth', 'expansion', 'scaling', 'increasing'],
                'market': ['market', 'market share', 'competitive', 'competition'],
                'innovation': ['innovation', 'technology', 'digital', 'transformation'],
                'operations': ['operations', 'efficiency', 'productivity', 'cost'],
                'strategy': ['strategy', 'strategic', 'initiative', 'plan'],
                'risk': ['risk', 'challenge', 'headwind', 'uncertainty'],
                'guidance': ['guidance', 'outlook', 'forecast', 'expectation'],
                'investment': ['investment', 'capex', 'capital', 'spending']
            }
            
            # Score each topic based on keyword frequency
            topic_scores = {}
            for topic, keywords in topic_keywords.items():
                score = sum(text_lower.count(keyword) for keyword in keywords)
                if score > 0:
                    topic_scores[topic] = score
            
            # Get top topics
            sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
            top_topics = [topic for topic, score in sorted_topics[:7]]
            
            # Extract concerns
            concern_keywords = [
                'challenge', 'concern', 'risk', 'headwind', 'pressure', 'uncertainty',
                'volatile', 'difficult', 'struggle', 'decline', 'weak', 'miss',
                'below', 'disappointing', 'concerning', 'worrisome', 'troubling'
            ]
            
            concerns = []
            for keyword in concern_keywords:
                if keyword in text_lower:
                    concerns.append(f"Management mentioned {keyword}")
            
            # Extract initiatives
            initiative_keywords = [
                'new initiative', 'strategic initiative', 'launch', 'introduce',
                'expand', 'acquisition', 'partnership', 'investment', 'development',
                'innovation', 'transformation', 'digital', 'technology'
            ]
            
            initiatives = []
            for keyword in initiative_keywords:
                if keyword in text_lower:
                    initiatives.append(f"New {keyword} mentioned")
            
            return {
                "topics": top_topics,
                "concerns": concerns[:5],  # Limit to 5 concerns
                "initiatives": initiatives[:5]  # Limit to 5 initiatives
            }
            
        except Exception as e:
            logger.error(f"Error in local topic extraction: {e}")
            return {
                "topics": [],
                "concerns": [],
                "initiatives": []
            }
    
    def _extract_topics_keywords(self, transcript_text: str) -> Dict[str, Any]:
        """Extract topics using keyword analysis"""
        # Common business topics
        topic_keywords = {
            "revenue": ["revenue", "sales", "top line"],
            "profitability": ["profit", "margin", "earnings", "bottom line"],
            "growth": ["growth", "expansion", "increase"],
            "market": ["market", "competition", "market share"],
            "technology": ["technology", "digital", "innovation"],
            "costs": ["cost", "expense", "efficiency"],
            "guidance": ["guidance", "outlook", "forecast"]
        }
        
        topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in transcript_text.lower() for keyword in keywords):
                topics.append(topic)
        
        return {
            "topics": topics[:5],
            "concerns": [],
            "initiatives": []
        }
    
    def _calculate_quality_metrics(self, transcript_text: str) -> Dict[str, float]:
        """Calculate call quality metrics"""
        # Simple quality metrics based on transcript characteristics
        word_count = len(transcript_text.split())
        
        # Quality score based on length and structure
        quality_score = min(1.0, word_count / 5000)  # Normalize to 5000 words
        
        # Information density (words per sentence)
        sentences = transcript_text.split('.')
        avg_words_per_sentence = word_count / max(len(sentences), 1)
        density_score = min(1.0, avg_words_per_sentence / 20)  # Normalize to 20 words/sentence
        
        # Transparency score (based on specific words)
        transparency_words = ["guidance", "outlook", "forecast", "expect", "plan"]
        transparency_count = sum(1 for word in transparency_words if word in transcript_text.lower())
        transparency_score = min(1.0, transparency_count / 10)  # Normalize to 10 mentions
        
        return {
            "quality": quality_score,
            "density": density_score,
            "transparency": transparency_score
        }
    
    def _aggregate_analyses(self, analyses: List[CallAnalysis]) -> Dict[str, Any]:
        """Aggregate multiple call analyses"""
        if not analyses:
            return {}
        
        # Calculate averages
        avg_sentiment = sum(a.overall_sentiment for a in analyses) / len(analyses)
        avg_confidence = sum(a.confidence_score for a in analyses) / len(analyses)
        avg_defensiveness = sum(a.defensiveness_score for a in analyses) / len(analyses)
        avg_quality = sum(a.call_quality_score for a in analyses) / len(analyses)
        
        # Aggregate guidance
        all_guidance = {
            "revenue": [],
            "earnings": [],
            "margins": [],
            "capex": []
        }
        
        for analysis in analyses:
            if analysis.revenue_guidance:
                all_guidance["revenue"].append(analysis.revenue_guidance)
            if analysis.earnings_guidance:
                all_guidance["earnings"].append(analysis.earnings_guidance)
            if analysis.margin_guidance:
                all_guidance["margins"].append(analysis.margin_guidance)
            if analysis.capex_guidance:
                all_guidance["capex"].append(analysis.capex_guidance)
        
        # Aggregate topics
        all_topics = []
        all_concerns = []
        all_initiatives = []
        
        for analysis in analyses:
            all_topics.extend(analysis.key_topics)
            all_concerns.extend(analysis.concerns_raised)
            all_initiatives.extend(analysis.new_initiatives)
        
        # Get most common items
        from collections import Counter
        common_topics = [item for item, count in Counter(all_topics).most_common(5)]
        common_concerns = [item for item, count in Counter(all_concerns).most_common(3)]
        common_initiatives = [item for item, count in Counter(all_initiatives).most_common(3)]
        
        return {
            "aggregated_sentiment": {
                "overall_sentiment": avg_sentiment,
                "confidence_score": avg_confidence,
                "defensiveness_score": avg_defensiveness,
                "call_quality": avg_quality
            },
            "guidance_summary": all_guidance,
            "key_topics": common_topics,
            "common_concerns": common_concerns,
            "new_initiatives": common_initiatives,
            "individual_analyses": [
                {
                    "quarter": a.quarter,
                    "call_date": a.call_date.isoformat(),
                    "sentiment": a.overall_sentiment,
                    "tone": a.management_tone,
                    "defensiveness": a.defensiveness_score,
                    "quality_score": a.call_quality_score
                }
                for a in analyses
            ]
        }


# Global analyzer instance to maintain cache between calls
_global_analyzer = None

async def get_global_analyzer() -> EarningsCallAnalyzer:
    """Get or create the global analyzer instance"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = EarningsCallAnalyzer()
        # Initialize sources with shared cache when the global analyzer is first created
        await _global_analyzer._initialize_sources() 
    return _global_analyzer

# Main function for integration
async def analyze_earnings_calls(ticker: str, days_back: int = 90, max_calls: int = 5) -> Dict[str, Any]:
    """
    Main function to analyze earnings calls for a ticker
    
    Args:
        ticker: Stock ticker symbol
        days_back: Number of days to look back
        max_calls: Maximum number of calls to analyze
        
    Returns:
        Comprehensive earnings call analysis
    """
    analyzer = await get_global_analyzer()
    try:
        return await analyzer.analyze_earnings_calls(ticker, days_back, max_calls)
    except Exception as e:
        logger.error(f"Error in analyze_earnings_calls for {ticker}: {e}")
        return {
            "status": "error",
            "transcripts": [],
            "analysis": {
                "management_sentiment": {"overall_sentiment": 0.0, "confidence_score": 0.0},
                "guidance_analysis": {},
                "key_insights": {"topics_discussed": [], "concerns_raised": [], "new_initiatives": []},
                "summary_insights": f"Error analyzing earnings calls for {ticker}: {e}",
                "confidence_score": 0.0
            }
        }
