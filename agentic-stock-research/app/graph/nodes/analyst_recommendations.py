from __future__ import annotations

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.analyst_recommendations import analyze_analyst_recommendations
from app.logging import get_logger

logger = get_logger()

_FRESHNESS_MULTIPLIERS = [(30, 1.0), (60, 0.80), (90, 0.60)]


def _get_freshness_multiplier(analyst_data: dict) -> float:
    days_old = analyst_data.get("data_freshness", {}).get("days_since_latest")
    if days_old is None:
        return 0.9
    for threshold, mult in _FRESHNESS_MULTIPLIERS:
        if days_old <= threshold:
            return mult
    return 0.20


def _calculate_analyst_confidence(analyst_data: dict) -> float:
    has_targets = bool(analyst_data.get("target_prices", {}).get("mean"))
    has_recs = bool(analyst_data.get("recommendation_summary", {}).get("consensus"))
    consensus = analyst_data.get("recommendation_summary", {}).get("consensus", "").lower()
    count = analyst_data.get("recommendation_summary", {}).get("analyst_count", 0) or 0

    if not has_targets and not has_recs:
        base = 0.2
    elif has_targets and not has_recs:
        base = 0.4
    elif not has_targets and has_recs:
        base = 0.45
    elif consensus in ("strong_buy", "strong buy"):
        base = 0.90 if count > 15 else 0.85 if count > 10 else 0.75
    elif consensus == "buy":
        base = 0.75 if count > 15 else 0.65 if count > 10 else 0.55
    elif consensus in ("hold", "neutral"):
        base = 0.55 if count > 10 else 0.50
    elif consensus in ("sell", "strong_sell", "strong sell"):
        base = 0.70 if count > 10 else 0.60
    else:
        base = 0.50

    return max(0.1, min(0.9, base * _get_freshness_multiplier(analyst_data)))


async def analyst_recommendations_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    analyst_data = await analyze_analyst_recommendations(ticker)
    state.setdefault("analysis", {})["analyst_recommendations"] = analyst_data
    confidence = _calculate_analyst_confidence(analyst_data)
    state.setdefault("confidences", {})["analyst_recommendations"] = confidence
    logger.info("analyst_recommendations_fetched", ticker=ticker,
                consensus=analyst_data.get("recommendation_summary", {}).get("consensus"),
                freshness_multiplier=_get_freshness_multiplier(analyst_data),
                confidence=confidence)
    return state
