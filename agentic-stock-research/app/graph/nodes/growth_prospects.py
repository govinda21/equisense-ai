from __future__ import annotations

import asyncio
import logging

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.growth_prospects import analyze_growth_prospects

logger = logging.getLogger(__name__)
GROWTH_PROSPECTS_TIMEOUT = 15.0


async def growth_prospects_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    try:
        growth_data = await asyncio.wait_for(analyze_growth_prospects(ticker), timeout=GROWTH_PROSPECTS_TIMEOUT)
        state.setdefault("analysis", {})["growth_prospects"] = growth_data
        has_historical = bool(growth_data.get("historical_growth", {}).get("metrics"))
        has_outlook = bool(growth_data.get("growth_outlook", {}).get("overall_outlook"))
        confidence = 0.8 if (has_historical and has_outlook) else 0.6 if has_outlook else 0.4
        state.setdefault("confidences", {})["growth_prospects"] = confidence
    except asyncio.TimeoutError:
        logger.warning(f"[{ticker}] Growth prospects timed out after {GROWTH_PROSPECTS_TIMEOUT}s")
        state.setdefault("analysis", {})["growth_prospects"] = {
            "error": "timeout", "message": "Growth prospects analysis timed out",
            "historical_growth": {}, "growth_outlook": {"overall_outlook": "Unknown"}
        }
        state.setdefault("confidences", {})["growth_prospects"] = 0.2
    except Exception as e:
        logger.error(f"[{ticker}] Growth prospects failed: {e}")
        state.setdefault("analysis", {})["growth_prospects"] = {"error": str(e)}
        state.setdefault("confidences", {})["growth_prospects"] = 0.2
    return state
