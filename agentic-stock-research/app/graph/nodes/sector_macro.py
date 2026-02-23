from __future__ import annotations

import asyncio
import logging

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.sector_macro import analyze_sector_macro

logger = logging.getLogger(__name__)
SECTOR_MACRO_TIMEOUT = 10.0


async def sector_macro_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    try:
        sm = await asyncio.wait_for(analyze_sector_macro(ticker), timeout=SECTOR_MACRO_TIMEOUT)
        state.setdefault("analysis", {})["sector_macro"] = sm
        state.setdefault("confidences", {})["sector_macro"] = 0.7
    except asyncio.TimeoutError:
        logger.warning(f"[{ticker}] Sector macro analysis timed out after {SECTOR_MACRO_TIMEOUT}s")
        state.setdefault("analysis", {})["sector_macro"] = {"error": "timeout", "message": "Sector macro analysis timed out"}
        state.setdefault("confidences", {})["sector_macro"] = 0.1
    except Exception as e:
        logger.error(f"[{ticker}] Sector macro analysis failed: {e}")
        state.setdefault("analysis", {})["sector_macro"] = {"error": str(e)}
        state.setdefault("confidences", {})["sector_macro"] = 0.1
    return state
