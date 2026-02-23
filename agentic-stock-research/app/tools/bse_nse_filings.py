"""BSE/NSE Filing Analysis System for Indian regulatory filings."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

import aiohttp
from bs4 import BeautifulSoup

from app.cache.redis_cache import get_cache_manager

logger = logging.getLogger(__name__)

try:
    import PyPDF2
    import pytesseract
    from PIL import Image
    import io
    PDF_PROCESSING_AVAILABLE = True
except ImportError:
    PDF_PROCESSING_AVAILABLE = False
    logger.warning("PDF processing libraries not available. OCR functionality will be disabled.")


class FilingType(Enum):
    ANNUAL_REPORT = "annual_report"
    QUARTERLY_RESULTS = "quarterly_results"
    CORPORATE_ANNOUNCEMENT = "corporate_announcement"
    BOARD_MEETING = "board_meeting"
    INSIDER_TRADING = "insider_trading"
    SHAREHOLDING_PATTERN = "shareholding_pattern"


@dataclass
class IndianFiling:
    ticker: str
    filing_type: FilingType
    filing_date: datetime
    title: str
    url: str
    exchange: str
    content: Optional[str] = None
    summary: Optional[str] = None
    key_metrics: Dict[str, Any] = field(default_factory=dict)
    management_commentary: Optional[str] = None
    risk_factors: List[str] = field(default_factory=list)
    filing_id: Optional[str] = None


_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"]
_SESSION_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _parse_filing_date(date_str: str) -> Optional[datetime]:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _classify_filing_type(title: str) -> FilingType:
    t = title.lower()
    if "annual report" in t:
        return FilingType.ANNUAL_REPORT
    if any(k in t for k in ("quarterly", "q1", "q2", "q3", "q4")):
        return FilingType.QUARTERLY_RESULTS
    if any(k in t for k in ("board meeting", "board resolution")):
        return FilingType.BOARD_MEETING
    if any(k in t for k in ("insider", "promoter")):
        return FilingType.INSIDER_TRADING
    if any(k in t for k in ("shareholding", "holding pattern")):
        return FilingType.SHAREHOLDING_PATTERN
    return FilingType.CORPORATE_ANNOUNCEMENT


class _ExchangeFilingAnalyzer:
    """Base class for BSE/NSE filing fetchers."""

    def __init__(self, base_url: str, exchange: str, cache_prefix: str):
        self.base_url = base_url
        self.exchange = exchange
        self.cache_prefix = cache_prefix
        self.cache = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_cache(self):
        if self.cache is None:
            self.cache = await get_cache_manager()
        return self.cache

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers=_SESSION_HEADERS,
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def get_company_filings(self, ticker: str, days_back: int = 90) -> List[IndianFiling]:
        cache_key = f"{self.cache_prefix}:{ticker}:{days_back}"
        cache = await self._ensure_cache()
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Retrieved {self.exchange} filings from cache for {ticker}")
            return [IndianFiling(**f) for f in cached]

        try:
            session = await self._get_session()
            filings = await self._fetch_filings(session, ticker, days_back)
            cache = await self._ensure_cache()
            await cache.set(cache_key, [f.__dict__ for f in filings], ttl=7200)
            logger.info(f"Retrieved {len(filings)} {self.exchange} filings for {ticker}")
            return filings
        except Exception as e:
            logger.error(f"Error fetching {self.exchange} filings for {ticker}: {e}")
            return []

    async def _fetch_filings(self, session: aiohttp.ClientSession, ticker: str, days_back: int) -> List[IndianFiling]:
        filings = []
        try:
            await asyncio.sleep(1.0)
            async with session.get(self._listings_url()) as response:
                if response.status != 200:
                    logger.warning(f"{self.exchange} returned {response.status} for {ticker}")
                    return filings
                soup = BeautifulSoup(await response.text(), "html.parser")
                for row in soup.find_all("tr", class_="TTRow")[:20]:
                    try:
                        cells = row.find_all("td")
                        if len(cells) < 4:
                            continue
                        title = cells[1].get_text(strip=True)
                        link = cells[2].find("a")
                        if not (link and title):
                            continue
                        filing_date = _parse_filing_date(cells[0].get_text(strip=True))
                        if filing_date and (datetime.now() - filing_date).days <= days_back:
                            filings.append(IndianFiling(
                                ticker=ticker,
                                filing_type=_classify_filing_type(title),
                                filing_date=filing_date,
                                title=title,
                                url=f"{self.base_url}{link['href']}",
                                exchange=self.exchange,
                            ))
                    except Exception as e:
                        logger.warning(f"Error parsing {self.exchange} filing row: {e}")
        except Exception as e:
            logger.error(f"Error fetching {self.exchange} filings: {e}")
        return filings

    def _listings_url(self) -> str:
        raise NotImplementedError


class BSEFilingAnalyzer(_ExchangeFilingAnalyzer):
    def __init__(self):
        super().__init__("https://www.bseindia.com", "BSE", "bse_filings")

    def _listings_url(self) -> str:
        return f"{self.base_url}/corporate/List_Scrips.aspx"


class NSEFilingAnalyzer(_ExchangeFilingAnalyzer):
    def __init__(self):
        super().__init__("https://www.nseindia.com", "NSE", "nse_filings")

    def _listings_url(self) -> str:
        return f"{self.base_url}/corporates/corporateHome.html"


class IndianFilingAnalyzer:
    """Main Indian filing analysis orchestrator (BSE + NSE)."""

    def __init__(self):
        self.bse_analyzer = BSEFilingAnalyzer()
        self.nse_analyzer = NSEFilingAnalyzer()
        self.cache = None

    async def _ensure_cache(self):
        if self.cache is None:
            self.cache = await get_cache_manager()
        return self.cache

    async def close(self):
        await self.bse_analyzer.close()
        await self.nse_analyzer.close()

    async def analyze_company_filings(self, ticker: str, days_back: int = 90) -> Dict[str, Any]:
        cache_key = f"indian_filing_analysis:{ticker}:{days_back}"
        cache = await self._ensure_cache()
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Retrieved Indian filing analysis from cache for {ticker}")
            return cached

        try:
            bse_filings, nse_filings = await asyncio.gather(
                self.bse_analyzer.get_company_filings(ticker, days_back),
                self.nse_analyzer.get_company_filings(ticker, days_back),
            )
            all_filings = self._deduplicate_filings(bse_filings + nse_filings)
            analysis = self._analyze_filings(all_filings)
            cache = await self._ensure_cache()
            await cache.set(cache_key, analysis, ttl=14400)
            logger.info(f"Analyzed {len(all_filings)} Indian filings for {ticker}")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing Indian filings for {ticker}: {e}")
            return {
                "ticker": ticker, "total_filings": 0, "filing_summary": {},
                "recent_developments": [], "management_commentary": "",
                "risk_factors": [], "key_metrics": {},
                "analysis_date": datetime.now().isoformat(), "error": str(e),
            }

    def _deduplicate_filings(self, filings: List[IndianFiling]) -> List[IndianFiling]:
        seen, unique = set(), []
        for f in filings:
            key = (f.title.lower().strip(), f.filing_date.date())
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return sorted(unique, key=lambda x: x.filing_date, reverse=True)

    def _analyze_filings(self, filings: List[IndianFiling]) -> Dict[str, Any]:
        if not filings:
            return {
                "total_filings": 0, "filing_summary": {}, "recent_developments": [],
                "management_commentary": "", "risk_factors": [], "key_metrics": {},
                "analysis_date": datetime.now().isoformat(),
            }

        filing_summary = {ft.value: sum(1 for f in filings if f.filing_type == ft) for ft in FilingType}

        recent_cutoff = datetime.now() - timedelta(days=30)
        recent_developments = [
            {"date": f.filing_date.isoformat(), "type": f.filing_type.value,
             "title": f.title, "exchange": f.exchange}
            for f in filings if f.filing_date >= recent_cutoff
        ][:10]

        annual_count = sum(1 for f in filings if f.filing_type == FilingType.ANNUAL_REPORT)
        management_commentary = (
            f"Management commentary available from {annual_count} annual report(s). "
            "Detailed extraction requires PDF processing."
            if annual_count else "No annual reports available for management commentary extraction."
        )

        risk_filings = [f for f in filings if "risk" in f.title.lower()]
        risk_factors = (
            [f"{f.title} ({f.filing_date.strftime('%Y-%m-%d')})" for f in risk_filings[:5]]
            or ["No specific risk factor filings identified in recent period."]
        )

        quarterly = [f for f in filings if f.filing_type == FilingType.QUARTERLY_RESULTS]
        key_metrics = (
            {
                "quarterly_reports_count": len(quarterly),
                "latest_quarter": quarterly[0].filing_date.isoformat(),
                "message": "Detailed financial metrics extraction requires XBRL processing.",
            }
            if quarterly else {"message": "No quarterly results available for metric extraction."}
        )

        return {
            "total_filings": len(filings),
            "filing_summary": filing_summary,
            "recent_developments": recent_developments,
            "management_commentary": management_commentary,
            "risk_factors": risk_factors,
            "key_metrics": key_metrics,
            "analysis_date": datetime.now().isoformat(),
        }


async def analyze_indian_filings(ticker: str, days_back: int = 90) -> Dict[str, Any]:
    """Main entry point: analyze Indian regulatory filings from BSE and NSE."""
    analyzer = IndianFilingAnalyzer()
    try:
        return await analyzer.analyze_company_filings(ticker, days_back)
    finally:
        await analyzer.close()
