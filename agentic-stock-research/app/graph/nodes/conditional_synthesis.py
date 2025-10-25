"""
Conditional Synthesis Node
Phase 1: Core Investment Framework - Smart Synthesis Selection
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.config import AppSettings
from app.graph.state import ResearchState
from app.graph.nodes.synthesis import synthesis_node as standard_synthesis
from app.graph.nodes.enhanced_synthesis import synthesis_node as institutional_synthesis

logger = logging.getLogger(__name__)


async def conditional_synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Conditional synthesis node that chooses between institutional and standard synthesis
    
    Uses institutional synthesis when:
    - Analysis type is "institutional"
    - Horizon filtering is requested
    - Professional formatting is needed
    
    Falls back to standard synthesis for:
    - Legacy compatibility
    - Simple analysis requests
    - Error recovery
    """
    try:
        # Check if institutional analysis is requested
        analysis_type = state.get("analysis_type", "standard")
        horizon_short_days = state.get("horizon_short_days")
        horizon_long_days = state.get("horizon_long_days")
        
        # Determine if institutional analysis should be used
        use_institutional = (
            analysis_type == "institutional" or
            (horizon_short_days and horizon_long_days) or
            state.get("include_charts", False) or
            state.get("include_appendix", False)
        )
        
        if use_institutional:
            logger.info("Using institutional synthesis for enhanced analysis")
            return await institutional_synthesis(state, settings)
        else:
            logger.info("Using standard synthesis for legacy compatibility")
            return await standard_synthesis(state, settings)
            
    except Exception as e:
        logger.error(f"Error in conditional synthesis: {str(e)}")
        logger.warning("Falling back to standard synthesis")
        
        # Fallback to standard synthesis
        try:
            return await standard_synthesis(state, settings)
        except Exception as fallback_error:
            logger.error(f"Standard synthesis also failed: {str(fallback_error)}")
            # Return minimal state to prevent complete failure
            return {
                **state,
                "final_output": {
                    "tickers": state.get("tickers", []),
                    "reports": [],
                    "generated_at": "Error occurred during analysis",
                    "error": str(e)
                }
            }


# Export the conditional synthesis function
synthesis_node = conditional_synthesis_node
