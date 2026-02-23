from __future__ import annotations

from typing import Any, Dict, List

import httpx


async def search_finance_videos(
    query: str, api_key: str | None = None, max_results: int = 5
) -> List[Dict[str, Any]]:
    """Search YouTube for finance videos. Falls back to search URLs if no API key."""
    if not query:
        return []

    sq = query.replace(" ", "+")

    def _fallback(suffix: str, label: str) -> Dict[str, Any]:
        return {"title": f"{query} - {label}", "channel": "YouTube Search",
                "url": f"https://www.youtube.com/results?search_query={sq}+{suffix}", "views": None}

    if not api_key:
        return [_fallback("financial+analysis", "Financial Analysis"),
                _fallback("stock+research", "Stock Research"),
                _fallback("investment+review", "Investment Review")][:max_results]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={"part": "snippet", "q": query, "type": "video",
                        "maxResults": str(max(1, min(max_results, 10))),
                        "safeSearch": "none", "order": "relevance", "key": api_key}
            )
            resp.raise_for_status()
            results = [
                {"title": it.get("snippet", {}).get("title") or query,
                 "channel": it.get("snippet", {}).get("channelTitle") or "Unknown",
                 "url": f"https://www.youtube.com/watch?v={it.get('id', {}).get('videoId')}",
                 "views": None}
                for it in resp.json().get("items", [])
                if isinstance(it.get("id"), dict) and it["id"].get("videoId")
            ]
            return results or [_fallback("financial+overview", "Financial Overview")]
    except Exception:
        return [_fallback("market+analysis", "Market Analysis")]
