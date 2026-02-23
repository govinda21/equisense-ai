from __future__ import annotations

from copy import deepcopy

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.strategic_conviction import analyze_strategic_conviction
from app.logging import get_logger

logger = get_logger()

_FALLBACK = {
    "overall_conviction_score": 30.0,
    "conviction_level": "Low Conviction",
    "strategic_recommendation": "Hold - Analysis Error",
    "position_sizing_pct": 1.0,
}


async def strategic_conviction_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    local_state = deepcopy(state)
    ticker = local_state["tickers"][0]

    if "strategic_conviction" in local_state.get("analysis", {}):
        return local_state

    try:
        result = await analyze_strategic_conviction(ticker)
        if "error" in result:
            local_state.setdefault("analysis", {})["strategic_conviction"] = {
                "ticker": ticker, "error": result["error"], **_FALLBACK
            }
            local_state.setdefault("confidences", {})["strategic_conviction"] = 0.3
        else:
            conviction_analysis = result["conviction_analysis"]
            local_state.setdefault("analysis", {})["strategic_conviction"] = conviction_analysis
            score = conviction_analysis["overall_conviction_score"]
            local_state.setdefault("confidences", {})["strategic_conviction"] = min(0.9, max(0.1, score / 100.0))
    except Exception as e:
        logger.error(f"[{ticker}] Strategic conviction failed: {e}")
        local_state.setdefault("analysis", {})["strategic_conviction"] = {
            "ticker": ticker, "error": str(e), **_FALLBACK
        }
        local_state.setdefault("confidences", {})["strategic_conviction"] = 0.3

    return local_state
