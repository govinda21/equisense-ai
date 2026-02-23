from __future__ import annotations

import asyncio
import logging

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.leadership import analyze_leadership

logger = logging.getLogger(__name__)
LEADERSHIP_TIMEOUT = 10.0


async def leadership_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    try:
        lead = await asyncio.wait_for(analyze_leadership(ticker), timeout=LEADERSHIP_TIMEOUT)
        state.setdefault("analysis", {})["leadership"] = lead
        state.setdefault("confidences", {})["leadership"] = 0.7
    except asyncio.TimeoutError:
        logger.warning(f"[{ticker}] Leadership analysis timed out after {LEADERSHIP_TIMEOUT}s")
        state.setdefault("analysis", {})["leadership"] = {"error": "timeout", "message": "Leadership analysis timed out"}
        state.setdefault("confidences", {})["leadership"] = 0.1
    except Exception as e:
        logger.error(f"[{ticker}] Leadership analysis failed: {e}")
        state.setdefault("analysis", {})["leadership"] = {"error": str(e)}
        state.setdefault("confidences", {})["leadership"] = 0.1
    return state
