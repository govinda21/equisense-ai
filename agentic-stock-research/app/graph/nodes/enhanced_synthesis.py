"""
Enhanced Synthesis Node with Institutional-Grade Analysis
Phase 1: Core Investment Framework Integration
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import logging

from app.config import AppSettings
from app.graph.state import ResearchState
from app.graph.nodes.synthesis_common import (
    convert_numpy_types,
    score_to_action as _score_to_action,
    score_to_action_with_conviction as _score_to_action_with_conviction,
    score_to_letter_grade as _score_to_letter_grade,
    score_to_stars as _score_to_stars,
    format_currency,
    format_percentage,
    safe_get,
)
from app.tools.institutional_analysis import institutional_engine
from app.tools.horizon_filtering import horizon_engine, AnalysisHorizon
from app.schemas.institutional_output import InstitutionalTickerReport, InstitutionalResearchResponse

logger = logging.getLogger(__name__)


async def enhanced_synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Enhanced synthesis node with institutional-grade analysis
    
    Integrates:
    - Horizon filtering for short-term and long-term analysis
    - Institutional-grade investment summary
    - Professional valuation metrics
    - Enhanced decision framework
    """
    try:
        logger.info("Starting enhanced synthesis with institutional analysis")
        
        # Extract analysis parameters
        tickers = state.get("tickers", [])
        short_term_days = state.get("horizon_short_days", 180)
        long_term_days = state.get("horizon_long_days", 1095)
        
        # Determine analysis horizons
        short_horizon, long_horizon = horizon_engine.determine_horizons(short_term_days, long_term_days)
        
        # Process each ticker with institutional analysis
        institutional_reports = []
        
        for ticker in tickers:
            logger.info(f"Processing institutional analysis for {ticker}")
            
            # Extract ticker-specific data
            ticker_analysis = state.get("ticker_analysis", {}).get(ticker, {})
            confidences = state.get("confidences", {}).get(ticker, {})
            
            # Apply horizon filtering
            short_term_data, short_confidences = horizon_engine.apply_horizon_filtering(
                ticker_analysis, short_horizon, confidences
            )
            long_term_data, long_confidences = horizon_engine.apply_horizon_filtering(
                ticker_analysis, long_horizon, confidences
            )
            
            # Calculate horizon-weighted scores
            section_scores = _extract_section_scores(ticker_analysis)
            short_term_score = horizon_engine.calculate_horizon_weighted_score(
                section_scores, short_confidences, short_horizon
            )
            long_term_score = horizon_engine.calculate_horizon_weighted_score(
                section_scores, long_confidences, long_horizon
            )
            
            # Generate institutional decision
            institutional_decision = await institutional_engine.generate_institutional_summary(
                ticker, ticker_analysis, short_term_days, long_term_days
            )
            
            # Create institutional ticker report
            institutional_report = await _create_institutional_report(
                ticker, ticker_analysis, institutional_decision, state
            )
            
            institutional_reports.append(institutional_report)
            
            logger.info(f"Completed institutional analysis for {ticker}")
        
        # Create institutional research response
        institutional_response = InstitutionalResearchResponse(
            tickers=tickers,
            analysis_horizon_short_days=short_term_days,
            analysis_horizon_long_days=long_term_days,
            reports=institutional_reports,
            data_quality_summary=_assess_overall_data_quality(state)
        )
        
        # Store both legacy and institutional outputs
        state["final_output"] = _create_legacy_output(state, institutional_reports)
        state["institutional_output"] = institutional_response
        
        logger.info("Enhanced synthesis completed successfully")
        return state
        
    except Exception as e:
        logger.error(f"Error in enhanced synthesis: {str(e)}")
        # Fallback to original synthesis
        return await _fallback_synthesis(state, settings)


