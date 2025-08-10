from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.peer_analysis import analyze_peers


async def peer_analysis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    peer_data = await analyze_peers(ticker)
    state.setdefault("analysis", {})["peer_analysis"] = peer_data
    state.setdefault("confidences", {})["peer_analysis"] = 0.8 if peer_data.get("peers_identified") else 0.3
    return state
