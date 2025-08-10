from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.leadership import analyze_leadership


async def leadership_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    lead = await analyze_leadership(ticker)
    state.setdefault("analysis", {})["leadership"] = lead
    state.setdefault("confidences", {})["leadership"] = 0.7
    return state
