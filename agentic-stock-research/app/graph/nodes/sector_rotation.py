from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.sector_rotation import analyze_sector_rotation
from app.logging import get_logger

logger = get_logger()


async def sector_rotation_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Perform sector rotation analysis for investment decision making
    """
    ticker = state["tickers"][0]
    
    # Check if already executed to prevent duplicate runs
    if "sector_rotation" in state.get("analysis", {}):
        logger.info(f"SECTOR_ROTATION_NODE: Already executed for {ticker}, skipping")
        return state
    
    try:
        logger.info(f"SECTOR_ROTATION_NODE: Starting sector rotation analysis for {ticker}")
        logger.info(f"SECTOR_ROTATION_NODE: State keys: {list(state.keys())}")
        
        # Perform sector rotation analysis
        rotation_result = await analyze_sector_rotation(ticker, days_back=90)
        
        if "error" in rotation_result:
            logger.warning(f"Sector rotation analysis failed for {ticker}: {rotation_result['error']}")
            # Set default neutral values
            state.setdefault("analysis", {})["sector_rotation"] = {
                "ticker": ticker,
                "error": rotation_result["error"],
                "rotation_phase": "Uncertain Rotation",
                "sector_outlook": "Neutral",
                "rotation_signal": "Hold",
                "market_breadth": 0.5,
                "confidence_score": 0.3
            }
            state.setdefault("confidences", {})["sector_rotation"] = 0.3
        else:
            # Store successful analysis
            state.setdefault("analysis", {})["sector_rotation"] = rotation_result
            
            # Calculate confidence based on data quality and market breadth
            confidence = 0.7  # Base confidence
            market_breadth = rotation_result.get("rotation_patterns", {}).get("market_breadth", 0.5)
            sector_count = rotation_result.get("rotation_patterns", {}).get("sector_count", 0)
            
            # Adjust confidence based on data quality
            if sector_count >= 8:  # Good sector coverage
                confidence += 0.1
            if 0.3 <= market_breadth <= 0.7:  # Moderate breadth (more reliable)
                confidence += 0.1
            elif market_breadth > 0.8 or market_breadth < 0.2:  # Extreme breadth (less reliable)
                confidence -= 0.1
            
            confidence = min(0.9, max(0.1, confidence))
            state.setdefault("confidences", {})["sector_rotation"] = confidence
            
            logger.info(f"SECTOR_ROTATION_NODE: Analysis completed for {ticker} "
                       f"(Phase: {rotation_result.get('rotation_patterns', {}).get('rotation_phase', 'Unknown')}, "
                       f"Outlook: {rotation_result.get('recommendations', {}).get('sector_outlook', 'Unknown')}, "
                       f"Signal: {rotation_result.get('recommendations', {}).get('rotation_signal', 'Unknown')})")
            logger.info(f"SECTOR_ROTATION_NODE: Stored in state['analysis']['sector_rotation']")
        
        return state
        
    except Exception as e:
        logger.error(f"Sector rotation analysis failed for {ticker}: {e}")
        state.setdefault("analysis", {})["sector_rotation"] = {"error": str(e)}
        state.setdefault("confidences", {})["sector_rotation"] = 0.1
        return state
