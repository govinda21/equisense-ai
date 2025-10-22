"""
Earnings Call Analysis Node

Analyzes earnings call transcripts to extract management sentiment,
guidance, and key insights for investment decision making.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.earnings_call_analyzer import analyze_earnings_calls

logger = logging.getLogger(__name__)


async def earnings_call_analysis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Analyze earnings call transcripts for management insights
    
    Processes:
    1. Fetch recent earnings call transcripts
    2. Analyze management sentiment and tone
    3. Extract financial guidance
    4. Analyze Q&A session for defensiveness
    5. Identify key topics and concerns
    6. Generate insights for investment decision
    """
    ticker = state["tickers"][0]
    logger.info(f"Starting earnings call analysis for {ticker}")
    
    # DEBUG: Log state before analysis
    logger.info(f"DEBUG earnings_call_analysis: state keys: {list(state.keys())}")
    logger.info(f"DEBUG earnings_call_analysis: analysis keys: {list(state.get('analysis', {}).keys())}")
    
    try:
        # Analyze earnings calls
        logger.info(f"DEBUG earnings_call_analysis: About to call analyze_earnings_calls for {ticker}")
        earnings_analysis = await analyze_earnings_calls(
            ticker=ticker,
            days_back=180,  # Look back 6 months
            max_calls=3     # Analyze last 3 calls
        )
        logger.info(f"DEBUG earnings_call_analysis: analyze_earnings_calls completed, result keys: {list(earnings_analysis.keys())}")
        
        # Process analysis results
        call_data = {
            "ticker": ticker,
            "total_calls_analyzed": earnings_analysis.get("total_calls", 0),
            "analysis_period": earnings_analysis.get("analysis_period", "180 days"),
            "sources_used": earnings_analysis.get("sources_used", []),
            "status": "success" if earnings_analysis.get("total_calls", 0) > 0 else "no_calls_found"
        }
        
        if earnings_analysis.get("total_calls", 0) > 0:
            # Extract key insights
            aggregated = earnings_analysis.get("aggregated_sentiment", {})
            guidance = earnings_analysis.get("guidance_summary", {})
            topics = earnings_analysis.get("key_topics", [])
            concerns = earnings_analysis.get("common_concerns", [])
            initiatives = earnings_analysis.get("new_initiatives", [])
            individual_analyses = earnings_analysis.get("individual_analyses", [])
            
            # Management sentiment analysis
            call_data.update({
                "management_sentiment": {
                    "overall_sentiment": aggregated.get("overall_sentiment", 0.0),
                    "confidence_score": aggregated.get("confidence_score", 0.0),
                    "defensiveness_score": aggregated.get("defensiveness_score", 0.0),
                    "call_quality": aggregated.get("call_quality", 0.0)
                },
                "guidance_analysis": {
                    "revenue_guidance": guidance.get("revenue", []),
                    "earnings_guidance": guidance.get("earnings", []),
                    "margin_guidance": guidance.get("margins", []),
                    "capex_guidance": guidance.get("capex", [])
                },
                "key_insights": {
                    "topics_discussed": topics,
                    "concerns_raised": concerns,
                    "new_initiatives": initiatives
                },
                "quarterly_trends": individual_analyses
            })
            
            # Generate summary insights
            call_data["summary_insights"] = _generate_summary_insights(
                aggregated, guidance, topics, concerns, initiatives
            )
            
            # Calculate confidence score
            call_data["confidence_score"] = _calculate_analysis_confidence(
                earnings_analysis.get("total_calls", 0),
                aggregated.get("confidence_score", 0.0),
                len(topics),
                len(guidance.get("revenue", []))
            )
        
        else:
            # No calls found - provide clear explanation
            is_indian_stock = '.NS' in ticker.upper()
            if is_indian_stock:
                summary_message = f"No earnings call transcripts available for {ticker}. Indian stock earnings call data is not available through current free APIs (API Ninja, FMP). Consider using premium data sources or company investor relations websites for actual earnings call transcripts."
            else:
                summary_message = f"No recent earnings call transcripts available for {ticker}. This may be due to limited data availability or the company not conducting public earnings calls."
            
            call_data.update({
                "management_sentiment": {
                    "overall_sentiment": 0.0,
                    "confidence_score": 0.0,
                    "defensiveness_score": 0.0,
                    "call_quality": 0.0
                },
                "guidance_analysis": {},
                "key_insights": {
                    "topics_discussed": [],
                    "concerns_raised": [],
                    "new_initiatives": []
                },
                "summary_insights": summary_message,
                "confidence_score": 0.0
            })
        
        # Add to state
        if "analysis" not in state:
            state["analysis"] = {}
        
        state["analysis"]["earnings_calls"] = call_data
        
        logger.info(f"Earnings call analysis complete for {ticker}: {call_data['total_calls_analyzed']} calls analyzed")
        
        # DEBUG: Log state after analysis
        logger.info(f"DEBUG earnings_call_analysis: state keys after: {list(state.keys())}")
        logger.info(f"DEBUG earnings_call_analysis: analysis keys after: {list(state.get('analysis', {}).keys())}")
        logger.info(f"DEBUG earnings_call_analysis: earnings_calls data: {call_data}")
        
        return state
    
    except Exception as e:
        logger.error(f"Earnings call analysis failed for {ticker}: {e}", exc_info=True)
        
        # Add error info to state but don't fail the workflow
        if "analysis" not in state:
            state["analysis"] = {}
        
        state["analysis"]["earnings_calls"] = {
            "ticker": ticker,
            "error": str(e),
            "status": "failed",
            "total_calls_analyzed": 0,
            "confidence_score": 0.0
        }
        
        return state


