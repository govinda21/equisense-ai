from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.sector_macro import analyze_sector_macro


async def sector_macro_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    sm = await analyze_sector_macro(ticker)
    state.setdefault("analysis", {})["sector_macro"] = sm
    state.setdefault("confidences", {})["sector_macro"] = 0.7
    return state
