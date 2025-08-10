from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.analyst_recommendations import analyze_analyst_recommendations


async def analyst_recommendations_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    analyst_data = await analyze_analyst_recommendations(ticker)
    state.setdefault("analysis", {})["analyst_recommendations"] = analyst_data
    
    # Confidence based on availability of analyst data
    has_targets = bool(analyst_data.get("target_prices", {}).get("mean"))
    has_recommendations = bool(analyst_data.get("recommendation_summary", {}).get("consensus"))
    confidence = 0.8 if (has_targets and has_recommendations) else 0.5 if (has_targets or has_recommendations) else 0.3
    
    state.setdefault("confidences", {})["analyst_recommendations"] = confidence
    return state