def _generate_summary_insights(
    aggregated: Dict[str, Any],
    guidance: Dict[str, Any],
    topics: List[str],
    concerns: List[str],
    initiatives: List[str]
) -> str:
    """Generate summary insights from earnings call analysis"""
    
    insights = []
    
    # Sentiment insights
    sentiment = aggregated.get("overall_sentiment", 0.0)
    confidence = aggregated.get("confidence_score", 0.0)
    defensiveness = aggregated.get("defensiveness_score", 0.0)
    
    if sentiment > 0.2:
        insights.append("Management tone is generally positive and optimistic.")
    elif sentiment < -0.2:
        insights.append("Management tone is cautious or negative.")
    else:
        insights.append("Management tone is neutral and balanced.")
    
    if confidence > 0.7:
        insights.append("Management demonstrates high confidence in business outlook.")
    elif confidence < 0.4:
        insights.append("Management shows low confidence or uncertainty.")
    
    if defensiveness > 0.6:
        insights.append("Management appears defensive in Q&A sessions, potentially avoiding difficult topics.")
    elif defensiveness < 0.3:
        insights.append("Management is open and transparent in addressing analyst questions.")
    
    # Guidance insights
    revenue_guidance = guidance.get("revenue", [])
    earnings_guidance = guidance.get("earnings", [])
    
    if revenue_guidance:
        insights.append(f"Management provided revenue guidance in {len(revenue_guidance)} call(s).")
    
    if earnings_guidance:
        insights.append(f"Management provided earnings guidance in {len(earnings_guidance)} call(s).")
    
    # Topic insights
    if topics:
        insights.append(f"Key topics discussed: {', '.join(topics[:3])}.")
    
    if concerns:
        insights.append(f"Main concerns raised: {', '.join(concerns[:2])}.")
    
    if initiatives:
        insights.append(f"New initiatives mentioned: {', '.join(initiatives[:2])}.")
    
    return " ".join(insights) if insights else "Limited insights available from earnings call analysis."


def _calculate_analysis_confidence(
    total_calls: int,
    sentiment_confidence: float,
    topics_count: int,
    guidance_count: int
) -> float:
    """Calculate overall confidence score for earnings call analysis"""
    
    if total_calls == 0:
        return 0.0
    
    # Base confidence from number of calls analyzed
    calls_confidence = min(1.0, total_calls / 3.0)  # Normalize to 3 calls
    
    # Sentiment confidence
    sentiment_weight = 0.4
    calls_weight = 0.3
    content_weight = 0.3
    
    # Content richness (topics + guidance)
    content_richness = min(1.0, (topics_count + guidance_count) / 10.0)
    
    # Weighted average
    confidence = (
        calls_confidence * calls_weight +
        sentiment_confidence * sentiment_weight +
        content_richness * content_weight
    )
    
    return round(confidence, 2)


# Convenience function for standalone usage
async def get_earnings_call_insights(ticker: str) -> Dict[str, Any]:
    """
    Get earnings call insights without full workflow
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Dictionary with earnings call analysis results
    """
    mock_state = {
        "tickers": [ticker],
        "analysis": {}
    }
    
    mock_settings = None  # Not used currently
    
    result_state = await earnings_call_analysis_node(mock_state, mock_settings)
    
    return result_state.get("analysis", {}).get("earnings_calls", {})
