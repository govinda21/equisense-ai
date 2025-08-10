from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.cashflow import analyze_cashflows


async def cashflow_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    cash = await analyze_cashflows(ticker)
    state.setdefault("analysis", {})["cashflow"] = cash
    state.setdefault("confidences", {})["cashflow"] = 0.75 if cash else 0.2
    return state
