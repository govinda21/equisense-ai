"""Conditional Synthesis Node - selects between institutional and standard synthesis."""
from __future__ import annotations

import logging
from copy import deepcopy

from app.config import AppSettings
from app.graph.state import ResearchState
from app.graph.nodes.synthesis import synthesis_node as standard_synthesis
from app.graph.nodes.enhanced_synthesis import synthesis_node as institutional_synthesis

logger = logging.getLogger(__name__)


async def conditional_synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    local_state = deepcopy(state)
    ticker = local_state.get("tickers", [None])[0]
    try:
        # Always use standard synthesis (institutional synthesis disabled pending fix)
        result = await standard_synthesis(local_state, settings)
        return result
    except Exception as e:
        logger.error(f"[{ticker}] Synthesis failed: {e}, falling back to standard")
        try:
            return await standard_synthesis(local_state, settings)
        except Exception as fallback_err:
            logger.error(f"[{ticker}] Fallback synthesis also failed: {fallback_err}")
            return {
                **local_state,
                "final_output": {
                    "tickers": local_state.get("tickers", []),
                    "reports": [],
                    "generated_at": "Error occurred during analysis",
                    "error": str(e)
                }
            }


synthesis_node = conditional_synthesis_node
