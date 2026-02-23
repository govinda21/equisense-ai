from __future__ import annotations

from typing import List

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.nlp import sentiment_score, summarize_texts, _ollama
from app.tools.news import get_news_headlines_and_summaries, get_recent_news_summary
from app.tools.valuepickr_scraper import analyze_valuepickr_sentiment
import asyncio
import logging

logger = logging.getLogger(__name__)


async def analyze_headline_sentiment(headline: str, ticker: str, published_at: str = None) -> tuple[str, str, str, str]:
    """
    Analyze individual headline sentiment with professional classification and date.
    Returns: (sentiment_label, rationale, confidence, formatted_date)
    """
    try:
        # Format date for display
        formatted_date = _format_news_date(published_at) if published_at else "Date unknown"
        
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

        response = await asyncio.to_thread(_ollama, prompt)
        
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
            
            return sentiment, rationale, "High", formatted_date
        
    except Exception as e:
        logger.debug(f"LLM headline analysis failed: {e}")
    
    # Fallback analysis
    headline_lower = headline.lower()
    if any(word in headline_lower for word in ['strong', 'growth', 'beat', 'exceed', 'bull', 'positive', 'gain', 'rise']):
        sentiment = "Positive"
        rationale = "positive market indicators"
    elif any(word in headline_lower for word in ['weak', 'fall', 'drop', 'concern', 'bear', 'negative', 'decline']):
        sentiment = "Negative"
        rationale = "negative market indicators"
    else:
        sentiment = "Neutral"
        rationale = "market analysis pending"
    
    formatted_date = _format_news_date(published_at) if published_at else "Date unknown"
    return sentiment, rationale, "Medium", formatted_date


def _format_news_date(published_at: str) -> str:
    """Format news date for display with freshness indicator"""
    if not published_at:
        return "Date unknown"
    
    try:
        from datetime import datetime, timezone
        
        # Parse the date string
        if isinstance(published_at, str):
            # Try different date formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                try:
                    pub_date = datetime.strptime(published_at, fmt)
                    break
                except ValueError:
                    continue
            else:
                return "Date unknown"
        else:
            pub_date = published_at
        
        # Calculate age
        now = datetime.now(timezone.utc)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        
        age_days = (now - pub_date).days
        
        # Format based on age
        if age_days == 0:
            return "Today"
        elif age_days == 1:
            return "Yesterday"
        elif age_days < 7:
            return f"{age_days} days ago"
        elif age_days < 30:
            weeks = age_days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''} ago"
        elif age_days < 365:
            months = age_days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            years = age_days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
            
    except Exception as e:
        logger.debug(f"Error formatting date {published_at}: {e}")
        return "Date unknown"


