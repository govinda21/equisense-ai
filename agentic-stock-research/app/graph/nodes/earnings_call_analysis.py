"""Earnings Call Analysis Node"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.earnings_call_analyzer import analyze_earnings_calls

logger = logging.getLogger(__name__)


def _generate_summary_insights(aggregated: Dict, guidance: Dict, topics: List, concerns: List, initiatives: List) -> str:
    parts = []
    sentiment = aggregated.get("overall_sentiment", 0.0)
    confidence = aggregated.get("confidence_score", 0.0)
    defensiveness = aggregated.get("defensiveness_score", 0.0)

    parts.append("Management tone is generally positive." if sentiment > 0.2 else
                 "Management tone is cautious or negative." if sentiment < -0.2 else
                 "Management tone is neutral and balanced.")
    if confidence > 0.7:
        parts.append("Management demonstrates high confidence in business outlook.")
    elif confidence < 0.4:
        parts.append("Management shows low confidence or uncertainty.")
    if defensiveness > 0.6:
        parts.append("Management appears defensive in Q&A sessions.")
    elif defensiveness < 0.3:
        parts.append("Management is open and transparent with analysts.")
    if guidance.get("revenue"):
        parts.append(f"Revenue guidance provided in {len(guidance['revenue'])} call(s).")
    if guidance.get("earnings"):
        parts.append(f"Earnings guidance provided in {len(guidance['earnings'])} call(s).")
    if topics:
        parts.append(f"Key topics: {', '.join(topics[:3])}.")
    if concerns:
        parts.append(f"Main concerns: {', '.join(concerns[:2])}.")
    if initiatives:
        parts.append(f"New initiatives: {', '.join(initiatives[:2])}.")
    return " ".join(parts) if parts else "Limited insights available."


def _calculate_analysis_confidence(total_calls: int, sentiment_confidence: float, topics_count: int, guidance_count: int) -> float:
    if total_calls == 0:
        return 0.0
    calls_conf = min(1.0, total_calls / 3.0)
    content = min(1.0, (topics_count + guidance_count) / 10.0)
    return round(calls_conf * 0.3 + sentiment_confidence * 0.4 + content * 0.3, 2)


async def earnings_call_analysis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    try:
        earnings_analysis = await analyze_earnings_calls(ticker=ticker, days_back=180, max_calls=3)
        total_calls = earnings_analysis.get("total_calls", 0)
        call_data: Dict[str, Any] = {
            "ticker": ticker,
            "total_calls_analyzed": total_calls,
            "analysis_period": earnings_analysis.get("analysis_period", "180 days"),
            "sources_used": earnings_analysis.get("sources_used", []),
            "status": "success" if total_calls > 0 else "no_calls_found",
        }

        if total_calls > 0:
            aggregated = earnings_analysis.get("aggregated_sentiment", {})
            guidance = earnings_analysis.get("guidance_summary", {})
            topics = earnings_analysis.get("key_topics", [])
            concerns = earnings_analysis.get("common_concerns", [])
            initiatives = earnings_analysis.get("new_initiatives", [])
            call_data.update({
                "management_sentiment": {
                    "overall_sentiment": aggregated.get("overall_sentiment", 0.0),
                    "confidence_score": aggregated.get("confidence_score", 0.0),
                    "defensiveness_score": aggregated.get("defensiveness_score", 0.0),
                    "call_quality": aggregated.get("call_quality", 0.0),
                },
                "guidance_analysis": {
                    "revenue_guidance": guidance.get("revenue", []),
                    "earnings_guidance": guidance.get("earnings", []),
                    "margin_guidance": guidance.get("margins", []),
                    "capex_guidance": guidance.get("capex", []),
                },
                "key_insights": {"topics_discussed": topics, "concerns_raised": concerns, "new_initiatives": initiatives},
                "quarterly_trends": earnings_analysis.get("individual_analyses", []),
                "summary_insights": _generate_summary_insights(aggregated, guidance, topics, concerns, initiatives),
                "confidence_score": _calculate_analysis_confidence(
                    total_calls, aggregated.get("confidence_score", 0.0), len(topics), len(guidance.get("revenue", []))
                ),
            })
        else:
            is_indian = ".NS" in ticker.upper()
            call_data.update({
                "management_sentiment": {"overall_sentiment": 0.0, "confidence_score": 0.0,
                                         "defensiveness_score": 0.0, "call_quality": 0.0},
                "guidance_analysis": {},
                "key_insights": {"topics_discussed": [], "concerns_raised": [], "new_initiatives": []},
                "summary_insights": (
                    f"No earnings call transcripts available for {ticker}. Indian stock earnings call data is not available "
                    "through current free APIs. Consider premium data sources or company investor relations websites."
                    if is_indian else
                    f"No recent earnings call transcripts available for {ticker}."
                ),
                "confidence_score": 0.0,
            })

        state.setdefault("analysis", {})["earnings_calls"] = call_data
    except Exception as e:
        logger.error(f"Earnings call analysis failed for {ticker}: {e}", exc_info=True)
        state.setdefault("analysis", {})["earnings_calls"] = {
            "ticker": ticker, "error": str(e), "status": "failed",
            "total_calls_analyzed": 0, "confidence_score": 0.0,
        }
    return state


async def get_earnings_call_insights(ticker: str) -> Dict[str, Any]:
    result = await earnings_call_analysis_node({"tickers": [ticker], "analysis": {}}, None)
    return result.get("analysis", {}).get("earnings_calls", {})
