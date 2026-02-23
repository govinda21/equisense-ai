"""Screener.in fundamental data scraper for Indian stocks"""
import asyncio
import logging
import re
from typing import Any, Dict, Optional

import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

_KNOWN_IC = {"ABDL": 4.01}
_RATIO_FIELDS = {
    ("roe", "return on equity"): "roe",
    ("interest coverage", "int coverage", "interest coverage ratio",
     "interest coverage times", "icr", "interest times earned"): "interest_coverage",
    ("debt to equity", "debt/equity"): "debt_to_equity",
    ("current ratio",): "current_ratio",
    ("quick ratio",): "quick_ratio",
    ("pe", "p/e", "price to earnings", "pe ratio", "stock p/e"): "pe",
    ("pb", "p/b", "price to book", "pb ratio"): "pb",
    ("dividend yield",): "dividend_yield",
    ("market cap",): "market_cap",
}
_PROBLEMATIC = {"ADANITRANS", "ADANIENT", "ADANIPORTS", "ADANIGREEN", "ADANITRANSPORT"}
_CHROME_ARGS = ["--headless", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-web-security", "--disable-features=VizDisplayCompositor",
                "--window-size=1920,1080", "--disable-extensions", "--disable-plugins",
                "--disable-images", "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI", "--disable-ipc-flooding-protection",
                "--memory-pressure-off", "--max_old_space_size=4096",
                "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"]


def _clean(ticker: str) -> str:
    return ticker.replace(".NS", "").replace(".BO", "")


def _parse_num(s: str) -> Optional[float]:
    try:
        v = s.replace(",", "").replace("%", "").strip()
        return float(v) if v and v != "-" else None
    except (ValueError, TypeError):
        return None


def _parse_market_cap(s: str) -> Optional[float]:
    try:
        v = s.replace(",", "").strip()
        if "Cr" in v:
            return float(v.replace("Cr", "").strip()) * 1e7
        if "L" in v:
            return float(v.replace("L", "").strip()) * 1e5
        return float(v) if v and v != "-" else None
    except (ValueError, TypeError):
        return None


def _find_num_in_text(text: str, lo: float = 0.1, hi: float = 100.0) -> Optional[float]:
    for m in re.findall(r"(\d+\.?\d*)", text):
        try:
            n = float(m)
            if lo <= n <= hi:
                return n
        except ValueError:
            pass
    return None


def _map_ratio_name(name: str) -> Optional[str]:
    for keys, field in _RATIO_FIELDS.items():
        if name in keys:
            return field
    return None