def calculate_news_freshness_score(published_at: str) -> float:
    """Calculate freshness score (0-1) based on news age"""
    if not published_at:
        return 0.3  # Low score for unknown dates
    
    try:
        from datetime import datetime, timezone
        
        # Parse the date string
        if isinstance(published_at, str):
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                try:
                    pub_date = datetime.strptime(published_at, fmt)
                    break
                except ValueError:
                    continue
            else:
                return 0.3
        else:
            pub_date = published_at
        
        # Calculate age in days
        now = datetime.now(timezone.utc)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        
        age_days = (now - pub_date).days
        
        # Freshness scoring:
        # 0-1 days: 1.0 (fresh)
        # 2-7 days: 0.8 (recent)
        # 8-30 days: 0.6 (recent)
        # 31-180 days: 0.4 (recent)
        # 181-365 days: 0.2 (old)
        # 365+ days: 0.1 (very old)
        
        if age_days <= 1:
            return 1.0
        elif age_days <= 7:
            return 0.8
        elif age_days <= 30:
            return 0.6
        elif age_days <= 180:  # 6 months
            return 0.4
        elif age_days <= 365:  # 1 year
            return 0.2
        else:
            return 0.1
            
    except Exception as e:
        logger.debug(f"Error calculating freshness for {published_at}: {e}")
        return 0.3


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
        
        # Fetch ValuePickr forum analysis for Indian stocks
        valuepickr_analysis = None
        if ticker.endswith('.NS') or ticker.endswith('.BO'):
            try:
                valuepickr_analysis = await analyze_valuepickr_sentiment(ticker, max_discussions=5)
                logger.info(f"ValuePickr analysis for {ticker}: {valuepickr_analysis.get('status', 'unknown')}")
            except Exception as e:
                logger.warning(f"ValuePickr analysis failed for {ticker}: {e}")
                valuepickr_analysis = {
                    'status': 'error',
                    'sentiment_score': 0.5,
                    'sentiment_label': 'neutral',
                    'summary': f'ValuePickr analysis unavailable for {ticker}',
                    'confidence': 0.1
                }
        
        # Analyze overall sentiment - combine news and ValuePickr sentiment
        texts = headlines if headlines else [f"Limited news coverage for {ticker}"]
        news_sentiment = await sentiment_score(texts) if texts else 0.5
        
        # Combine news and ValuePickr sentiment for Indian stocks
        if valuepickr_analysis and valuepickr_analysis.get('status') == 'success':
            valuepickr_sentiment = valuepickr_analysis.get('sentiment_score', 0.5)
            valuepickr_confidence = valuepickr_analysis.get('confidence', 0.1)
            
            # Weighted average: 70% news, 30% ValuePickr for Indian stocks
            sent = (news_sentiment * 0.7) + (valuepickr_sentiment * 0.3)
            logger.info(f"Combined sentiment for {ticker}: News={news_sentiment:.2f}, ValuePickr={valuepickr_sentiment:.2f}, Combined={sent:.2f}")
        else:
            sent = news_sentiment
        
        # Enhanced confidence based on actual news availability and data quality
        base_confidence = 0.85 if len(headlines) >= 3 else 0.7 if len(headlines) >= 1 else 0.4
        
        # Initialize variables early to avoid scope issues
        headline_analyses = []
        freshness_scores = []
        
        # Get structured news data with dates
        news_data = await get_recent_news_summary(ticker)
        articles = news_data.get('articles', [])
        
        if headlines:
            for i, headline in enumerate(headlines[:3]):  # Analyze top 3 headlines
                # Get corresponding article data for date
                published_at = None
                if i < len(articles):
                    published_at = articles[i].get('published_at')
                
                sentiment_label, rationale, conf_level, formatted_date = await analyze_headline_sentiment(
                    headline, ticker, published_at
                )
                
                # Calculate freshness score
                freshness_score = calculate_news_freshness_score(published_at)
                freshness_scores.append(freshness_score)
                
                headline_analyses.append({
                    "headline": headline,
                    "sentiment": sentiment_label,
                    "rationale": rationale,
                    "confidence": conf_level,
                    "published_at": published_at,
                    "formatted_date": formatted_date,
                    "freshness_score": freshness_score
                })
        
        # Adjust confidence based on news freshness
        if freshness_scores:
            avg_freshness = sum(freshness_scores) / len(freshness_scores)
            # Reduce confidence for old news
            if avg_freshness < 0.2:  # 1+ year old news
                base_confidence *= 0.3
            elif avg_freshness < 0.4:  # 6+ months old news
                base_confidence *= 0.6
        
        # Create professional sentiment summary
        professional_sentiment = get_professional_sentiment_label(sent, base_confidence)
        
        # Format professional news summary with ValuePickr integration
        if headlines:
            # Create structured summary instead of cluttered text
            professional_summary = f"**Overall Sentiment:** {professional_sentiment}\n\n"
            
            # News Headlines Section
            professional_summary += "**News Headlines:**\n"
            for analysis in headline_analyses:
                freshness_indicator = ""
                if analysis['freshness_score'] < 0.2:  # 1+ year old
                    freshness_indicator = " ⚠️ (Old - 1+ year)"
                elif analysis['freshness_score'] < 0.4:  # 6+ months old
                    freshness_indicator = " ⚠️ (Old - 6+ months)"
                
                professional_summary += f"• {analysis['headline']} — {analysis['sentiment']}; {analysis['rationale']} ({analysis['formatted_date']}){freshness_indicator}.\n"
            
            # ValuePickr Community Section (for Indian stocks)
            if valuepickr_analysis and valuepickr_analysis.get('status') == 'success':
                vp_sentiment = valuepickr_analysis.get('sentiment_label', 'neutral')
                vp_summary = valuepickr_analysis.get('summary', '')
                vp_discussions = valuepickr_analysis.get('engagement_metrics', {}).get('discussion_count', 0)
                vp_views = valuepickr_analysis.get('engagement_metrics', {}).get('total_views', 0)
                vp_replies = valuepickr_analysis.get('engagement_metrics', {}).get('total_replies', 0)
                
                professional_summary += f"\n**ValuePickr Community Sentiment:** {vp_sentiment.title()}\n"
                professional_summary += f"• {vp_summary}\n"
                if vp_discussions > 0:
                    professional_summary += f"• Found {vp_discussions} active discussions on ValuePickr forum\n"
                    if vp_views > 0 or vp_replies > 0:
                        professional_summary += f"• Community engagement: {vp_replies} replies, {vp_views} views\n"
        else:
            professional_summary = f"**Overall Sentiment:** {professional_sentiment}\n\n"
            professional_summary += f"**News Coverage:** Limited news coverage available for {ticker} at this time.\n"
            
            # Add ValuePickr analysis even if no news
            if valuepickr_analysis and valuepickr_analysis.get('status') == 'success':
                vp_sentiment = valuepickr_analysis.get('sentiment_label', 'neutral')
                vp_summary = valuepickr_analysis.get('summary', '')
                vp_discussions = valuepickr_analysis.get('engagement_metrics', {}).get('discussion_count', 0)
                
                professional_summary += f"\n**ValuePickr Community Sentiment:** {vp_sentiment.title()}\n"
                professional_summary += f"• {vp_summary}\n"
                if vp_discussions > 0:
                    professional_summary += f"• Found {vp_discussions} active discussions on ValuePickr forum\n"
        
        # Store both professional and legacy formats
        state.setdefault("analysis", {})["news_sentiment"] = {
            "summary": professional_summary,
            "professional_sentiment": professional_sentiment,
            "score": sent,
            "headlines": headlines[:3],
            "headline_analyses": headline_analyses,
            "freshness_scores": freshness_scores,
            "avg_freshness": sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.5,
            "article_count": news_data.get("article_count", 0),
            "latest_date": news_data.get("latest_date"),
            "sources": news_data.get("sources", []),
            "raw_articles": news_data.get("articles", []),
            "valuepickr_analysis": valuepickr_analysis,
            "news_sentiment": news_sentiment,
            "combined_sentiment": sent
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
