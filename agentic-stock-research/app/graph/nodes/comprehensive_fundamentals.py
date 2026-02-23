"""
Comprehensive Fundamentals Analysis Node - Phase 2 Enhanced
Integrates DCF valuation, governance analysis, comprehensive scoring, and deep financial analysis.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.comprehensive_scoring import score_stock_comprehensively
from app.tools.dcf_valuation import perform_dcf_valuation
from app.tools.governance_analysis import analyze_corporate_governance
from app.tools.indian_market_data import get_indian_market_data
from app.tools.fundamentals import compute_fundamentals
from app.tools.deep_financial_analysis import DeepFinancialAnalyzer

logger = logging.getLogger(__name__)


def _assess_overall_data_quality(results: list) -> str:
    rate = sum(1 for r in results if not isinstance(r, Exception)) / len(results)
    return "high" if rate >= 0.8 else "medium" if rate >= 0.6 else "low"


def _generate_key_insights(basic: Dict, dcf: Dict, gov: Dict, indian: Dict, score: Any) -> List[str]:
    insights = []
    try:
        if basic:
            roe = basic.get("roe", 0) or 0
            de = basic.get("debtToEquity", 0) or 0
            if roe > 15.0:
                insights.append(f"💪 Strong ROE of {roe:.1f}% indicates efficient capital utilization")
            elif roe < 8.0:
                insights.append(f"⚠️ Weak ROE of {roe:.1f}% suggests capital efficiency concerns")
            if de < 50:
                insights.append("💰 Conservative leverage profile provides financial stability")
            elif de > 100:
                insights.append("⚠️ High leverage increases financial risk")

        if "error" not in dcf:
            mos = dcf.get("margin_of_safety", 0)
            iv = dcf.get("intrinsic_value", 0)
            cp = dcf.get("current_price", 0)
            if mos > 0.2:
                insights.append(f"🎯 Attractive valuation with {mos*100:.1f}% margin of safety")
            elif mos < 0:
                insights.append(f"💸 Currently overvalued by {abs(mos)*100:.1f}%")
            if iv and cp:
                upside = (iv - cp) / cp
                if upside > 0.25:
                    insights.append(f"🚀 Significant upside potential of {upside*100:.1f}% to intrinsic value")

        if gov and "error" not in gov:
            gs = gov.get("governance_score", 50)
            if gs >= 80:
                insights.append("✅ Excellent corporate governance standards")
            elif gs < 60:
                insights.append("🔴 Governance concerns require careful monitoring")
            critical = [rf for rf in gov.get("red_flags", []) if rf.get("severity") == "Critical"]
            if critical:
                insights.append(f"🚨 {len(critical)} critical governance red flag(s) identified")

        if "error" not in indian:
            sp = indian.get("shareholding_pattern", {}).get("latest")
            if sp:
                pledge = sp.get("promoter_pledge_pct", 0)
                if pledge > 50:
                    insights.append(f"⚠️ High promoter pledge at {pledge:.1f}% indicates stress")
                elif pledge == 0:
                    insights.append("✅ Zero promoter pledge indicates strong promoter confidence")

        if score:
            if score.overall_score >= 80:
                insights.append("⭐ High-quality investment opportunity with strong fundamentals")
            elif score.overall_score < 50:
                insights.append("⚠️ Below-average fundamentals suggest caution")
            if score.confidence_level >= 0.8:
                insights.append("📊 High confidence in analysis due to comprehensive data availability")
            elif score.confidence_level < 0.5:
                insights.append("📉 Limited data availability reduces analysis confidence")
    except Exception as e:
        logger.error(f"Failed to generate insights: {e}")
        insights.append("⚠️ Analysis completed with limited insights due to data constraints")
    return insights[:8]


def _pillar(score: Any, pillar_name: str) -> Dict:
    pillar = getattr(score, pillar_name) if score else None
    return {
        "score": pillar.score if pillar else 50.0,
        "confidence": pillar.confidence if pillar else 0.5,
        "key_metrics": pillar.key_metrics if pillar else {},
        "positive_factors": pillar.positive_factors if pillar else [],
        "negative_factors": pillar.negative_factors if pillar else [],
    }


async def comprehensive_fundamentals_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]

    # Resolve current price from state
    current_price: Optional[float] = None
    tech_data = state.get("analysis", {}).get("technicals", {})
    current_price = (tech_data.get("currentPrice") or tech_data.get("current_price") or
                     tech_data.get("details", {}).get("indicators", {}).get("last_close"))

    logger.info(f"Fetched currentPrice from tech_data of {ticker}: {current_price}")

    if not current_price:
        raw = state.get("raw_data", {})
        td = raw.get(ticker) or (raw if "info" in raw or "ohlcv_summary" in raw else None)
        if td is None:
            keys = list(raw.keys())
            td = raw[keys[0]] if len(keys) == 1 else None
        if td:
            info = td.get("info", {})
            current_price = (info.get("currentPrice") or info.get("regularMarketPrice") or
                             info.get("price") or td.get("ohlcv_summary", {}).get("last_close"))
            logger.info(f"Fetched currentPrice from raw_data of {ticker}: {current_price}")

    if not current_price:
        try:
            from app.tools.finance import fetch_info
            info = await fetch_info(ticker)
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            logger.info(f"Fetched currentPrice from fetch_info: {current_price}")
        except Exception as e:
            logger.error(f"Error fetching currentPrice for {ticker}: {e}")

    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                compute_fundamentals(ticker),
                perform_dcf_valuation(ticker, current_price),
                analyze_corporate_governance(ticker),
                get_indian_market_data(ticker),
                score_stock_comprehensively(ticker, current_price),
                DeepFinancialAnalyzer().analyze_financial_history(ticker, years_back=10),
                return_exceptions=True,
            ),
            timeout=60.0,
        )

        basic, dcf_raw, gov, indian, score, deep = (
            r if not isinstance(r, Exception) else ({} if i != 4 else None)
            for i, r in enumerate(results)
        )

        # Normalize DCF output
        dcf: Dict = {}
        if hasattr(dcf_raw, "intrinsic_value_per_share"):
            dcf = {
                "intrinsic_value": dcf_raw.intrinsic_value_per_share,
                "target_price": dcf_raw.intrinsic_value_per_share * 1.20,
                "enterprise_value": dcf_raw.enterprise_value,
                "equity_value": dcf_raw.equity_value,
                "wacc": dcf_raw.wacc,
                "terminal_growth": dcf_raw.terminal_growth,
                "margin_of_safety": dcf_raw.margin_of_safety,
                "upside_potential": dcf_raw.upside_potential,
                "shares_outstanding": dcf_raw.shares_outstanding,
                "net_debt": dcf_raw.net_debt,
                "pv_explicit_period": dcf_raw.pv_explicit_period,
                "pv_terminal_value": dcf_raw.pv_terminal_value,
            }
        elif isinstance(dcf_raw, dict):
            dcf = dcf_raw

        analysis = {
            "ticker": ticker,
            "current_price": current_price,
            "basic_fundamentals": basic,
            "dcf_valuation": dcf,
            "governance_analysis": gov,
            "indian_market_data": indian,
            "deep_financial_analysis": deep,
            "overall_score": score.overall_score if score else 50.0,
            "overall_grade": score.overall_grade if score else "C",
            "recommendation": score.recommendation if score else "Hold",
            "confidence_level": score.confidence_level if score else 0.5,
            "pillar_scores": {
                "financial_health": _pillar(score, "financial_health"),
                "valuation": _pillar(score, "valuation"),
                "growth_prospects": _pillar(score, "growth_prospects"),
                "governance": _pillar(score, "governance"),
                "macro_sensitivity": _pillar(score, "macro_sensitivity"),
            },
            "trading_recommendations": {
                "position_sizing_pct": score.position_sizing_pct if score else 1.0,
                "entry_zone": score.entry_zone if score else (0.0, 0.0),
                "entry_explanation": getattr(score, "entry_explanation", "Entry zone calculated using technical analysis"),
                "target_price": score.target_price if score else 0.0,
                "stop_loss": score.stop_loss if score else 0.0,
                "time_horizon_months": score.time_horizon_months if score else 12,
            },
            "risk_assessment": {
                "risk_rating": score.risk_rating if score else "Medium",
                "key_risks": score.key_risks if score else [],
                "key_catalysts": score.key_catalysts if score else [],
            },
            "key_insights": _generate_key_insights(basic, dcf, gov, indian, score),
            "data_quality": {
                "basic_fundamentals": "high" if basic else "low",
                "dcf_valuation": "high" if "error" not in dcf else "low",
                "governance": "medium" if gov else "low",
                "indian_data": "medium" if "error" not in indian else "low",
                "deep_financial_analysis": "high" if deep and "summary" in deep else "low",
                "overall_quality": _assess_overall_data_quality(results),
            },
        }

        state.setdefault("analysis", {})["fundamentals"] = analysis
        state.setdefault("analysis", {})["comprehensive_fundamentals"] = analysis
        state.setdefault("confidences", {})["fundamentals"] = score.confidence_level if score else 0.5
        logger.info(f"Comprehensive fundamentals completed for {ticker} "
                    f"(Score: {analysis['overall_score']}, Grade: {analysis['overall_grade']})")

    except Exception as e:
        logger.error(f"Comprehensive fundamental analysis failed for {ticker}: {e}")
        state.setdefault("analysis", {})["fundamentals"] = {
            "ticker": ticker, "error": str(e),
            "overall_score": 50.0, "overall_grade": "C",
            "recommendation": "Hold", "confidence_level": 0.1,
        }
        state.setdefault("confidences", {})["fundamentals"] = 0.1

    return state
