# Options Flow Analysis Node

from typing import Any, Dict
from app.config import AppSettings
from app.graph.state import ResearchState
from app.logging import get_logger
from app.tools.options_flow import analyze_options_flow

logger = get_logger(__name__)

async def options_flow_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Perform options flow analysis for investment decision making
    """
    ticker = state["tickers"][0]
    
    try:
        logger.info(f"OPTIONS_FLOW_NODE: Starting options flow analysis for {ticker}")
        
        # Perform options flow analysis
        flow_result = await analyze_options_flow(ticker)
        
        if "error" in flow_result:
            logger.warning(f"Options flow analysis failed for {ticker}: {flow_result['error']}")
            # Set default neutral values
            state.setdefault("analysis", {})["options_flow"] = {
                "ticker": ticker,
                "error": flow_result["error"],
                "flow_sentiment": "Neutral",
                "sentiment_score": 0.5,
                "unusual_activity": False
            }
            state.setdefault("confidences", {})["options_flow"] = 0.3
        else:
            # Store successful analysis
            state.setdefault("analysis", {})["options_flow"] = flow_result
            
            # Set confidence based on data quality and unusual activity
            sentiment_score = flow_result.get("sentiment_score", 0.5)
            unusual_activity = flow_result.get("unusual_activity", False)
            
            # Higher confidence if unusual activity is detected
            base_confidence = min(0.9, max(0.1, abs(sentiment_score - 0.5) * 2))
            confidence = min(0.9, base_confidence + (0.2 if unusual_activity else 0))
            
            state.setdefault("confidences", {})["options_flow"] = confidence
            
            logger.info(f"OPTIONS_FLOW_NODE: Analysis completed for {ticker} "
                       f"(Sentiment: {flow_result['flow_sentiment']}, "
                       f"Score: {sentiment_score:.2f}, "
                       f"Unusual Activity: {unusual_activity})")
        
        return state
        
    except Exception as e:
        logger.error(f"Options flow analysis failed for {ticker}: {e}")
        state.setdefault("analysis", {})["options_flow"] = {"error": str(e)}
        state.setdefault("confidences", {})["options_flow"] = 0.1
        return state
