"""Enhanced Synthesis Node with Institutional-Grade Analysis."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import AppSettings
from app.graph.state import ResearchState
from app.graph.nodes.synthesis_common import convert_numpy_types, safe_get
from app.tools.institutional_analysis import institutional_engine
from app.tools.horizon_filtering import horizon_engine, AnalysisHorizon
from app.schemas.institutional_output import InstitutionalTickerReport, InstitutionalResearchResponse

logger = logging.getLogger(__name__)


def _convert_to_section_score(data: Dict[str, Any]) -> Any:
    from app.schemas.output import SectionScore
    if not data:
        return SectionScore(summary="Analysis pending", confidence=0.5)
    return SectionScore(summary=data.get("summary", "Analysis completed"),
                        confidence=data.get("confidence", 0.5), details=data.get("details", data))


def _extract_section_scores(analysis: Dict) -> Dict[str, float]:
    sections = ["news_sentiment", "youtube", "technicals", "fundamentals", "peer_analysis",
                "analyst_recommendations", "cashflow", "leadership", "sector_macro",
                "growth_prospects", "valuation"]
    return {
        s: float((analysis.get(s) or {}).get("score") or
                 (analysis.get(s) or {}).get("confidence") or 0.5)
        for s in sections
    }


def _extract_data_sources(analysis: Dict) -> List[str]:
    mapping = [("fundamentals", "Yahoo Finance"), ("news_sentiment", "News APIs"),
               ("technicals", "Technical Analysis"), ("analyst_recommendations", "Analyst Data")]
    return [label for key, label in mapping if analysis.get(key)] or ["Multiple Sources"]


def _assess_overall_data_quality(state: ResearchState) -> Dict[str, Any]:
    tickers = state.get("tickers", [])
    all_conf = [v for t in tickers for v in state.get("confidences", {}).get(t, {}).values()]
    if not all_conf:
        return {"overall_quality": "Unknown", "confidence": 0.5}
    avg = sum(all_conf) / len(all_conf)
    quality = "High" if avg >= 0.8 else "Medium" if avg >= 0.6 else "Low"
    return {"overall_quality": quality, "average_confidence": avg,
            "tickers_analyzed": len(tickers), "data_completeness": f"{len(all_conf)}/{len(tickers)*10} sections"}


async def _create_institutional_report(ticker: str, analysis: Dict, decision: Any, state: ResearchState) -> InstitutionalTickerReport:
    info = analysis.get("company_info", {})
    sections = ["news_sentiment", "youtube", "technicals", "fundamentals", "peer_analysis",
                "analyst_recommendations", "cashflow", "leadership", "sector_macro",
                "growth_prospects", "valuation", "strategic_conviction", "sector_rotation"]
    kwargs = {s: _convert_to_section_score(analysis.get(s, {})) for s in sections}
    return InstitutionalTickerReport(
        ticker=ticker,
        company_name=info.get("name", f"{ticker} Corporation"),
        sector=info.get("sector", "Unknown"),
        country=info.get("country", "Unknown"),
        exchange=info.get("exchange", "Unknown"),
        decision=decision,
        earnings_call_analysis=analysis.get("earnings_call_analysis"),
        comprehensive_fundamentals=analysis.get("comprehensive_fundamentals"),
        data_sources=_extract_data_sources(analysis),
        **kwargs,
    )


def _create_legacy_output(state: ResearchState, reports: List[Any]) -> Dict:
    tickers = state.get("tickers", [])
    _fields = ["news_sentiment", "youtube_sentiment", "technicals", "fundamentals",
               "peer_analysis", "analyst_recommendations", "cashflow", "leadership",
               "sector_macro", "growth_prospects", "valuation"]
    legacy_reports = []
    for i, ticker in enumerate(tickers):
        if i >= len(reports): continue
        r = reports[i]
        report: Dict[str, Any] = {"ticker": ticker,
                                   "executive_summary": r.decision.investment_summary.executive_summary}
        for field in _fields:
            section = getattr(r, field, None) or getattr(r, field.replace("youtube_sentiment", "youtube_sentiment"), None)
            if section:
                report[field] = {"summary": section.summary, "confidence": section.confidence, "details": section.details}
        report["decision"] = {
            "action": r.decision.investment_summary.recommendation.value,
            "rating": r.decision.investment_summary.confidence_score / 20,
            "expected_return_pct": r.decision.valuation_metrics.expected_return_long_term or 0,
            "top_reasons_for": r.decision.investment_summary.key_investment_thesis,
            "top_reasons_against": r.decision.investment_summary.key_risks,
            "letter_grade": r.decision.investment_summary.letter_grade.value,
            "stars": r.decision.investment_summary.stars_rating,
            "professional_rationale": r.decision.investment_summary.analyst_notes,
            "executive_summary": r.decision.investment_summary.executive_summary,
            "short_term_outlook": r.decision.short_term_analysis.analyst_outlook,
            "long_term_outlook": r.decision.long_term_analysis.analyst_outlook,
        }
        legacy_reports.append(report)
    return {"tickers": tickers, "reports": legacy_reports, "generated_at": datetime.now(timezone.utc).isoformat()}


async def enhanced_synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    try:
        tickers = state.get("tickers", [])
        short_days = state.get("horizon_short_days", 180)
        long_days = state.get("horizon_long_days", 1095)
        short_horizon, long_horizon = horizon_engine.determine_horizons(short_days, long_days)

        reports = []
        for ticker in tickers:
            analysis = state.get("ticker_analysis", {}).get(ticker, {})
            confidences = state.get("confidences", {}).get(ticker, {})
            _, short_conf = horizon_engine.apply_horizon_filtering(analysis, short_horizon, confidences)
            _, long_conf  = horizon_engine.apply_horizon_filtering(analysis, long_horizon, confidences)
            section_scores = _extract_section_scores(analysis)
            horizon_engine.calculate_horizon_weighted_score(section_scores, short_conf, short_horizon)
            horizon_engine.calculate_horizon_weighted_score(section_scores, long_conf, long_horizon)
            decision = await institutional_engine.generate_institutional_summary(ticker, analysis, short_days, long_days)
            report = await _create_institutional_report(ticker, analysis, decision, state)
            reports.append(report)

        institutional_response = InstitutionalResearchResponse(
            tickers=tickers, analysis_horizon_short_days=short_days,
            analysis_horizon_long_days=long_days, reports=reports,
            data_quality_summary=_assess_overall_data_quality(state),
        )
        state["final_output"] = _create_legacy_output(state, reports)
        state["institutional_output"] = institutional_response
    except Exception as e:
        logger.error(f"Error in enhanced synthesis: {e}")
        from app.graph.nodes.synthesis import synthesis_node as original
        return await original(state, settings)
    return state


synthesis_node = enhanced_synthesis_node
