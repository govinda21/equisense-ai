"""
Strategic Conviction Analysis Graph Node

This node integrates strategic conviction analysis into the research workflow.
"""

from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.strategic_conviction import analyze_strategic_conviction
from app.logging import get_logger

logger = get_logger()


async def strategic_conviction_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Perform strategic conviction analysis for investment decision making
    """
    ticker = state["tickers"][0]
    
    try:
        logger.info(f"Starting strategic conviction analysis for {ticker}")
        
        # Perform strategic conviction analysis
        conviction_result = await analyze_strategic_conviction(ticker)
        
        if "error" in conviction_result:
            logger.warning(f"Strategic conviction analysis failed for {ticker}: {conviction_result['error']}")
            # Set default low conviction values
            state.setdefault("analysis", {})["strategic_conviction"] = {
                "ticker": ticker,
                "error": conviction_result["error"],
                "overall_conviction_score": 30.0,
                "conviction_level": "Low Conviction",
                "strategic_recommendation": "Hold - Insufficient Conviction",
                "position_sizing_pct": 1.0
            }
            state.setdefault("confidences", {})["strategic_conviction"] = 0.3
        else:
            # Store successful analysis
            conviction_analysis = conviction_result["conviction_analysis"]
            state.setdefault("analysis", {})["strategic_conviction"] = conviction_analysis
            
            # Set confidence based on conviction score
            conviction_score = conviction_analysis["overall_conviction_score"]
            confidence = min(0.9, max(0.1, conviction_score / 100.0))
            state.setdefault("confidences", {})["strategic_conviction"] = confidence
            
            logger.info(f"Strategic conviction analysis completed for {ticker} "
                       f"(Score: {conviction_score:.1f}, "
                       f"Level: {conviction_analysis['conviction_level']}, "
                       f"Recommendation: {conviction_analysis['strategic_recommendation']})")
        
        return state
        
    except Exception as e:
        logger.error(f"Strategic conviction analysis failed for {ticker}: {e}")
        
        # Fallback analysis with error information
        state.setdefault("analysis", {})["strategic_conviction"] = {
            "ticker": ticker,
            "error": str(e),
            "overall_conviction_score": 30.0,
            "conviction_level": "Low Conviction",
            "strategic_recommendation": "Hold - Analysis Error",
            "position_sizing_pct": 1.0
        }
        state.setdefault("confidences", {})["strategic_conviction"] = 0.3
        
        return state
