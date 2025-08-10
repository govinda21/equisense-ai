from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.valuation import compute_valuation


async def valuation_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    valuation = await compute_valuation(ticker)
    state.setdefault("analysis", {})["valuation"] = valuation
    # Confidence is lower if DCF could not be computed
    state.setdefault("confidences", {})["valuation"] = 0.8 if valuation and valuation.get("intrinsic_market_cap") else 0.4
    return state


