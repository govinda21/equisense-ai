"""
Comprehensive Fundamentals Analysis Node
Integrates DCF valuation, governance analysis, and comprehensive scoring
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.comprehensive_scoring import score_stock_comprehensively
from app.tools.dcf_valuation import perform_dcf_valuation
from app.tools.governance_analysis import analyze_corporate_governance
from app.tools.indian_market_data import get_indian_market_data
from app.tools.fundamentals import compute_fundamentals

logger = logging.getLogger(__name__)


async def comprehensive_fundamentals_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Comprehensive fundamentals analysis node that performs:
    1. Basic fundamental metrics calculation
    2. DCF valuation with scenario analysis
    3. Corporate governance assessment
    4. Indian market-specific data integration
    5. Multi-dimensional scoring and ranking
    """
    ticker = state["tickers"][0]
    logger.info(f"Starting comprehensive fundamental analysis for {ticker}")
    
    try:
        # Get current price if available from previous analysis or fetch it directly
        current_price = None
        
        # Try to get current price from technicals first
        if "analysis" in state and "technicals" in state["analysis"]:
            tech_data = state["analysis"]["technicals"]
            # Try multiple possible locations for current price
            current_price = (
                tech_data.get("currentPrice") or 
                tech_data.get("current_price") or
                tech_data.get("details", {}).get("indicators", {}).get("last_close")
            )
        
        # If not found, try to fetch from raw data
        if not current_price and "raw_data" in state:
            for ticker_data in state["raw_data"].values():
                if isinstance(ticker_data, dict):
                    current_price = (
                        ticker_data.get("currentPrice") or 
                        ticker_data.get("regularMarketPrice") or
                        ticker_data.get("price")
                    )
                    if current_price:
                        break
        
        # Last resort: try to fetch current price using rate-limited client
        if not current_price:
            try:
                from app.tools.finance import fetch_info
                info = await fetch_info(ticker)
                current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                logger.info(f"Fetched current price from yfinance for {ticker}: {current_price}")
            except Exception as e:
                logger.warning(f"Failed to fetch current price from yfinance for {ticker}: {e}")
        
        # Log the current price for debugging
        logger.info(f"Current price for {ticker}: {current_price}")
        
        # Parallel execution of all analysis components with timeout control
        analysis_results = await asyncio.wait_for(
            asyncio.gather(
                compute_fundamentals(ticker),
                perform_dcf_valuation(ticker, current_price),
                analyze_corporate_governance(ticker),
                get_indian_market_data(ticker),
                score_stock_comprehensively(ticker, current_price),
                return_exceptions=True
            ),
            timeout=45.0  # 45 second timeout for all fundamental analysis
        )
        
        # Process results
        basic_fundamentals = analysis_results[0] if not isinstance(analysis_results[0], Exception) else {}
        dcf_valuation_raw = analysis_results[1] if not isinstance(analysis_results[1], Exception) else {}
        governance_analysis = analysis_results[2] if not isinstance(analysis_results[2], Exception) else {}
        indian_market_data = analysis_results[3] if not isinstance(analysis_results[3], Exception) else {}
        comprehensive_score = analysis_results[4] if not isinstance(analysis_results[4], Exception) else None
        
        # Convert DCFOutputs to dictionary with expected keys
        dcf_valuation = {}
        if hasattr(dcf_valuation_raw, 'intrinsic_value_per_share'):
            dcf_valuation = {
                "intrinsic_value": dcf_valuation_raw.intrinsic_value_per_share,
                "target_price": dcf_valuation_raw.intrinsic_value_per_share * 1.20,  # 20% premium
                "enterprise_value": dcf_valuation_raw.enterprise_value,
                "equity_value": dcf_valuation_raw.equity_value,
                "wacc": dcf_valuation_raw.wacc,
                "terminal_growth": dcf_valuation_raw.terminal_growth,
                "margin_of_safety": dcf_valuation_raw.margin_of_safety,
                "upside_potential": dcf_valuation_raw.upside_potential,
                "shares_outstanding": dcf_valuation_raw.shares_outstanding,
                "net_debt": dcf_valuation_raw.net_debt,
                "pv_explicit_period": dcf_valuation_raw.pv_explicit_period,
                "pv_terminal_value": dcf_valuation_raw.pv_terminal_value
            }
        elif isinstance(dcf_valuation_raw, dict):
            dcf_valuation = dcf_valuation_raw
        
        # Log any failures
        for i, result in enumerate(analysis_results):
            if isinstance(result, Exception):
                component_names = ["basic_fundamentals", "dcf_valuation", "governance_analysis", 
                                 "indian_market_data", "comprehensive_score"]
                logger.error(f"Failed to compute {component_names[i]} for {ticker}: {result}")
        
        # Compile comprehensive analysis
        comprehensive_analysis = {
            "ticker": ticker,
            "analysis_timestamp": analysis_results[4].ticker if comprehensive_score else None,
            "current_price": current_price,
            
            # Core metrics
            "basic_fundamentals": basic_fundamentals,
            "dcf_valuation": dcf_valuation,
            "governance_analysis": governance_analysis,
            "indian_market_data": indian_market_data,
            
            # Comprehensive scoring
            "overall_score": comprehensive_score.overall_score if comprehensive_score else 50.0,
            "overall_grade": comprehensive_score.overall_grade if comprehensive_score else "C",
            "recommendation": comprehensive_score.recommendation if comprehensive_score else "Hold",
            "confidence_level": comprehensive_score.confidence_level if comprehensive_score else 0.5,
            
            # Pillar scores
            "pillar_scores": {
                "financial_health": {
                    "score": comprehensive_score.financial_health.score if comprehensive_score else 50.0,
                    "confidence": comprehensive_score.financial_health.confidence if comprehensive_score else 0.5,
                    "key_metrics": comprehensive_score.financial_health.key_metrics if comprehensive_score else {},
                    "positive_factors": comprehensive_score.financial_health.positive_factors if comprehensive_score else [],
                    "negative_factors": comprehensive_score.financial_health.negative_factors if comprehensive_score else []
                },
                "valuation": {
                    "score": comprehensive_score.valuation.score if comprehensive_score else 50.0,
                    "confidence": comprehensive_score.valuation.confidence if comprehensive_score else 0.5,
                    "key_metrics": comprehensive_score.valuation.key_metrics if comprehensive_score else {},
                    "positive_factors": comprehensive_score.valuation.positive_factors if comprehensive_score else [],
                    "negative_factors": comprehensive_score.valuation.negative_factors if comprehensive_score else []
                },
                "growth_prospects": {
                    "score": comprehensive_score.growth_prospects.score if comprehensive_score else 50.0,
                    "confidence": comprehensive_score.growth_prospects.confidence if comprehensive_score else 0.5,
                    "key_metrics": comprehensive_score.growth_prospects.key_metrics if comprehensive_score else {},
                    "positive_factors": comprehensive_score.growth_prospects.positive_factors if comprehensive_score else [],
                    "negative_factors": comprehensive_score.growth_prospects.negative_factors if comprehensive_score else []
                },
                "governance": {
                    "score": comprehensive_score.governance.score if comprehensive_score else 50.0,
                    "confidence": comprehensive_score.governance.confidence if comprehensive_score else 0.5,
                    "key_metrics": comprehensive_score.governance.key_metrics if comprehensive_score else {},
                    "positive_factors": comprehensive_score.governance.positive_factors if comprehensive_score else [],
                    "negative_factors": comprehensive_score.governance.negative_factors if comprehensive_score else []
                },
                "macro_sensitivity": {
                    "score": comprehensive_score.macro_sensitivity.score if comprehensive_score else 50.0,
                    "confidence": comprehensive_score.macro_sensitivity.confidence if comprehensive_score else 0.5,
                    "key_metrics": comprehensive_score.macro_sensitivity.key_metrics if comprehensive_score else {},
                    "positive_factors": comprehensive_score.macro_sensitivity.positive_factors if comprehensive_score else [],
                    "negative_factors": comprehensive_score.macro_sensitivity.negative_factors if comprehensive_score else []
                }
            },
            
            # Trading recommendations
            "trading_recommendations": {
                "position_sizing_pct": comprehensive_score.position_sizing_pct if comprehensive_score else 1.0,
                "entry_zone": comprehensive_score.entry_zone if comprehensive_score else (0.0, 0.0),
                "entry_explanation": getattr(comprehensive_score, 'entry_explanation', 'Entry zone calculated using technical analysis'),
                "target_price": comprehensive_score.target_price if comprehensive_score else 0.0,
                "stop_loss": comprehensive_score.stop_loss if comprehensive_score else 0.0,
                "time_horizon_months": comprehensive_score.time_horizon_months if comprehensive_score else 12
            },
            
            # Risk assessment
            "risk_assessment": {
                "risk_rating": comprehensive_score.risk_rating if comprehensive_score else "Medium",
                "key_risks": comprehensive_score.key_risks if comprehensive_score else [],
                "key_catalysts": comprehensive_score.key_catalysts if comprehensive_score else []
            },
            
            # Key insights summary
            "key_insights": _generate_key_insights(
                basic_fundamentals, dcf_valuation, governance_analysis, 
                indian_market_data, comprehensive_score
            ),
            
            # Data quality indicators
            "data_quality": {
                "basic_fundamentals": "high" if basic_fundamentals else "low",
                "dcf_valuation": "high" if "error" not in dcf_valuation else "low",
                "governance": "medium" if governance_analysis else "low",
                "indian_data": "medium" if "error" not in indian_market_data else "low",
                "overall_quality": _assess_overall_data_quality(analysis_results)
            }
        }
        
        # Update state with comprehensive analysis
        state.setdefault("analysis", {})["comprehensive_fundamentals"] = comprehensive_analysis
        
        # Set confidence based on comprehensive scoring confidence
        confidence = comprehensive_score.confidence_level if comprehensive_score else 0.5
        state.setdefault("confidences", {})["fundamentals"] = confidence
        
        logger.info(f"Comprehensive fundamental analysis completed for {ticker} "
                   f"(Score: {comprehensive_analysis['overall_score']}, "
                   f"Grade: {comprehensive_analysis['overall_grade']}, "
                   f"Recommendation: {comprehensive_analysis['recommendation']})")
        
        return state
        
    except Exception as e:
        logger.error(f"Comprehensive fundamental analysis failed for {ticker}: {e}")
        
        # Fallback analysis with error information
        state.setdefault("analysis", {})["fundamentals"] = {
            "ticker": ticker,
            "error": str(e),
            "overall_score": 50.0,
            "overall_grade": "C",
            "recommendation": "Hold",
            "confidence_level": 0.1
        }
        state.setdefault("confidences", {})["fundamentals"] = 0.1
        
        return state


