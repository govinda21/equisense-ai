from __future__ import annotations

from typing import Any, Dict, List, Optional
import asyncio
import yfinance as yf
from datetime import datetime
import pandas as pd

from app.tools.finance import fetch_info
import logging

logger = logging.getLogger(__name__)


def _safe_float(x: Any) -> Optional[float]:
    try:
        f = float(x) if x is not None else None
        return None if f != f else f  # NaN check
    except Exception:
        return None


def _parse_index_date(idx) -> str:
    if isinstance(idx, pd.Timestamp):
        return idx.strftime("%Y-%m-%d")
    return str(idx)


def _calculate_consensus(
    current_price: Optional[float], target_mean: Optional[float],
    target_high: Optional[float], target_low: Optional[float],
    target_median: Optional[float], rec_mean: Optional[float],
    rec_key: str, recent_recs: List[Dict]
) -> Dict[str, Any]:
    analysis: Dict[str, Any] = {}

    if current_price and target_mean:
        upside = ((target_mean - current_price) / current_price) * 100
        analysis["implied_return"] = upside
        analysis["price_sentiment"] = (
            "Very Bullish" if upside > 20 else
            "Bullish" if upside > 10 else
            "Slightly Bullish" if upside > 0 else
            "Neutral" if upside > -10 else "Bearish"
        )

    if target_high and target_low and target_mean:
        dispersion = ((target_high - target_low) / target_mean) * 100
        analysis["target_dispersion"] = dispersion
        analysis["analyst_agreement"] = "High" if dispersion < 20 else "Moderate" if dispersion < 40 else "Low"

    if recent_recs:
        r = recent_recs[-1]
        total = sum(r.get(k, 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell"))
        if total > 0:
            analysis["recommendation_distribution"] = {
                "buy_percentage": (r.get("strongBuy", 0) + r.get("buy", 0)) / total * 100,
                "hold_percentage": r.get("hold", 0) / total * 100,
                "sell_percentage": (r.get("sell", 0) + r.get("strongSell", 0)) / total * 100,
                "total_analysts": total,
            }

    parts = [
        f"Price sentiment: {analysis['price_sentiment']}" if "price_sentiment" in analysis else None,
        f"Implied return: {analysis['implied_return']:.1f}%" if "implied_return" in analysis else None,
        f"Analyst agreement: {analysis['analyst_agreement']}" if "analyst_agreement" in analysis else None,
        f"Consensus: {rec_key.title()}" if rec_key else None,
    ]
    analysis["summary"] = "; ".join(p for p in parts if p) or "Limited consensus data available"
    return analysis


def _analyze_price_targets(
    current_price: Optional[float], target_mean: Optional[float],
    target_high: Optional[float], target_low: Optional[float]
) -> Dict[str, Any]:
    if not current_price:
        return {"analysis": "Current price not available"}

    analysis: Dict[str, Any] = {}
    if target_mean:
        analysis["mean_target_upside"] = ((target_mean - current_price) / current_price) * 100
    if target_high:
        analysis["max_upside"] = ((target_high - current_price) / current_price) * 100
    if target_low:
        analysis["downside_risk"] = ((target_low - current_price) / current_price) * 100

    if target_high and target_low:
        downside_risk = current_price - target_low
        if downside_risk > 0:
            rr = (target_high - current_price) / downside_risk
            analysis["risk_reward_ratio"] = rr
            analysis["risk_assessment"] = (
                "Favorable risk-reward" if rr > 3 else
                "Balanced risk-reward" if rr > 1.5 else
                "Limited upside vs risk"
            )
    return analysis


async def analyze_analyst_recommendations(ticker: str) -> Dict[str, Any]:
    """Retrieve and analyze consensus analyst recommendations."""
    try:
        company_info = await fetch_info(ticker)
        current_price = _safe_float(company_info.get("currentPrice") or company_info.get("regularMarketPrice"))
        # Log the fetched current price for debugging
        logger.info(f"Fetched currentPrice for analyst recommendations: {current_price}")
        recommendation_key = company_info.get("recommendationKey", "").lower()
        recommendation_mean = _safe_float(company_info.get("recommendationMean"))
        target_high = _safe_float(company_info.get("targetHighPrice"))
        target_low = _safe_float(company_info.get("targetLowPrice"))
        target_mean = _safe_float(company_info.get("targetMeanPrice"))
        target_median = _safe_float(company_info.get("targetMedianPrice"))
        analyst_count = company_info.get("numberOfAnalystOpinions")

        recent_recommendations, recent_changes, data_freshness = [], [], {}
        try:
            loop = asyncio.get_event_loop()
            ticker_obj = await loop.run_in_executor(None, lambda: yf.Ticker(ticker))
            recs_df = await loop.run_in_executor(None, lambda: getattr(ticker_obj, "recommendations", None))
            upgrades_df = await loop.run_in_executor(None, lambda: getattr(ticker_obj, "upgrades_downgrades", None))

            if recs_df is not None and not recs_df.empty:
                recent_recs = recs_df.tail(10)
                for idx, row in recent_recs.iterrows():
                    recent_recommendations.append({
                        "date": _parse_index_date(idx),
                        **{k: int(row.get(k, 0) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
                    })

                latest_date = pd.to_datetime(str(recent_recs.index[-1])).date()
                oldest_date = pd.to_datetime(str(recent_recs.index[0])).date()
                days_old = (datetime.now().date() - latest_date).days
                data_freshness = {
                    "latest_recommendation_date": latest_date.isoformat(),
                    "oldest_recommendation_date": oldest_date.isoformat(),
                    "days_since_latest": days_old,
                    "data_span_days": (latest_date - oldest_date).days,
                    "freshness_status": "Current" if days_old <= 30 else "Stale" if days_old <= 90 else "Outdated",
                }

            if upgrades_df is not None and not upgrades_df.empty:
                for idx, row in upgrades_df.tail(5).iterrows():
                    recent_changes.append({
                        "date": _parse_index_date(idx),
                        "firm": row.get("Firm", "Unknown"),
                        "action": row.get("Action", ""),
                        "fromGrade": row.get("From Grade", ""),
                        "toGrade": row.get("To Grade", ""),
                    })
        except Exception as e:
            data_freshness = {"error": f"Failed to extract dates: {e}"}

        consensus = _calculate_consensus(
            current_price, target_mean, target_high, target_low,
            target_median, recommendation_mean, recommendation_key, recent_recommendations
        )

        return {
            "current_price": current_price,
            "target_prices": {"mean": target_mean, "median": target_median, "high": target_high, "low": target_low},
            "recommendation_summary": {
                "consensus": recommendation_key.title() if recommendation_key else "N/A",
                "mean_rating": recommendation_mean,
                "analyst_count": analyst_count,
            },
            "recent_recommendations": recent_recommendations[-1] if recent_recommendations else {},
            "all_recommendations": recent_recommendations,
            "recent_changes": recent_changes,
            "data_freshness": data_freshness,
            "consensus_analysis": consensus,
            "price_target_analysis": _analyze_price_targets(current_price, target_mean, target_high, target_low),
            "summary": consensus.get("summary", "Limited analyst data available"),
            "data_as_of": datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            "current_price": None,
            "target_prices": {},
            "recommendation_summary": {},
            "recent_recommendations": {},
            "recent_changes": [],
            "consensus_analysis": {},
            "price_target_analysis": {},
            "summary": f"Unable to retrieve analyst data: {e}",
        }
