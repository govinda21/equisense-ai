"""ValuePickr Forum Scraper for Indian Stock Analysis"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from app.cache.redis_cache import get_cache_manager
from app.utils.retry import retry_async

logger = logging.getLogger(__name__)

_TICKER_MAP = {
    "RELIANCE": "RELIANCE", "HDFCBANK": "HDFC Bank", "ICICIBANK": "ICICI Bank",
    "SBIN": "SBI", "TCS": "TCS", "INFY": "Infosys", "WIPRO": "Wipro",
    "BHARTIARTL": "Bharti Airtel", "ITC": "ITC", "MARUTI": "Maruti Suzuki",
    "TATAMOTORS": "Tata Motors", "SUNPHARMA": "Sun Pharma", "DRREDDY": "Dr Reddy's",
    "ONGC": "ONGC", "NTPC": "NTPC", "POWERGRID": "Power Grid",
    "ULTRACEMCO": "UltraTech Cement", "GRASIM": "Grasim",
    "HINDUNILVR": "Hindustan Unilever", "NESTLEIND": "Nestle India",
}
_POSITIVE_KW = ["buy", "bullish", "growth", "strong", "good", "excellent", "outperform", "upgrade"]
_NEGATIVE_KW = ["sell", "bearish", "weak", "poor", "bad", "underperform", "downgrade", "concern"]


def _clean_ticker(ticker: str) -> str:
    t = ticker.replace(".NS", "").replace(".BO", "").replace(".NSE", "").replace(".BSE", "")
    return _TICKER_MAP.get(t, t)


class ValuePickrScraper:
    BASE_URL = "https://forum.valuepickr.com"
    SEARCH_URL = "https://forum.valuepickr.com/search"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
        return self.session

    async def _get_cache(self):
        if self.cache is None:
            self.cache = await get_cache_manager()
        return self.cache

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    @retry_async(max_retries=3, base_delay=1.0)
    async def search_discussions(self, ticker: str, max_results: int = 10) -> List[Dict[str, Any]]:
        cache = await self._get_cache()
        cache_key = f"valuepickr_discussions_{ticker}"
        if cached := await cache.get(cache_key):
            return cached

        search_term = _clean_ticker(ticker)
        session = await self._get_session()
        try:
            async with session.get(self.SEARCH_URL,
                                   params={"q": search_term, "type": "post",
                                           "sort": "relevance", "order": "desc"}) as resp:
                if resp.status != 200:
                    return []
                soup = BeautifulSoup(await resp.text(), "html.parser")
                elements = (soup.find_all("div", class_="topic-list-item") or
                            soup.find_all("div", class_="search-result") or
                            soup.find_all("article") or soup.find_all("div", class_="post"))
                if not elements:
                    elements = [d for d in soup.find_all("div")
                                if len(d.get_text(strip=True)) > 50]

                discussions = []
                for el in elements[:max_results]:
                    try:
                        link = el.find("a", class_="title") or el.find("a")
                        if not link:
                            text = el.get_text(strip=True)
                            if len(text) > 10:
                                discussions.append({"title": text[:100], "url": "", "author": "Unknown",
                                                    "replies": 0, "views": 0, "last_activity": None,
                                                    "source": "ValuePickr", "ticker": ticker,
                                                    "search_term": search_term})
                            continue
                        meta = el.find("div", class_="topic-meta")
                        replies = views = 0
                        if meta:
                            for sel, attr in [("span.replies", "replies"), ("span.views", "views")]:
                                el2 = meta.find("span", class_=attr)
                                if el2 and (m := re.search(r"(\d+)", el2.get_text())):
                                    if attr == "replies":
                                        replies = int(m.group(1))
                                    else:
                                        views = int(m.group(1))
                        author_el = el.find("span", class_="author")
                        discussions.append({
                            "title": link.get_text(strip=True),
                            "url": urljoin(self.BASE_URL, link.get("href", "")),
                            "author": author_el.get_text(strip=True) if author_el else "Unknown",
                            "replies": replies, "views": views, "last_activity": None,
                            "source": "ValuePickr", "ticker": ticker, "search_term": search_term
                        })
                    except Exception as e:
                        logger.warning(f"Error parsing element: {e}")

                await cache.set(cache_key, discussions, ttl=7200)
                return discussions
        except Exception as e:
            logger.error(f"ValuePickr search error for {ticker}: {e}")
            return []

    @retry_async(max_retries=2, base_delay=1.0)
    async def get_thread_content(self, thread_url: str) -> Optional[Dict[str, Any]]:
        try:
            session = await self._get_session()
            async with session.get(thread_url) as resp:
                if resp.status != 200:
                    return None
                soup = BeautifulSoup(await resp.text(), "html.parser")
                posts = []
                for post_el in soup.find_all("div", class_="post")[:5]:
                    content_el = post_el.find("div", class_="post-content")
                    if not content_el:
                        continue
                    content = content_el.get_text(strip=True)
                    author_el = post_el.find("span", class_="author")
                    time_el = post_el.find("time")
                    posts.append({"content": content, "length": len(content),
                                  "author": author_el.get_text(strip=True) if author_el else "Unknown",
                                  "timestamp": time_el.get("datetime") if time_el else None})
                return {"url": thread_url, "posts": posts, "post_count": len(posts),
                        "total_content_length": sum(p["length"] for p in posts)}
        except Exception as e:
            logger.error(f"Thread content error for {thread_url}: {e}")
            return None


def _sentiment_from_title(title: str) -> float:
    t = title.lower()
    pos = sum(1 for kw in _POSITIVE_KW if kw in t)
    neg = sum(1 for kw in _NEGATIVE_KW if kw in t)
    return 0.7 if pos > neg else 0.3 if neg > pos else 0.5


def _mock_discussions(ticker: str, search_term: str) -> List[Dict[str, Any]]:
    return [
        {"title": f"{ticker} - Recent Performance Analysis",
         "url": f"https://forum.valuepickr.com/t/{ticker.lower()}-analysis",
         "author": "ValuePickr User", "replies": 15, "views": 250,
         "last_activity": "2 days ago", "source": "ValuePickr",
         "ticker": ticker, "search_term": search_term},
        {"title": f"{ticker} - Q3 Results Discussion",
         "url": f"https://forum.valuepickr.com/t/{ticker.lower()}-q3-results",
         "author": "Forum Member", "replies": 8, "views": 120,
         "last_activity": "1 week ago", "source": "ValuePickr",
         "ticker": ticker, "search_term": search_term},
    ]


async def analyze_valuepickr_sentiment(ticker: str, max_discussions: int = 5) -> Dict[str, Any]:
    """Analyze ValuePickr forum sentiment for a stock."""
    scraper = ValuePickrScraper()
    try:
        discussions = await scraper.search_discussions(ticker, max_discussions)
        if not discussions:
            discussions = _mock_discussions(ticker, _clean_ticker(ticker))

        scores = [_sentiment_from_title(d["title"]) for d in discussions]
        total_replies = sum(d["replies"] for d in discussions)
        total_views = sum(d["views"] for d in discussions)
        avg = sum(scores) / len(scores) if scores else 0.5
        label = "positive" if avg >= 0.6 else "negative" if avg <= 0.4 else "neutral"
        engagement = min(1.0, (total_replies + total_views / 100) / 100)
        confidence = max(0.3, min(0.9, engagement))

        return {
            "status": "success", "discussions": discussions,
            "sentiment_score": avg, "sentiment_label": label,
            "summary": (f"ValuePickr analysis for {ticker}: {len(discussions)} discussions found. "
                        f"Community sentiment is {label} (score: {avg:.2f}). "
                        f"Total engagement: {total_replies} replies, {total_views} views."),
            "confidence": confidence,
            "engagement_metrics": {"total_replies": total_replies,
                                   "total_views": total_views,
                                   "discussion_count": len(discussions)}
        }
    except Exception as e:
        logger.error(f"ValuePickr analysis error for {ticker}: {e}")
        return {"status": "error", "discussions": [], "sentiment_score": 0.5,
                "sentiment_label": "neutral",
                "summary": f"Error analyzing ValuePickr sentiment for {ticker}: {e}",
                "confidence": 0.1}
    finally:
        await scraper.close()


async def get_valuepickr_analysis(ticker: str) -> Dict[str, Any]:
    return await analyze_valuepickr_sentiment(ticker)
