from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState


async def start_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    # Handle both string and list inputs for tickers
    tickers_input = state.get("tickers", [])
    if isinstance(tickers_input, str):
        # If string, split by comma
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
    elif isinstance(tickers_input, list):
        # If already a list, just clean and uppercase
        tickers = [t.strip().upper() for t in tickers_input if t and t.strip()]
    else:
        # Fallback to empty list
        tickers = []
    
    # Preserve country from input state
    country = state.get("country", "United States")  # Default to United States
    
    return ResearchState(
        tickers=tickers,
        country=country,
        raw_data={},
        analysis={},
        confidences={},
        retries={},
        needs_rerun=[],
    )
