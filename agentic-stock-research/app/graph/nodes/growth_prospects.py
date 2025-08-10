from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.growth_prospects import analyze_growth_prospects


async def growth_prospects_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    growth_data = await analyze_growth_prospects(ticker)
    state.setdefault("analysis", {})["growth_prospects"] = growth_data
    
    # Confidence based on data quality and historical performance
    has_historical = bool(growth_data.get("historical_growth", {}).get("metrics"))
    has_outlook = bool(growth_data.get("growth_outlook", {}).get("overall_outlook"))
    confidence = 0.8 if (has_historical and has_outlook) else 0.6 if has_outlook else 0.4
    
    state.setdefault("confidences", {})["growth_prospects"] = confidence
    return state
