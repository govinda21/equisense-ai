from __future__ import annotations

from typing import List

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.nlp import sentiment_score, summarize_texts
from app.tools.news import get_news_headlines_and_summaries, get_recent_news_summary


async def news_sentiment_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0] if state["tickers"] else ""
    
    try:
        # Fetch real news headlines and content
        headlines, combined_text = await get_news_headlines_and_summaries(ticker, max_articles=5)
        
        # Get structured news summary for detailed analysis
        news_data = await get_recent_news_summary(ticker)
        
        # Analyze sentiment of real news content
        texts = headlines if headlines else [f"Limited news coverage for {ticker}"]
        summary = await summarize_texts(texts) if texts else f"No recent news available for {ticker}"
        sent = await sentiment_score(texts) if texts else 0.5
        
        # Enhanced confidence based on actual news availability
        confidence = 0.8 if len(headlines) >= 3 else 0.6 if len(headlines) >= 1 else 0.3
        
        # Store both summary and detailed news data
        state.setdefault("analysis", {})["news_sentiment"] = {
            "summary": summary,
            "score": sent,
            "headlines": headlines[:3],  # Top 3 headlines for display
            "article_count": news_data.get("article_count", 0),
            "latest_date": news_data.get("latest_date"),
            "sources": news_data.get("sources", []),
            "raw_articles": news_data.get("articles", [])  # For detailed view
        }
        
        state.setdefault("confidences", {})["news_sentiment"] = confidence
        
    except Exception as e:
        # Fallback to neutral analysis if news fetching fails
        fallback_summary = f"Unable to fetch current news for {ticker}. Analysis based on limited data."
        state.setdefault("analysis", {})["news_sentiment"] = {
            "summary": fallback_summary,
            "score": 0.5,
            "headlines": [],
            "article_count": 0,
            "latest_date": None,
            "sources": [],
            "error": str(e)
        }
        state.setdefault("confidences", {})["news_sentiment"] = 0.2
    
    return state
