from __future__ import annotations

from typing import List

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.nlp import sentiment_score, summarize_texts, _ollama_chat
from app.tools.news import get_news_headlines_and_summaries, get_recent_news_summary
import asyncio
import logging

logger = logging.getLogger(__name__)


async def analyze_headline_sentiment(headline: str, ticker: str) -> tuple[str, str, str]:
    """
    Analyze individual headline sentiment with professional classification.
    Returns: (sentiment_label, rationale, confidence)
    """
    try:
        prompt = f"""Analyze this financial headline for {ticker} and provide:
1. Sentiment classification: Positive, Negative, or Neutral
2. One-line professional rationale (max 8 words)

Headline: "{headline}"

Format your response as:
SENTIMENT: [Positive/Negative/Neutral]
RATIONALE: [brief professional explanation]

Example:
SENTIMENT: Positive
RATIONALE: Strong earnings growth reported"""

        response = await asyncio.to_thread(_ollama_chat, prompt)
        
        if response:
            # Parse response
            lines = response.strip().split('\n')
            sentiment = "Neutral"
            rationale = "market analysis pending"
            
            for line in lines:
                if line.startswith("SENTIMENT:"):
                    sentiment = line.replace("SENTIMENT:", "").strip()
                elif line.startswith("RATIONALE:"):
                    rationale = line.replace("RATIONALE:", "").strip()
            
            # Ensure valid sentiment
            if sentiment not in ["Positive", "Negative", "Neutral"]:
                sentiment = "Neutral"
            
            return sentiment, rationale, "High"
        
    except Exception as e:
        logger.debug(f"LLM headline analysis failed: {e}")
    
    # Fallback analysis
    headline_lower = headline.lower()
    if any(word in headline_lower for word in ['strong', 'growth', 'beat', 'exceed', 'bull', 'positive', 'gain', 'rise']):
        return "Positive", "positive market indicators", "Medium"
    elif any(word in headline_lower for word in ['weak', 'fall', 'drop', 'concern', 'bear', 'negative', 'decline']):
        return "Negative", "negative market indicators", "Medium"
    else:
        return "Neutral", "market analysis pending", "Low"


def get_professional_sentiment_label(score: float, confidence: float) -> str:
    """
    Convert numerical sentiment score to professional financial terminology.
    """
    conf_pct = int(confidence * 100)
    
    if score >= 0.75:
        return f"Strongly Bullish ({conf_pct}% Confidence)"
    elif score >= 0.65:
        return f"Moderately Positive ({conf_pct}% Confidence)"
    elif score >= 0.55:
        return f"Neutral with Upward Bias ({conf_pct}% Confidence)"
    elif score >= 0.45:
        return f"Neutral ({conf_pct}% Confidence)"
    elif score >= 0.35:
        return f"Neutral with Downward Bias ({conf_pct}% Confidence)"
    elif score >= 0.25:
        return f"Moderately Bearish ({conf_pct}% Confidence)"
    else:
        return f"Strongly Bearish ({conf_pct}% Confidence)"


async def news_sentiment_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0] if state["tickers"] else ""
    
    try:
        # Fetch real news headlines and content
        headlines, combined_text = await get_news_headlines_and_summaries(ticker, max_articles=5)
        
        # Get structured news summary for detailed analysis
        news_data = await get_recent_news_summary(ticker)
        
        # Analyze overall sentiment
        texts = headlines if headlines else [f"Limited news coverage for {ticker}"]
        sent = await sentiment_score(texts) if texts else 0.5
        
        # Enhanced confidence based on actual news availability and data quality
        base_confidence = 0.85 if len(headlines) >= 3 else 0.7 if len(headlines) >= 1 else 0.4
        
        # Analyze individual headlines with professional classification
        headline_analyses = []
        if headlines:
            for headline in headlines[:3]:  # Analyze top 3 headlines
                sentiment_label, rationale, conf_level = await analyze_headline_sentiment(headline, ticker)
                headline_analyses.append({
                    "headline": headline,
                    "sentiment": sentiment_label,
                    "rationale": rationale,
                    "confidence": conf_level
                })
        
        # Create professional sentiment summary
        professional_sentiment = get_professional_sentiment_label(sent, base_confidence)
        
        # Format professional news summary
        if headlines:
            professional_summary = f"**Overall Sentiment:** {professional_sentiment}\n**News Headlines:**\n"
            for analysis in headline_analyses:
                professional_summary += f"• {analysis['headline']} — {analysis['sentiment']}; {analysis['rationale']}.\n"
        else:
            professional_summary = f"**Overall Sentiment:** {professional_sentiment}\n**News Coverage:** Limited news coverage available for {ticker} at this time."
        
        # Store both professional and legacy formats
        state.setdefault("analysis", {})["news_sentiment"] = {
            "summary": professional_summary,
            "professional_sentiment": professional_sentiment,
            "score": sent,
            "headlines": headlines[:3],
            "headline_analyses": headline_analyses,
            "article_count": news_data.get("article_count", 0),
            "latest_date": news_data.get("latest_date"),
            "sources": news_data.get("sources", []),
            "raw_articles": news_data.get("articles", [])
        }
        
        state.setdefault("confidences", {})["news_sentiment"] = base_confidence
        
    except Exception as e:
        # Fallback to professional neutral analysis if news fetching fails
        fallback_professional = get_professional_sentiment_label(0.5, 0.3)
        fallback_summary = f"**Overall Sentiment:** {fallback_professional}\n**News Coverage:** Unable to fetch current news for {ticker}. Analysis based on limited data."
        
        state.setdefault("analysis", {})["news_sentiment"] = {
            "summary": fallback_summary,
            "professional_sentiment": fallback_professional,
            "score": 0.5,
            "headlines": [],
            "headline_analyses": [],
            "article_count": 0,
            "latest_date": None,
            "sources": [],
            "error": str(e)
        }
        state.setdefault("confidences", {})["news_sentiment"] = 0.3
    
    return state
