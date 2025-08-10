from __future__ import annotations

from typing import Any, Dict, List

import httpx


async def search_finance_videos(
    query: str, api_key: str | None = None, max_results: int = 5
) -> List[Dict[str, Any]]:
    """
    Search YouTube for finance videos related to the query.

    - If api_key is provided, uses YouTube Data API v3
    - Otherwise, returns a small, deterministic fallback list
    """
    if not query:
        return []

    # Fallback if no API key configured - return real search URLs instead of dummy data
    if not api_key:
        search_query = query.replace(" ", "+")
        return [
            {
                "title": f"{query} - Financial Analysis",
                "channel": "YouTube Search",
                "url": f"https://www.youtube.com/results?search_query={search_query}+financial+analysis",
                "views": None,
            },
            {
                "title": f"{query} - Stock Research",
                "channel": "YouTube Search", 
                "url": f"https://www.youtube.com/results?search_query={search_query}+stock+research",
                "views": None,
            },
            {
                "title": f"{query} - Investment Review",
                "channel": "YouTube Search",
                "url": f"https://www.youtube.com/results?search_query={search_query}+investment+review",
                "views": None,
            }
        ][:max_results]

    try:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": str(max(1, min(max_results, 10))),
            "safeSearch": "none",
            "order": "relevance",
            "key": api_key,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search", params=params
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            results: List[Dict[str, Any]] = []
            for it in items:
                video_id = (
                    it.get("id", {}).get("videoId")
                    if isinstance(it.get("id"), dict)
                    else None
                )
                snippet = it.get("snippet", {})
                title = snippet.get("title") or query
                channel = snippet.get("channelTitle") or "Unknown"
                url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
                if not url:
                    continue
                results.append(
                    {
                        "title": title,
                        "channel": channel,
                        "url": url,
                        # View counts require an extra API call; omit to keep quota minimal
                        "views": None,
                    }
                )
            # Fallback if API returned nothing - use real search URLs
            if not results:
                search_query = query.replace(" ", "+")
                return [
                    {
                        "title": f"{query} - Financial Overview",
                        "channel": "YouTube Search",
                        "url": f"https://www.youtube.com/results?search_query={search_query}+financial+overview",
                        "views": None,
                    }
                ]
            return results
    except Exception:
        # Network/quota errors → safe fallback with real search URLs
        search_query = query.replace(" ", "+")
        return [
            {
                "title": f"{query} - Market Analysis",
                "channel": "YouTube Search",
                "url": f"https://www.youtube.com/results?search_query={search_query}+market+analysis",
                "views": None,
            }
        ]
