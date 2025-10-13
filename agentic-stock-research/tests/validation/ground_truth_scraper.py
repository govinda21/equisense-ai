"""
Ground truth data scraper for Screener.in
Uses Playwright for reliable scraping with caching
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logging.warning("Playwright not available. Install with: pip install playwright && playwright install chromium")

from tests.validation.test_data import get_screener_id

logger = logging.getLogger(__name__)


class ScreenerScraper:
    """Scraper for Screener.in financial data"""
    
    def __init__(self, cache_dir: str = "tests/validation/.cache", cache_ttl_hours: int = 24):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required. Install with: pip install playwright && playwright install chromium")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        
        self.browser: Optional[Browser] = None
        self.playwright = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def start(self):
        """Start the browser"""
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            logger.info("Playwright browser started")
    
    async def close(self):
        """Close the browser"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            logger.info("Playwright browser closed")
    
    def _get_cache_path(self, ticker: str) -> Path:
        """Get cache file path for a ticker"""
        return self.cache_dir / f"{ticker}.json"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is valid and not expired"""
        if not cache_path.exists():
            return False
        
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            
            cached_time = datetime.fromisoformat(data.get("timestamp", ""))
            return datetime.now() - cached_time < self.cache_ttl
        except Exception as e:
            logger.warning(f"Cache validation error: {e}")
            return False
    
    def _load_from_cache(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Load data from cache if valid"""
        cache_path = self._get_cache_path(ticker)
        
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
                logger.info(f"Loaded {ticker} from cache")
                return data.get("data")
            except Exception as e:
                logger.warning(f"Cache read error for {ticker}: {e}")
        
        return None
    
    def _save_to_cache(self, ticker: str, data: Dict[str, Any]):
        """Save data to cache"""
        cache_path = self._get_cache_path(ticker)
        
        try:
            cache_data = {
                "ticker": ticker,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            with open(cache_path, "w") as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"Saved {ticker} to cache")
        except Exception as e:
            logger.error(f"Cache write error for {ticker}: {e}")
    
    async def _extract_number(self, page: Page, selector: str, default: Optional[float] = None) -> Optional[float]:
        """Extract a number from a page element"""
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                # Clean the text: remove commas, %, Cr, etc.
                cleaned = re.sub(r'[^\d.+-]', '', text)
                if cleaned:
                    return float(cleaned)
        except Exception as e:
            logger.debug(f"Failed to extract number from {selector}: {e}")
        
        return default
    
    async def _extract_text(self, page: Page, selector: str, default: str = "") -> str:
        """Extract text from a page element"""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.inner_text()
        except Exception as e:
            logger.debug(f"Failed to extract text from {selector}: {e}")
        
        return default
    
    async def get_company_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch company data from Screener.in
        
        Args:
            ticker: Stock ticker (e.g., "HDFCBANK.NS")
            
        Returns:
            Dictionary with financial data
        """
        # Check cache first
        cached = self._load_from_cache(ticker)
        if cached:
            return cached
        
        # Ensure browser is started
        if not self.browser:
            await self.start()
        
        # Get Screener.in company ID
        screener_id = get_screener_id(ticker)
        if not screener_id:
            logger.error(f"No Screener ID found for {ticker}")
            return {}
        
        url = f"https://www.screener.in/company/{screener_id}/"
        logger.info(f"Scraping {ticker} from {url}")
        
        try:
            page = await self.browser.new_page()
            
            # Navigate to page
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for key elements
            await page.wait_for_selector("#top-ratios", timeout=10000)
            
            # Extract data
            data = await self._scrape_page_data(page, ticker)
            
            await page.close()
            
            # Cache the data
            self._save_to_cache(ticker, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to scrape {ticker}: {e}")
            return {}
    
    async def _scrape_page_data(self, page: Page, ticker: str) -> Dict[str, Any]:
        """Scrape all financial data from a Screener.in page"""
        data = {}
        
        try:
            # Top ratios section
            data["market_cap"] = await self._extract_market_cap(page)
            data["current_price"] = await self._extract_current_price(page)
            data["pe_ratio"] = await self._extract_ratio(page, "Stock P/E")
            data["pb_ratio"] = await self._extract_ratio(page, "Price to Book")
            
            # Company ratios section
            data["roe"] = await self._extract_ratio(page, "ROE")
            data["roce"] = await self._extract_ratio(page, "ROCE")
            data["debt_to_equity"] = await self._extract_ratio(page, "Debt to equity")
            data["operating_margin"] = await self._extract_ratio(page, "OPM")
            data["net_margin"] = await self._extract_ratio(page, "Net profit margin")
            data["interest_coverage"] = await self._extract_ratio(page, "Interest Coverage")
            
            # Quarterly results - latest
            data["revenue"] = await self._extract_latest_quarterly(page, "Sales")
            data["net_profit"] = await self._extract_latest_quarterly(page, "Net Profit")
            data["ebitda"] = await self._extract_latest_quarterly(page, "Operating Profit")
            
            # Balance sheet
            data["total_debt"] = await self._extract_balance_sheet_item(page, "Borrowings")
            data["equity"] = await self._extract_balance_sheet_item(page, "Reserves")
            
            logger.info(f"Successfully scraped {len([v for v in data.values() if v is not None])} fields for {ticker}")
            
        except Exception as e:
            logger.error(f"Error scraping page data for {ticker}: {e}")
        
        return data
    
    async def _extract_market_cap(self, page: Page) -> Optional[float]:
        """Extract market cap from top ratios"""
        try:
            # Market cap is typically in the first ratio
            selector = "#top-ratios li:first-child .number"
            text = await self._extract_text(page, selector)
            
            # Parse market cap (e.g., "12,34,567 Cr." -> 1234567000000)
            match = re.search(r'([\d,]+)\s*Cr', text)
            if match:
                value = float(match.group(1).replace(',', ''))
                return value * 1e7  # Convert Crores to actual value
        except Exception as e:
            logger.debug(f"Failed to extract market cap: {e}")
        
        return None
    
    async def _extract_current_price(self, page: Page) -> Optional[float]:
        """Extract current stock price"""
        try:
            selector = "#top-ratios li:nth-child(2) .number"
            return await self._extract_number(page, selector)
        except Exception as e:
            logger.debug(f"Failed to extract current price: {e}")
        
        return None
    
    async def _extract_ratio(self, page: Page, ratio_name: str) -> Optional[float]:
        """Extract a specific ratio by name"""
        try:
            # Find the row containing the ratio name
            rows = await page.query_selector_all(".company-ratios li")
            
            for row in rows:
                text = await row.inner_text()
                if ratio_name.lower() in text.lower():
                    # Extract the number from this row
                    number_elem = await row.query_selector(".number")
                    if number_elem:
                        num_text = await number_elem.inner_text()
                        # Clean and parse
                        cleaned = re.sub(r'[^\d.+-]', '', num_text)
                        if cleaned:
                            return float(cleaned)
        except Exception as e:
            logger.debug(f"Failed to extract ratio {ratio_name}: {e}")
        
        return None
    
    async def _extract_latest_quarterly(self, page: Page, item_name: str) -> Optional[float]:
        """Extract latest quarterly value for an item"""
        try:
            # Find the quarterly results table
            tables = await page.query_selector_all("table")
            
            for table in tables:
                header_text = await table.inner_text()
                if "Quarterly Results" in header_text:
                    # Find the row with item_name
                    rows = await table.query_selector_all("tr")
                    for row in rows:
                        row_text = await row.inner_text()
                        if item_name in row_text:
                            # Get the latest value (usually second cell)
                            cells = await row.query_selector_all("td")
                            if len(cells) >= 2:
                                cell_text = await cells[1].inner_text()
                                cleaned = re.sub(r'[^\d.+-]', '', cell_text)
                                if cleaned:
                                    return float(cleaned)
        except Exception as e:
            logger.debug(f"Failed to extract quarterly {item_name}: {e}")
        
        return None
    
    async def _extract_balance_sheet_item(self, page: Page, item_name: str) -> Optional[float]:
        """Extract a balance sheet item"""
        try:
            # Find the balance sheet table
            tables = await page.query_selector_all("table")
            
            for table in tables:
                header_text = await table.inner_text()
                if "Balance Sheet" in header_text:
                    rows = await table.query_selector_all("tr")
                    for row in rows:
                        row_text = await row.inner_text()
                        if item_name in row_text:
                            cells = await row.query_selector_all("td")
                            if len(cells) >= 2:
                                cell_text = await cells[-1].inner_text()  # Latest value
                                cleaned = re.sub(r'[^\d.+-]', '', cell_text)
                                if cleaned:
                                    return float(cleaned)
        except Exception as e:
            logger.debug(f"Failed to extract balance sheet {item_name}: {e}")
        
        return None


async def main():
    """Test the scraper"""
    logging.basicConfig(level=logging.INFO)
    
    async with ScreenerScraper() as scraper:
        data = await scraper.get_company_data("HDFCBANK.NS")
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    asyncio.run(main())


