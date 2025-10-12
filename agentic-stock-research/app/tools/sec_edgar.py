"""
SEC Edgar Filing Integration

Fetches and analyzes SEC regulatory filings (10-K, 10-Q, 8-K) for US companies.
Provides filing summaries, key section extraction, and change detection.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import aiohttp
import yfinance as yf
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class FilingType(str, Enum):
    """SEC filing types"""
    FORM_10K = "10-K"  # Annual report
    FORM_10Q = "10-Q"  # Quarterly report
    FORM_8K = "8-K"    # Current report (material events)
    FORM_4 = "4"       # Insider trading
    FORM_13F = "13F-HR"  # Institutional holdings
    FORM_DEF14A = "DEF 14A"  # Proxy statement


@dataclass
class SECFiling:
    """SEC filing metadata and content"""
    ticker: str
    filing_type: FilingType
    filing_date: datetime
    report_date: datetime
    accession_number: str
    url: str
    
    # Content sections (extracted)
    business_description: Optional[str] = None
    risk_factors: Optional[str] = None
    md_and_a: Optional[str] = None  # Management Discussion & Analysis
    financial_statements: Optional[str] = None
    
    # Summary
    executive_summary: Optional[str] = None
    key_points: List[str] = None
    
    def __post_init__(self):
        if self.key_points is None:
            self.key_points = []


@dataclass
class FilingComparison:
    """Comparison between consecutive filings"""
    current_filing: SECFiling
    previous_filing: SECFiling
    changes_detected: List[Dict[str, Any]]
    risk_factor_changes: List[str]
    new_risks: List[str]
    removed_risks: List[str]


class SECEdgarClient:
    """
    SEC Edgar API client for fetching and parsing regulatory filings
    
    Uses the official SEC Edgar API (rate limit: 10 requests/second)
    """
    
    BASE_URL = "https://www.sec.gov"
    API_URL = f"{BASE_URL}/cgi-bin/browse-edgar"
    
    def __init__(self, user_agent: str = "EquiSense AI research@equisense.ai"):
        """
        Initialize SEC Edgar client
        
        Args:
            user_agent: Required by SEC (must include email/contact info)
        """
        self.user_agent = user_agent
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = asyncio.Semaphore(10)  # 10 requests/second
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                    "Host": "www.sec.gov"
                }
            )
        return self.session
    
    async def close(self):
        """Close the HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_cik_from_ticker(self, ticker: str) -> Optional[str]:
        """
        Get CIK (Central Index Key) from ticker symbol
        
        Args:
            ticker: Stock ticker (e.g., "AAPL")
        
        Returns:
            CIK string (10-digit padded) or None
        """
        try:
            # Use yfinance to get CIK if available
            t = yf.Ticker(ticker)
            info = t.info or {}
            
            # Try to extract CIK from info
            cik = info.get("cik")
            if cik:
                return str(cik).zfill(10)  # Pad to 10 digits
            
            # Fallback: Search SEC company lookup
            session = await self._get_session()
            async with session.get(
                f"{self.BASE_URL}/cgi-bin/browse-edgar",
                params={
                    "company": ticker,
                    "action": "getcompany",
                    "output": "atom"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    # Parse CIK from response
                    match = re.search(r'CIK=(\d+)', text)
                    if match:
                        return match.group(1).zfill(10)
            
            logger.warning(f"Could not find CIK for ticker {ticker}")
            return None
        
        except Exception as e:
            logger.error(f"Error fetching CIK for {ticker}: {e}")
            return None
    
    async def get_recent_filings(
        self,
        ticker: str,
        filing_types: List[FilingType],
        count: int = 5,
        start_date: Optional[datetime] = None
    ) -> List[SECFiling]:
        """
        Get recent filings for a company
        
        Args:
            ticker: Stock ticker
            filing_types: List of filing types to retrieve
            count: Number of filings per type
            start_date: Only get filings after this date
        
        Returns:
            List of SECFiling objects
        """
        try:
            # Get CIK
            cik = await self.get_cik_from_ticker(ticker)
            if not cik:
                logger.warning(f"Could not find CIK for {ticker}, returning empty filings list")
                return []
            
            filings = []
            
            # Fetch each filing type
            for filing_type in filing_types:
                async with self._rate_limiter:  # Rate limiting
                    type_filings = await self._fetch_filings_by_type(
                        cik, ticker, filing_type, count, start_date
                    )
                    filings.extend(type_filings)
                    await asyncio.sleep(0.1)  # Polite delay
            
            # Sort by filing date (most recent first)
            filings.sort(key=lambda f: f.filing_date, reverse=True)
            
            return filings
        
        except Exception as e:
            logger.error(f"Error fetching recent filings for {ticker}: {e}")
            return []
    
    async def _fetch_filings_by_type(
        self,
        cik: str,
        ticker: str,
        filing_type: FilingType,
        count: int,
        start_date: Optional[datetime]
    ) -> List[SECFiling]:
        """Fetch filings of a specific type"""
        try:
            session = await self._get_session()
            
            # Build query
            params = {
                "action": "getcompany",
                "CIK": cik,
                "type": filing_type.value,
                "dateb": "",
                "owner": "exclude",
                "count": count,
                "output": "atom"
            }
            
            async with session.get(
                f"{self.BASE_URL}/cgi-bin/browse-edgar",
                params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    logger.warning(f"SEC API returned {response.status} for {ticker} {filing_type}")
                    return []
                
                text = await response.text()
                filings = self._parse_atom_feed(text, ticker, filing_type)
                
                # Filter by start_date if provided
                if start_date:
                    filings = [f for f in filings if f.filing_date >= start_date]
                
                return filings
        
        except Exception as e:
            logger.error(f"Error fetching {filing_type} for {ticker}: {e}")
            return []
    
    def _parse_atom_feed(self, atom_xml: str, ticker: str, filing_type: FilingType) -> List[SECFiling]:
        """Parse SEC Atom feed XML"""
        filings = []
        
        try:
            soup = BeautifulSoup(atom_xml, 'xml')
            entries = soup.find_all('entry')
            
            for entry in entries:
                try:
                    # Extract metadata
                    filing_date_str = entry.find('filing-date').text if entry.find('filing-date') else None
                    filing_href = entry.find('filing-href').text if entry.find('filing-href') else None
                    accession_number = entry.find('accession-number').text if entry.find('accession-number') else ""
                    
                    if not filing_date_str or not filing_href:
                        continue
                    
                    filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")
                    
                    # For report date, try to extract from title or use filing date
                    report_date = filing_date  # Default
                    title = entry.find('title')
                    if title:
                        # Try to extract date from title like "10-Q - 2024-09-30"
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', title.text)
                        if date_match:
                            try:
                                report_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                            except:
                                pass
                    
                    filing = SECFiling(
                        ticker=ticker,
                        filing_type=filing_type,
                        filing_date=filing_date,
                        report_date=report_date,
                        accession_number=accession_number,
                        url=filing_href
                    )
                    
                    filings.append(filing)
                
                except Exception as e:
                    logger.warning(f"Error parsing filing entry: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing Atom feed: {e}")
        
        return filings
    
    async def extract_filing_content(self, filing: SECFiling) -> SECFiling:
        """
        Extract key sections from a filing
        
        Args:
            filing: SECFiling object with URL
        
        Returns:
            Same filing object with extracted content
        """
        try:
            session = await self._get_session()
            
            async with session.get(
                filing.url,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    logger.warning(f"Could not fetch filing content from {filing.url}")
                    return filing
                
                html = await response.text()
                
                # Parse HTML content
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract sections based on filing type
                if filing.filing_type in [FilingType.FORM_10K, FilingType.FORM_10Q]:
                    filing.business_description = self._extract_section(soup, ["Item 1", "Business"])
                    filing.risk_factors = self._extract_section(soup, ["Item 1A", "Risk Factors"])
                    filing.md_and_a = self._extract_section(soup, ["Item 2", "Item 7", "Management's Discussion"])
                    filing.financial_statements = self._extract_section(soup, ["Item 8", "Financial Statements"])
                
                # Generate executive summary (placeholder - would use LLM in production)
                filing.executive_summary = self._generate_executive_summary(filing)
                filing.key_points = self._extract_key_points(filing)
            
            return filing
        
        except Exception as e:
            logger.error(f"Error extracting filing content: {e}")
            return filing
    
    def _extract_section(self, soup: BeautifulSoup, keywords: List[str]) -> Optional[str]:
        """Extract a section from filing HTML based on keywords"""
        try:
            # Look for section headers containing keywords
            for keyword in keywords:
                # Try different tag types
                for tag in ['div', 'p', 'span', 'b', 'strong', 'font']:
                    elements = soup.find_all(tag, string=re.compile(keyword, re.IGNORECASE))
                    
                    for element in elements:
                        # Get the next few siblings (section content)
                        content_parts = []
                        current = element.find_next_sibling()
                        
                        # Collect content until next section or max length
                        while current and len(''.join(content_parts)) < 5000:
                            if current.name in ['div', 'p']:
                                text = current.get_text(strip=True)
                                if text:
                                    content_parts.append(text)
                            current = current.find_next_sibling()
                        
                        if content_parts:
                            return '\n\n'.join(content_parts[:20])  # First 20 paragraphs
            
            return None
        
        except Exception as e:
            logger.warning(f"Error extracting section: {e}")
            return None
    
    def _generate_executive_summary(self, filing: SECFiling) -> str:
        """Generate a simple executive summary (placeholder for LLM-based summarization)"""
        summary_parts = [
            f"{filing.filing_type.value} filed on {filing.filing_date.strftime('%Y-%m-%d')}",
            f"Reporting period: {filing.report_date.strftime('%Y-%m-%d')}"
        ]
        
        if filing.risk_factors:
            summary_parts.append("Risk factors section updated")
        
        if filing.md_and_a:
            summary_parts.append("Management discussion included")
        
        return ". ".join(summary_parts)
    
    def _extract_key_points(self, filing: SECFiling) -> List[str]:
        """Extract key points from filing (placeholder for NLP-based extraction)"""
        points = []
        
        # Simple heuristic-based extraction
        if filing.md_and_a:
            # Look for sentences with key financial terms
            financial_keywords = ['revenue', 'profit', 'margin', 'growth', 'decline', 'increase', 'decrease']
            sentences = filing.md_and_a.split('.')
            
            for sentence in sentences[:50]:  # First 50 sentences
                if any(keyword in sentence.lower() for keyword in financial_keywords):
                    cleaned = sentence.strip()
                    if len(cleaned) > 30 and len(cleaned) < 200:
                        points.append(cleaned)
                        if len(points) >= 5:
                            break
        
        return points


async def get_recent_sec_filings(
    ticker: str,
    filing_types: Optional[List[FilingType]] = None,
    count: int = 3,
    include_content: bool = False
) -> List[SECFiling]:
    """
    Convenience function to get recent SEC filings
    
    Args:
        ticker: Stock ticker
        filing_types: List of filing types (default: 10-K, 10-Q, 8-K)
        count: Number of filings per type
        include_content: Whether to extract content sections
    
    Returns:
        List of SECFiling objects
    """
    if filing_types is None:
        filing_types = [FilingType.FORM_10K, FilingType.FORM_10Q, FilingType.FORM_8K]
    
    client = SECEdgarClient()
    
    try:
        filings = await client.get_recent_filings(ticker, filing_types, count)
        
        if include_content:
            # Extract content for each filing
            filings = await asyncio.gather(*[
                client.extract_filing_content(filing)
                for filing in filings
            ])
        
        return filings
    
    finally:
        await client.close()


async def compare_consecutive_filings(
    ticker: str,
    filing_type: FilingType = FilingType.FORM_10K
) -> Optional[FilingComparison]:
    """
    Compare two consecutive filings to detect changes
    
    Args:
        ticker: Stock ticker
        filing_type: Filing type to compare
    
    Returns:
        FilingComparison object or None
    """
    client = SECEdgarClient()
    
    try:
        # Get last 2 filings
        filings = await client.get_recent_filings(ticker, [filing_type], count=2)
        
        if len(filings) < 2:
            logger.warning(f"Not enough filings to compare for {ticker}")
            return None
        
        # Extract content
        current = await client.extract_filing_content(filings[0])
        previous = await client.extract_filing_content(filings[1])
        
        # Detect changes (simple placeholder - would use NLP in production)
        changes = []
        risk_changes = []
        new_risks = []
        removed_risks = []
        
        # Compare risk factors
        if current.risk_factors and previous.risk_factors:
            curr_risks = set(current.risk_factors.split('.'))
            prev_risks = set(previous.risk_factors.split('.'))
            
            new_risks = list(curr_risks - prev_risks)[:3]  # Top 3
            removed_risks = list(prev_risks - curr_risks)[:3]
            
            if new_risks or removed_risks:
                risk_changes.append(f"{len(new_risks)} new risks, {len(removed_risks)} removed")
        
        return FilingComparison(
            current_filing=current,
            previous_filing=previous,
            changes_detected=changes,
            risk_factor_changes=risk_changes,
            new_risks=new_risks,
            removed_risks=removed_risks
        )
    
    finally:
        await client.close()

