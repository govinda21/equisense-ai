from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.fundamentals import compute_fundamentals


async def fundamentals_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    fundamentals = await compute_fundamentals(ticker)
    state.setdefault("analysis", {})["fundamentals"] = fundamentals
    state.setdefault("confidences", {})["fundamentals"] = 0.8 if fundamentals else 0.2
    return state