async def _create_institutional_report(
    ticker: str,
    ticker_analysis: Dict[str, Any],
    institutional_decision: Any,
    state: ResearchState
) -> InstitutionalTickerReport:
    """Create institutional ticker report"""
    
    # Extract company information
    company_info = ticker_analysis.get("company_info", {})
    
    return InstitutionalTickerReport(
        ticker=ticker,
        company_name=company_info.get("name", f"{ticker} Corporation"),
        sector=company_info.get("sector", "Unknown"),
        country=company_info.get("country", "Unknown"),
        exchange=company_info.get("exchange", "Unknown"),
        decision=institutional_decision,
        # Map existing sections to SectionScore format
        news_sentiment=_convert_to_section_score(ticker_analysis.get("news_sentiment", {})),
        youtube_sentiment=_convert_to_section_score(ticker_analysis.get("youtube", {})),
        technicals=_convert_to_section_score(ticker_analysis.get("technicals", {})),
        fundamentals=_convert_to_section_score(ticker_analysis.get("fundamentals", {})),
        peer_analysis=_convert_to_section_score(ticker_analysis.get("peer_analysis", {})),
        analyst_recommendations=_convert_to_section_score(ticker_analysis.get("analyst_recommendations", {})),
        cashflow=_convert_to_section_score(ticker_analysis.get("cashflow", {})),
        leadership=_convert_to_section_score(ticker_analysis.get("leadership", {})),
        sector_macro=_convert_to_section_score(ticker_analysis.get("sector_macro", {})),
        growth_prospects=_convert_to_section_score(ticker_analysis.get("growth_prospects", {})),
        valuation=_convert_to_section_score(ticker_analysis.get("valuation", {})),
        strategic_conviction=_convert_to_section_score(ticker_analysis.get("strategic_conviction", {})),
        earnings_call_analysis=ticker_analysis.get("earnings_call_analysis"),
        sector_rotation=_convert_to_section_score(ticker_analysis.get("sector_rotation", {})),
        comprehensive_fundamentals=ticker_analysis.get("comprehensive_fundamentals"),
        data_sources=_extract_data_sources(ticker_analysis)
    )


def _convert_to_section_score(data: Dict[str, Any]) -> Any:
    """Convert data to SectionScore format"""
    from app.schemas.output import SectionScore
    
    if not data:
        return SectionScore(summary="Analysis pending", confidence=0.5)
    
    return SectionScore(
        summary=data.get("summary", "Analysis completed"),
        confidence=data.get("confidence", 0.5),
        details=data.get("details", data)
    )


def _extract_section_scores(ticker_analysis: Dict[str, Any]) -> Dict[str, float]:
    """Extract section scores from ticker analysis"""
    section_scores = {}
    
    sections = [
        "news_sentiment", "youtube", "technicals", "fundamentals",
        "peer_analysis", "analyst_recommendations", "cashflow",
        "leadership", "sector_macro", "growth_prospects", "valuation"
    ]
    
    for section in sections:
        section_data = ticker_analysis.get(section, {})
        if isinstance(section_data, dict):
            # Try to extract score from various possible locations
            score = (section_data.get("score") or 
                    section_data.get("rating") or 
                    section_data.get("confidence") or 
                    0.5)
            section_scores[section] = float(score)
        else:
            section_scores[section] = 0.5
    
    return section_scores


def _extract_data_sources(ticker_analysis: Dict[str, Any]) -> List[str]:
    """Extract data sources used in analysis"""
    sources = []
    
    # Check for various data sources
    if ticker_analysis.get("fundamentals"):
        sources.append("Yahoo Finance")
    if ticker_analysis.get("news_sentiment"):
        sources.append("News APIs")
    if ticker_analysis.get("technicals"):
        sources.append("Technical Analysis")
    if ticker_analysis.get("analyst_recommendations"):
        sources.append("Analyst Data")
    
    return sources if sources else ["Multiple Sources"]


def _assess_overall_data_quality(state: ResearchState) -> Dict[str, Any]:
    """Assess overall data quality across all tickers"""
    tickers = state.get("tickers", [])
    confidences = state.get("confidences", {})
    
    if not tickers:
        return {"overall_quality": "Unknown", "confidence": 0.5}
    
    all_confidences = []
    for ticker in tickers:
        ticker_confidences = confidences.get(ticker, {})
        all_confidences.extend(ticker_confidences.values())
    
    if not all_confidences:
        return {"overall_quality": "Unknown", "confidence": 0.5}
    
    avg_confidence = sum(all_confidences) / len(all_confidences)
    
    if avg_confidence >= 0.8:
        quality = "High"
    elif avg_confidence >= 0.6:
        quality = "Medium"
    else:
        quality = "Low"
    
    return {
        "overall_quality": quality,
        "average_confidence": avg_confidence,
        "tickers_analyzed": len(tickers),
        "data_completeness": f"{len(all_confidences)}/{len(tickers) * 10} sections"
    }