def _generate_key_insights(
    basic_fundamentals: Dict[str, Any],
    dcf_valuation: Dict[str, Any],
    governance_analysis: Dict[str, Any],
    indian_market_data: Dict[str, Any],
    comprehensive_score: Any
) -> List[str]:
    """Generate key insights from comprehensive analysis"""
    insights = []
    
    try:
        # Financial health insights
        if basic_fundamentals:
            roe = basic_fundamentals.get("roe", 0) or 0
            if roe > 15.0:  # ROE is stored as percentage (15.0 not 0.15)
                insights.append(f"💪 Strong ROE of {roe:.1f}% indicates efficient capital utilization")
            elif roe < 8.0:  # ROE is stored as percentage
                insights.append(f"⚠️ Weak ROE of {roe:.1f}% suggests capital efficiency concerns")
            
            debt_equity = basic_fundamentals.get("debtToEquity", 0) or 0
            if debt_equity < 50:
                insights.append("💰 Conservative leverage profile provides financial stability")
            elif debt_equity > 100:
                insights.append("⚠️ High leverage increases financial risk")
        
        # Valuation insights
        if "error" not in dcf_valuation:
            margin_of_safety = dcf_valuation.get("margin_of_safety", 0)
            if margin_of_safety > 0.2:
                insights.append(f"🎯 Attractive valuation with {margin_of_safety*100:.1f}% margin of safety")
            elif margin_of_safety < 0:
                insights.append(f"💸 Currently overvalued by {abs(margin_of_safety)*100:.1f}%")
            
            intrinsic_value = dcf_valuation.get("intrinsic_value", 0)
            current_price = dcf_valuation.get("current_price", 0)
            if intrinsic_value and current_price:
                upside = (intrinsic_value - current_price) / current_price
                if upside > 0.25:
                    insights.append(f"🚀 Significant upside potential of {upside*100:.1f}% to intrinsic value")
        
        # Governance insights
        if governance_analysis and "error" not in governance_analysis:
            governance_score = governance_analysis.get("governance_score", 50)
            if governance_score >= 80:
                insights.append("✅ Excellent corporate governance standards")
            elif governance_score < 60:
                insights.append("🔴 Governance concerns require careful monitoring")
            
            red_flags = governance_analysis.get("red_flags", [])
            critical_flags = [rf for rf in red_flags if rf.get("severity") == "Critical"]
            if critical_flags:
                insights.append(f"🚨 {len(critical_flags)} critical governance red flag(s) identified")
        
        # Indian market specific insights
        if "error" not in indian_market_data:
            shareholding = indian_market_data.get("shareholding_pattern", {}).get("latest")
            if shareholding:
                promoter_pledge = shareholding.get("promoter_pledge_pct", 0)
                if promoter_pledge > 50:
                    insights.append(f"⚠️ High promoter pledge at {promoter_pledge:.1f}% indicates stress")
                elif promoter_pledge == 0:
                    insights.append("✅ Zero promoter pledge indicates strong promoter confidence")
        
        # Overall scoring insights
        if comprehensive_score:
            if comprehensive_score.overall_score >= 80:
                insights.append("⭐ High-quality investment opportunity with strong fundamentals")
            elif comprehensive_score.overall_score < 50:
                insights.append("⚠️ Below-average fundamentals suggest caution")
            
            if comprehensive_score.confidence_level >= 0.8:
                insights.append("📊 High confidence in analysis due to comprehensive data availability")
            elif comprehensive_score.confidence_level < 0.5:
                insights.append("📉 Limited data availability reduces analysis confidence")
    
    except Exception as e:
        logger.error(f"Failed to generate insights: {e}")
        insights.append("⚠️ Analysis completed with limited insights due to data constraints")
    
    # Limit to top 8 insights
    return insights[:8]


def _assess_overall_data_quality(analysis_results: list) -> str:
    """Assess overall data quality across all analysis components"""
    try:
        successful_components = sum(1 for result in analysis_results if not isinstance(result, Exception))
        total_components = len(analysis_results)
        
        success_rate = successful_components / total_components
        
        if success_rate >= 0.8:
            return "high"
        elif success_rate >= 0.6:
            return "medium"
        else:
            return "low"
    except:
        return "low"