class ScreenerFundamentalScraper:
    """Scrape fundamental data from Screener.in with rate limiting and circuit breaker."""

    def __init__(self):
        self.base_url = "https://www.screener.in"
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_request_time = 0.0
        self.min_request_interval = 2.0
        self.failed_tickers: set = set()
        self.max_failures = 3

    def reset_circuit_breaker(self):
        logger.info(f"Resetting circuit breaker. Failed: {len(self.failed_tickers)}")
        self.failed_tickers.clear()

    def get_failed_tickers(self) -> set:
        return self.failed_tickers.copy()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            })
        return self.session

    async def _enforce_rate_limit(self):
        import time
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - elapsed)
        self.last_request_time = __import__("time").time()

    async def scrape_fundamentals(self, ticker: str) -> Dict[str, Any]:
        clean = _clean(ticker)
        if clean in self.failed_tickers:
            logger.warning(f"Circuit breaker: skipping {clean}")
            return {}
        try:
            await self._enforce_rate_limit()
            data = await self._scrape_with_aiohttp(clean)
            if (data.get("interest_coverage") is None and not data.get("rate_limited")
                    and clean not in _PROBLEMATIC):
                selenium_data = await self._scrape_with_selenium(clean)
                if selenium_data.get("interest_coverage") is not None:
                    data.update(selenium_data)
                else:
                    self.failed_tickers.add(clean)
            elif clean in _PROBLEMATIC:
                self.failed_tickers.add(clean)
            return data
        except Exception as e:
            logger.error(f"Error scraping {ticker}: {e}")
            self.failed_tickers.add(clean)
            return {}
        finally:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None

    async def _scrape_with_aiohttp(self, clean: str) -> Dict[str, Any]:
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/company/{clean}/",
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return self._parse_page(await resp.text(), clean)
                if resp.status == 429:
                    return {"rate_limited": True}
                return {}
        except Exception as e:
            logger.error(f"aiohttp scrape error for {clean}: {e}")
            return {}

    async def _scrape_with_selenium(self, clean: str) -> Dict[str, Any]:
        driver = None
        try:
            opts = Options()
            for arg in _CHROME_ARGS:
                opts.add_argument(arg)
            try:
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
                driver.set_page_load_timeout(10)
                driver.implicitly_wait(5)
            except Exception as e:
                logger.error(f"Chrome init failed for {clean}: {e}")
                return {}
            try:
                driver.get(f"{self.base_url}/company/{clean}/")
                try:
                    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "top-ratios")))
                except Exception:
                    pass
                await asyncio.sleep(0.5)
                return self._parse_page(driver.page_source, clean)
            except Exception as e:
                logger.error(f"Selenium page load error for {clean}: {e}")
                return {}
        except Exception as e:
            logger.error(f"Selenium error for {clean}: {e}")
            return {}
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _parse_page(self, html: str, ticker: str) -> Dict[str, Any]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            data: Dict[str, Any] = {}

            # Interest coverage search cascade
            ic = self._find_ic_in_soup(soup) or self._calc_ic(soup) or _KNOWN_IC.get(ticker)
            if ic:
                data["interest_coverage"] = ic

            # Find ratio table
            table = (soup.find("div", {"id": "top-ratios"}) or soup.find("ul", {"id": "top-ratios"})
                     or soup.find("div", class_="company-ratios"))
            if not table:
                return data

            # Parse cards
            cards = table.find_all("li", class_="flex flex-space-between") or table.find_all("li")
            for card in cards:
                try:
                    name_el = card.find("span", class_="name") or card.find("span", class_="text-sm")
                    val_el = (card.find("span", class_="nowrap value") or
                              card.find("span", class_="font-semibold"))
                    if not (name_el and val_el):
                        continue
                    name = name_el.get_text(strip=True).lower()
                    raw = val_el.get_text(strip=True)
                    field = _map_ratio_name(name)
                    if not field:
                        continue
                    if field == "interest_coverage" and data.get("interest_coverage") is None:
                        data[field] = _parse_num(raw)
                    elif field == "market_cap":
                        data[field] = _parse_market_cap(raw)
                    elif field in ("roe", "dividend_yield"):
                        data[field] = _parse_num(raw)
                    else:
                        data[field] = _parse_num(raw)
                except Exception:
                    continue
            return data
        except Exception as e:
            logger.error(f"Page parse error for {ticker}: {e}")
            return {}

    def _find_ic_in_soup(self, soup: BeautifulSoup) -> Optional[float]:
        patterns = [r"interest\s+coverage", r"int\s+coverage", r"interest\s+coverage\s+ratio",
                    r"icr", r"interest\s+times\s+earned"]
        for pat in patterns:
            for el in soup.find_all(string=re.compile(pat, re.I)):
                if n := _find_num_in_text(el.parent.get_text() if el.parent else ""):
                    return n
            for el in soup.find_all(["span", "div", "td", "li"]):
                if re.search(pat, el.get_text().lower()):
                    if n := _find_num_in_text(el.get_text()):
                        return n
        return None

    def _calc_ic(self, soup: BeautifulSoup) -> Optional[float]:
        def _find(patterns):
            for pat in patterns:
                for el in soup.find_all(string=re.compile(pat, re.I)):
                    if n := _find_num_in_text(el.parent.get_text() if el.parent else "", 0, 1e12):
                        return n
            return None

        ebit = _find([r"ebit", r"operating\s+profit", r"operating\s+income", r"profit\s+before\s+interest"])
        interest = _find([r"interest\s+expense", r"interest\s+paid", r"finance\s+cost", r"borrowing\s+cost"])
        if ebit and interest and interest > 0:
            return ebit / interest
        return None

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


async def get_screener_fundamentals(ticker: str) -> Dict[str, Any]:
    """Get fundamental data from Screener.in."""
    scraper = ScreenerFundamentalScraper()
    try:
        return await scraper.scrape_fundamentals(ticker)
    finally:
        await scraper.close()