def _create_legacy_output(state: ResearchState, institutional_reports: List[Any]) -> Dict[str, Any]:
    """Create legacy output format for backward compatibility"""
    
    # Extract original data for legacy format
    tickers = state.get("tickers", [])
    reports = []
    
    for i, ticker in enumerate(tickers):
        if i < len(institutional_reports):
            institutional_report = institutional_reports[i]
            
            # Convert institutional report to legacy format
            legacy_report = {
                "ticker": ticker,
                "executive_summary": institutional_report.decision.investment_summary.executive_summary,
                "news_sentiment": {
                    "summary": institutional_report.news_sentiment.summary,
                    "confidence": institutional_report.news_sentiment.confidence,
                    "details": institutional_report.news_sentiment.details
                },
                "youtube_sentiment": {
                    "summary": institutional_report.youtube_sentiment.summary,
                    "confidence": institutional_report.youtube_sentiment.confidence,
                    "details": institutional_report.youtube_sentiment.details
                },
                "technicals": {
                    "summary": institutional_report.technicals.summary,
                    "confidence": institutional_report.technicals.confidence,
                    "details": institutional_report.technicals.details
                },
                "fundamentals": {
                    "summary": institutional_report.fundamentals.summary,
                    "confidence": institutional_report.fundamentals.confidence,
                    "details": institutional_report.fundamentals.details
                },
                "peer_analysis": {
                    "summary": institutional_report.peer_analysis.summary,
                    "confidence": institutional_report.peer_analysis.confidence,
                    "details": institutional_report.peer_analysis.details
                },
                "analyst_recommendations": {
                    "summary": institutional_report.analyst_recommendations.summary,
                    "confidence": institutional_report.analyst_recommendations.confidence,
                    "details": institutional_report.analyst_recommendations.details
                },
                "cashflow": {
                    "summary": institutional_report.cashflow.summary,
                    "confidence": institutional_report.cashflow.confidence,
                    "details": institutional_report.cashflow.details
                },
                "leadership": {
                    "summary": institutional_report.leadership.summary,
                    "confidence": institutional_report.leadership.confidence,
                    "details": institutional_report.leadership.details
                },
                "sector_macro": {
                    "summary": institutional_report.sector_macro.summary,
                    "confidence": institutional_report.sector_macro.confidence,
                    "details": institutional_report.sector_macro.details
                },
                "growth_prospects": {
                    "summary": institutional_report.growth_prospects.summary,
                    "confidence": institutional_report.growth_prospects.confidence,
                    "details": institutional_report.growth_prospects.details
                },
                "valuation": {
                    "summary": institutional_report.valuation.summary,
                    "confidence": institutional_report.valuation.confidence,
                    "details": institutional_report.valuation.details
                },
                "decision": {
                    "action": institutional_report.decision.investment_summary.recommendation.value,
                    "rating": institutional_report.decision.investment_summary.confidence_score / 20,  # Convert to 0-5 scale
                    "expected_return_pct": institutional_report.decision.valuation_metrics.expected_return_long_term or 0,
                    "top_reasons_for": institutional_report.decision.investment_summary.key_investment_thesis,
                    "top_reasons_against": institutional_report.decision.investment_summary.key_risks,
                    "letter_grade": institutional_report.decision.investment_summary.letter_grade.value,
                    "stars": institutional_report.decision.investment_summary.stars_rating,
                    "professional_rationale": institutional_report.decision.investment_summary.analyst_notes,
                    "executive_summary": institutional_report.decision.investment_summary.executive_summary,
                    "short_term_outlook": institutional_report.decision.short_term_analysis.analyst_outlook,
                    "long_term_outlook": institutional_report.decision.long_term_analysis.analyst_outlook
                }
            }
            
            reports.append(legacy_report)
    
    return {
        "tickers": tickers,
        "reports": reports,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


async def _fallback_synthesis(state: ResearchState, settings: AppSettings) -> ResearchState:
    """Fallback to original synthesis if institutional analysis fails"""
    logger.warning("Falling back to original synthesis")
    
    # Import and use original synthesis
    from app.graph.nodes.synthesis import synthesis_node as original_synthesis
    return await original_synthesis(state, settings)


# Export the enhanced synthesis function
synthesis_node = enhanced_synthesis_node
