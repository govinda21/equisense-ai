from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.youtube import search_finance_videos
from app.tools.nlp import summarize_texts, sentiment_score


async def youtube_analysis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state['tickers'][0] if state["tickers"] else ""
    
    # Only search for videos if we have a real YouTube API key
    if settings.youtube_api_key and settings.youtube_api_key.strip():
        vids = await search_finance_videos(f"{ticker} stock analysis", api_key=settings.youtube_api_key)
        titles = [v["title"] for v in vids]
        
        if titles:
            summary = await summarize_texts(titles)
            sent = await sentiment_score(titles)
            confidence = 0.75
        else:
            summary = f"No recent YouTube videos found for {ticker} analysis."
            sent = 0.5
            confidence = 0.2
    else:
        # No API key - provide a neutral message instead of fake content
        vids = []
        summary = f"YouTube analysis requires API key configuration. Search manually: https://www.youtube.com/results?search_query={ticker.replace('.', '')}+stock+analysis"
        sent = 0.5
        confidence = 0.1
    
    state.setdefault("analysis", {})["youtube"] = {"videos": vids, "summary": summary, "score": sent}
    state.setdefault("confidences", {})["youtube"] = confidence
    return state
