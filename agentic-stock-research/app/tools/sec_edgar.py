"""
SEC Edgar Filing Integration
Fetches and analyzes SEC regulatory filings (10-K, 10-Q, 8-K) for US companies.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp
import yfinance as yf
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_FINANCIAL_KW = ["revenue", "profit", "margin", "growth", "decline", "increase", "decrease"]
_CONTENT_SELECTORS = {
    "10-K": {"business": ["Item 1", "Business"], "risk": ["Item 1A", "Risk Factors"],
             "mda": ["Item 2", "Item 7", "Management's Discussion"],
             "financials": ["Item 8", "Financial Statements"]},
    "10-Q": {"business": ["Item 1", "Business"], "risk": ["Item 1A", "Risk Factors"],
             "mda": ["Item 2", "Item 7", "Management's Discussion"],
             "financials": ["Item 8", "Financial Statements"]},
}


class FilingType(str, Enum):
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_4 = "4"
    FORM_13F = "13F-HR"
    FORM_DEF14A = "DEF 14A"


@dataclass
class SECFiling:
    ticker: str
    filing_type: FilingType
    filing_date: datetime
    report_date: datetime
    accession_number: str
    url: str
    business_description: Optional[str] = None
    risk_factors: Optional[str] = None
    md_and_a: Optional[str] = None
    financial_statements: Optional[str] = None
    executive_summary: Optional[str] = None
    key_points: List[str] = field(default_factory=list)


@dataclass
class FilingComparison:
    current_filing: SECFiling
    previous_filing: SECFiling
    changes_detected: List[Dict[str, Any]]
    risk_factor_changes: List[str]
    new_risks: List[str]
    removed_risks: List[str]


class SECEdgarClient:
    """SEC Edgar API client (rate limit: 10 req/sec)."""

    BASE_URL = "https://www.sec.gov"

    def __init__(self, user_agent: str = "EquiSense AI research@equisense.ai"):
        self.user_agent = user_agent
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = asyncio.Semaphore(10)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov"
            })
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_cik_from_ticker(self, ticker: str) -> Optional[str]:
        try:
            info = yf.Ticker(ticker).info or {}
            if cik := info.get("cik"):
                return str(cik).zfill(10)
            session = await self._get_session()
            async with session.get(
                f"{self.BASE_URL}/cgi-bin/browse-edgar",
                params={"company": ticker, "action": "getcompany", "output": "atom"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    if m := re.search(r"CIK=(\d+)", await resp.text()):
                        return m.group(1).zfill(10)
        except Exception as e:
            logger.error(f"CIK fetch error for {ticker}: {e}")
        return None

    async def get_recent_filings(self, ticker: str, filing_types: List[FilingType],
                                  count: int = 5, start_date: Optional[datetime] = None) -> List[SECFiling]:
        cik = await self.get_cik_from_ticker(ticker)
        if not cik:
            return []
        filings = []
        for ft in filing_types:
            async with self._rate_limiter:
                filings.extend(await self._fetch_filings_by_type(cik, ticker, ft, count, start_date))
                await asyncio.sleep(0.1)
        filings.sort(key=lambda f: f.filing_date, reverse=True)
        return filings

    async def _fetch_filings_by_type(self, cik: str, ticker: str, filing_type: FilingType,
                                      count: int, start_date: Optional[datetime]) -> List[SECFiling]:
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.BASE_URL}/cgi-bin/browse-edgar",
                params={"action": "getcompany", "CIK": cik, "type": filing_type.value,
                        "dateb": "", "owner": "exclude", "count": count, "output": "atom"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return []
                filings = self._parse_atom_feed(await resp.text(), ticker, filing_type)
                return [f for f in filings if not start_date or f.filing_date >= start_date]
        except Exception as e:
            logger.error(f"Filing fetch error {filing_type} for {ticker}: {e}")
            return []

    def _parse_atom_feed(self, xml: str, ticker: str, filing_type: FilingType) -> List[SECFiling]:
        filings = []
        try:
            soup = BeautifulSoup(xml, "xml")
            for entry in soup.find_all("entry"):
                try:
                    date_str = entry.find("filing-date")
                    href = entry.find("filing-href")
                    if not (date_str and href):
                        continue
                    filing_date = datetime.strptime(date_str.text, "%Y-%m-%d")
                    report_date = filing_date
                    if title := entry.find("title"):
                        if m := re.search(r"(\d{4}-\d{2}-\d{2})", title.text):
                            try:
                                report_date = datetime.strptime(m.group(1), "%Y-%m-%d")
                            except Exception:
                                pass
                    acc = entry.find("accession-number")
                    filings.append(SECFiling(
                        ticker=ticker, filing_type=filing_type,
                        filing_date=filing_date, report_date=report_date,
                        accession_number=acc.text if acc else "",
                        url=href.text
                    ))
                except Exception as e:
                    logger.warning(f"Entry parse error: {e}")
        except Exception as e:
            logger.error(f"Atom feed parse error: {e}")
        return filings

    async def extract_filing_content(self, filing: SECFiling) -> SECFiling:
        try:
            session = await self._get_session()
            async with session.get(filing.url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return filing
                soup = BeautifulSoup(await resp.text(), "html.parser")
                if filing.filing_type.value in _CONTENT_SELECTORS:
                    cfg = _CONTENT_SELECTORS[filing.filing_type.value]
                    filing.business_description = self._extract_section(soup, cfg["business"])
                    filing.risk_factors = self._extract_section(soup, cfg["risk"])
                    filing.md_and_a = self._extract_section(soup, cfg["mda"])
                    filing.financial_statements = self._extract_section(soup, cfg["financials"])
                filing.executive_summary = self._make_summary(filing)
                filing.key_points = self._extract_key_points(filing)
        except Exception as e:
            logger.error(f"Content extraction error: {e}")
        return filing

    def _extract_section(self, soup: BeautifulSoup, keywords: List[str]) -> Optional[str]:
        for kw in keywords:
            for tag in ["div", "p", "span", "b", "strong", "font"]:
                for el in soup.find_all(tag, string=re.compile(kw, re.IGNORECASE)):
                    parts, cur = [], el.find_next_sibling()
                    while cur and len("".join(parts)) < 5000:
                        if cur.name in ["div", "p"] and (t := cur.get_text(strip=True)):
                            parts.append(t)
                        cur = cur.find_next_sibling()
                    if parts:
                        return "\n\n".join(parts[:20])
        return None

    def _make_summary(self, f: SECFiling) -> str:
        parts = [f"{f.filing_type.value} filed on {f.filing_date:%Y-%m-%d}",
                 f"Reporting period: {f.report_date:%Y-%m-%d}"]
        if f.risk_factors:
            parts.append("Risk factors section updated")
        if f.md_and_a:
            parts.append("Management discussion included")
        return ". ".join(parts)

    def _extract_key_points(self, f: SECFiling) -> List[str]:
        if not f.md_and_a:
            return []
        points = []
        for sent in f.md_and_a.split(".")[:50]:
            if any(kw in sent.lower() for kw in _FINANCIAL_KW):
                cleaned = sent.strip()
                if 30 < len(cleaned) < 200:
                    points.append(cleaned)
                    if len(points) >= 5:
                        break
        return points


async def get_recent_sec_filings(ticker: str, filing_types: Optional[List[FilingType]] = None,
                                  count: int = 3, include_content: bool = False) -> List[SECFiling]:
    """Get recent SEC filings for a ticker."""
    filing_types = filing_types or [FilingType.FORM_10K, FilingType.FORM_10Q, FilingType.FORM_8K]
    client = SECEdgarClient()
    try:
        filings = await client.get_recent_filings(ticker, filing_types, count)
        if include_content:
            filings = list(await asyncio.gather(*[client.extract_filing_content(f) for f in filings]))
        return filings
    finally:
        await client.close()


async def compare_consecutive_filings(ticker: str,
                                       filing_type: FilingType = FilingType.FORM_10K) -> Optional[FilingComparison]:
    """Compare two consecutive filings to detect changes."""
    client = SECEdgarClient()
    try:
        filings = await client.get_recent_filings(ticker, [filing_type], count=2)
        if len(filings) < 2:
            return None
        current, previous = await asyncio.gather(
            client.extract_filing_content(filings[0]),
            client.extract_filing_content(filings[1])
        )
        new_risks, removed_risks, risk_changes = [], [], []
        if current.risk_factors and previous.risk_factors:
            curr_s = set(current.risk_factors.split("."))
            prev_s = set(previous.risk_factors.split("."))
            new_risks = list(curr_s - prev_s)[:3]
            removed_risks = list(prev_s - curr_s)[:3]
            if new_risks or removed_risks:
                risk_changes.append(f"{len(new_risks)} new risks, {len(removed_risks)} removed")
        return FilingComparison(current_filing=current, previous_filing=previous,
                                changes_detected=[], risk_factor_changes=risk_changes,
                                new_risks=new_risks, removed_risks=removed_risks)
    finally:
        await client.close()
