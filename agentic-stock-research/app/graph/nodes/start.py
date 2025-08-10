from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState


async def start_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    tickers = [t.strip().upper() for t in state.get("tickers", []) if t.strip()]
    return ResearchState(
        tickers=tickers,
        raw_data={},
        analysis={},
        confidences={},
        retries={},
        needs_rerun=[],
    )
