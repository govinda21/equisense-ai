from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState


async def start_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    tickers_input = state.get("tickers", [])
    if isinstance(tickers_input, str):
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    elif isinstance(tickers_input, list):
        tickers = [t.strip().upper() for t in tickers_input if t and t.strip()]
    else:
        tickers = []
    return ResearchState(
        tickers=tickers,
        country=state.get("country", "United States"),
        raw_data={},
        analysis={},
        confidences={},
        retries={},
        needs_rerun=[],
    )
