from app.config import AppSettings
from app.graph.state import ResearchState
from app.logging import get_logger
from app.tools.options_flow import analyze_options_flow

logger = get_logger(__name__)


async def options_flow_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    try:
        flow_result = await analyze_options_flow(ticker)
        if "error" in flow_result:
            state.setdefault("analysis", {})["options_flow"] = {
                "ticker": ticker, "error": flow_result["error"],
                "flow_sentiment": "Neutral", "sentiment_score": 0.5, "unusual_activity": False
            }
            state.setdefault("confidences", {})["options_flow"] = 0.3
        else:
            state.setdefault("analysis", {})["options_flow"] = flow_result
            sentiment_score = flow_result.get("sentiment_score", 0.5)
            unusual_activity = flow_result.get("unusual_activity", False)
            base = min(0.9, max(0.1, abs(sentiment_score - 0.5) * 2))
            state.setdefault("confidences", {})["options_flow"] = min(0.9, base + (0.2 if unusual_activity else 0))
    except Exception as e:
        logger.error(f"Options flow analysis failed for {ticker}: {e}")
        state.setdefault("analysis", {})["options_flow"] = {"error": str(e)}
        state.setdefault("confidences", {})["options_flow"] = 0.1
    return state
