"""
Multi-source financial news fetcher.
Priority: Yahoo Finance → Indian RSS feeds (.NS tickers) → Google News RSS.
All sources are de-duplicated and filtered for ticker relevance.
"""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
import yfinance as yf

from app.utils.retry import retry_async

logger = logging.getLogger(__name__)

# Company-name keywords per ticker for relevance filtering
_TICKER_KEYWORDS: Dict[str, List[str]] = {
    "AAPL": ["apple", "iphone", "ipad", "mac", "tim cook"],
    "MSFT": ["microsoft", "windows", "azure", "office", "satya nadella"],
    "GOOGL": ["google", "alphabet", "android", "youtube", "pichai"],
    "AMZN": ["amazon", "aws", "prime", "bezos", "andy jassy"],
    "TSLA": ["tesla", "elon musk", "electric vehicle", "model"],
    "META": ["meta", "facebook", "instagram", "whatsapp", "zuckerberg"],
    "NVDA": ["nvidia", "gpu", "jensen huang", "graphics"],
    "NFLX": ["netflix", "streaming"],
    "RELIANCE": ["reliance", "jio", "mukesh ambani"],
}
_MAJOR_TICKERS = {"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX"}
_INCLUSIVE_TERMS = ["growth stocks", "tech stocks", "magnificent seven", "big tech",
                    "mega cap", "faang", "market leaders", "blue chip"]


# ---------- individual source fetchers ----------

@retry_async(max_retries=2, base_delay=0.5, exceptions=(Exception,))
async def _yf_news(ticker: str, max_articles: int) -> List[Dict]:
    def _fetch():
        stock = yf.Ticker(ticker)
        out = []
        for art in (getattr(stock, "news", []) or [])[:max_articles]:
            if isinstance(art, dict) and "content" in art:
                c = art["content"]
                out.append({
                    "title":               c.get("title", ""),
                    "summary":             c.get("summary", c.get("description", "")),
                    "link":                c.get("canonicalUrl", {}).get("url", ""),
                    "publisher":           c.get("provider", {}).get("displayName", "Yahoo Finance"),
                    "providerPublishTime": c.get("pubDate", ""),
                })
        return out

    return await asyncio.to_thread(_fetch)


async def _rss_news(url: str, source_label: str, max_items: int = 3) -> List[Dict]:
    """Generic RSS parser returning article dicts."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return []
        root = ET.fromstring(r.content)
        arts = []
        for item in root.findall(".//item")[:max_items]:
            t = item.findtext("title", "")
            if t:
                arts.append({
                    "title":               t,
                    "summary":             item.findtext("description", ""),
                    "link":                item.findtext("link", ""),
                    "publisher":           source_label,
                    "providerPublishTime": item.findtext("pubDate", ""),
                })
        return arts
    except Exception as e:
        logger.debug(f"RSS fetch failed ({url}): {e}")
        return []


async def _google_news(ticker: str) -> List[Dict]:
    base = ticker.split(".")[0]
    return await _rss_news(
        f"https://news.google.com/rss/search?q={base}+stock&hl=en-US&gl=US&ceid=US:en",
        "Google News",
    )


async def _indian_news(ticker: str) -> List[Dict]:
    if not ticker.endswith(".NS"):
        return []
    base = ticker.replace(".NS", "")
    arts = []
    for url, label in [
        ("https://economictimes.indiatimes.com/markets/stocks/rss", "Economic Times"),
        ("https://www.moneycontrol.com/rss/latestnews.xml",         "MoneyControl"),
    ]:
        for a in await _rss_news(url, label, max_items=2):
            text = f"{a['title']} {a['summary']}".lower()
            if any(kw in text for kw in [base.lower(), "stock", "share", "market"]):
                arts.append(a)
    return arts


# ---------- de-duplicate & relevance filter ----------

def _deduplicate(articles: List[Dict]) -> List[Dict]:
    seen, unique = set(), []
    for a in articles:
        title = a.get("title", "").lower().strip()
        if not title or title in seen:
            continue
        title_words = set(title.split())
        if any(len(title_words & set(s.split())) / max(len(title_words), len(set(s.split()))) > 0.7 for s in seen):
            continue
        seen.add(title)
        unique.append(a)
    return unique


def _is_relevant(article: Dict, ticker: str) -> bool:
    base = ticker.split(".")[0].upper()
    text = f"{article.get('title','')} {article.get('summary','')}".lower()
    keywords = _TICKER_KEYWORDS.get(base, []) + [base.lower()]
    if any(kw in text for kw in keywords):
        return True
    if base in _MAJOR_TICKERS:
        return any(t in text for t in _INCLUSIVE_TERMS)
    return False


def _parse_ts(ts: Any) -> str:
    try:
        if isinstance(ts, int):
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(ts, str) and ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------- public API ----------

async def fetch_real_news(ticker: str, max_articles: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch, de-duplicate, and relevance-filter news for a ticker.
    Falls back progressively: Yahoo Finance → Indian RSS → Google News.
    """
    raw: List[Dict] = []

    try:
        raw += await _yf_news(ticker, max_articles)
    except Exception as e:
        logger.debug(f"YF news failed for {ticker}: {e}")

    if len(raw) < 3:
        if ticker.endswith(".NS"):
            raw += await _indian_news(ticker)
        if len(raw) < 2:
            raw += await _google_news(ticker)

    arts = _deduplicate(raw)
    standardized, skipped = [], 0
    for a in arts:
        s = {
            "title":        a.get("title", ""),
            "summary":      a.get("summary", ""),
            "url":          a.get("link", ""),
            "source":       a.get("publisher", "Yahoo Finance"),
            "published_at": _parse_ts(a.get("providerPublishTime")),
            "raw":          a,
        }
        if len(s["title"]) > 10 and _is_relevant(s, ticker):
            standardized.append(s)
        else:
            skipped += 1

    logger.info(f"News for {ticker}: {len(standardized)} relevant, {skipped} filtered")
    return standardized[:max_articles]


async def get_news_headlines_and_summaries(ticker: str, max_articles: int = 5
                                           ) -> Tuple[List[str], str]:
    """Return (headlines, combined_summary_text) for sentiment analysis."""
    articles = await fetch_real_news(ticker, max_articles)
    if not articles:
        fallback = f"Limited news coverage available for {ticker}."
        return [fallback], fallback

    headlines = [a["title"] for a in articles if a["title"]]
    summaries = [a["summary"][:500] + ("..." if len(a["summary"]) > 500 else "")
                 for a in articles if a["summary"]]
    combined  = " ".join(summaries or headlines)
    return headlines, combined


async def get_recent_news_summary(ticker: str) -> Dict[str, Any]:
    """Return structured recent-news metadata."""
    articles = await fetch_real_news(ticker)
    if not articles:
        return {"summary": f"No recent news for {ticker}", "article_count": 0,
                "latest_date": None, "sources": [], "articles": []}

    headlines = [a["title"] for a in articles if a["title"]]
    summary   = f"Recent news for {ticker}: " + "; ".join(headlines[:3])
    if len(headlines) > 3:
        summary += f" and {len(headlines)-3} more"

    return {
        "summary":       summary,
        "article_count": len(articles),
        "latest_date":   articles[0]["published_at"] if articles else None,
        "sources":       list({a["source"] for a in articles}),
        "articles":      articles[:3],
    }
