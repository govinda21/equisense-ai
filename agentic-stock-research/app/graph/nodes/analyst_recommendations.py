from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.analyst_recommendations import analyze_analyst_recommendations
from app.logging import get_logger

logger = get_logger()

async def analyst_recommendations_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    analyst_data = await analyze_analyst_recommendations(ticker)
    state.setdefault("analysis", {})["analyst_recommendations"] = analyst_data
    
    # Log analyst data with freshness information
    logger.info(
        "analyst_recommendations_fetched",
        ticker=ticker,
        consensus=analyst_data.get("recommendation_summary", {}).get("consensus"),
        analyst_count=analyst_data.get("recommendation_summary", {}).get("analyst_count"),
        target_mean=analyst_data.get("target_prices", {}).get("mean"),
        freshness_status=analyst_data.get("data_freshness", {}).get("freshness_status"),
        days_since_latest=analyst_data.get("data_freshness", {}).get("days_since_latest")
    )

    # Calculate confidence based on data quality, consensus, and freshness
    confidence = _calculate_analyst_confidence(analyst_data)
    
    state.setdefault("confidences", {})["analyst_recommendations"] = confidence
    logger.info(
        "analyst_confidence_calculated",
        ticker=ticker,
        confidence=confidence,
        freshness_impact=_get_freshness_multiplier(analyst_data)
    )
    
    return state


def _calculate_analyst_confidence(analyst_data: dict) -> float:
    """
    Calculate confidence score for analyst recommendations based on:
    - Data availability (targets, recommendations)
    - Analyst consensus strength
    - Analyst count
    - Data freshness (NEW!)
    
    Returns: float between 0.0 and 1.0
    """
    # Base confidence from data availability
    has_targets = bool(analyst_data.get("target_prices", {}).get("mean"))
    has_recommendations = bool(analyst_data.get("recommendation_summary", {}).get("consensus"))
    consensus = analyst_data.get("recommendation_summary", {}).get("consensus", "").lower()
    analyst_count = analyst_data.get("recommendation_summary", {}).get("analyst_count", 0) or 0
    
    # Base confidence score (0.2 to 0.85)
    if not has_targets and not has_recommendations:
        base_confidence = 0.2  # Minimal data
    elif has_targets and not has_recommendations:
        base_confidence = 0.4  # Price targets only
    elif not has_targets and has_recommendations:
        base_confidence = 0.45  # Recommendations only
    else:
        # Both targets and recommendations available
        if consensus in ["strong_buy", "strong buy"]:
            base_confidence = 0.90 if analyst_count > 15 else 0.85 if analyst_count > 10 else 0.75
        elif consensus in ["buy"]:
            base_confidence = 0.75 if analyst_count > 15 else 0.65 if analyst_count > 10 else 0.55
        elif consensus in ["hold", "neutral"]:
            base_confidence = 0.55 if analyst_count > 10 else 0.50
        elif consensus in ["sell", "strong_sell", "strong sell"]:
            base_confidence = 0.70 if analyst_count > 10 else 0.60
        else:
            base_confidence = 0.50  # No clear consensus
    
    # Apply freshness multiplier (0.5 to 1.0)
    freshness_multiplier = _get_freshness_multiplier(analyst_data)
    
    # Final confidence with freshness adjustment
    final_confidence = base_confidence * freshness_multiplier
    
    # Ensure confidence stays within bounds
    return max(0.1, min(0.9, final_confidence))


def _get_freshness_multiplier(analyst_data: dict) -> float:
    """
    Calculate freshness multiplier based on how old the analyst data is.
    
    Returns: float between 0.2 and 1.0
    """
    data_freshness = analyst_data.get("data_freshness", {})
    
    # If no freshness data, give benefit of doubt but slight penalty
    if not data_freshness or "days_since_latest" not in data_freshness:
        return 0.9
    
    days_old = data_freshness.get("days_since_latest", 0)
    
    if days_old <= 30:
        return 1.0  # Current - full confidence
    elif days_old <= 60:
        return 0.80  # Slightly stale - minor penalty
    elif days_old <= 90:
        return 0.60  # Stale - moderate penalty
    else:
        return 0.20  # Outdated - significant penalty
