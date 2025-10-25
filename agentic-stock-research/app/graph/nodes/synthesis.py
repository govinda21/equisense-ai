from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

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
import logging

logger = logging.getLogger(__name__)


def _score_to_letter_grade_old(score: float) -> str:
    """Convert numeric score to letter grade rating (OLD - keeping for compatibility)"""
    if score >= 0.93:
        return "A+"
    elif score >= 0.87:
        return "A"
    elif score >= 0.83:
        return "A-"
    elif score >= 0.77:
        return "B+"
    elif score >= 0.73:
        return "B"
    elif score >= 0.67:
        return "B-"
    elif score >= 0.63:
        return "C+"
    elif score >= 0.57:
        return "C"
    elif score >= 0.53:
        return "C-"
    elif score >= 0.47:
        return "D+"
    elif score >= 0.40:
        return "D"
    elif score >= 0.33:
        return "D-"
    else:
        return "F"


def _generate_star_display(score: float) -> str:
    """Generate star display with proper unicode stars"""
    rating_out_of_5 = score * 5
    full_stars = int(rating_out_of_5)
    has_half_star = (rating_out_of_5 - full_stars) >= 0.5
    
    stars = "★" * full_stars
    if has_half_star and full_stars < 5:
        stars += "☆"
        full_stars += 1
    
    # Fill remaining with empty stars
    empty_stars = 5 - len(stars)
    stars += "☆" * empty_stars
    
    return stars


def _generate_professional_rationale(score: float, action: str, positives: list, negatives: list, analysis: dict) -> str:
    """Generate formal investment analysis rationale"""
    # Extract key data points for rationale
    fund = analysis.get("comprehensive_fundamentals", {})
    tech = analysis.get("technicals", {})
    growth = analysis.get("growth_prospects", {})
    cashflow = analysis.get("cashflow", {})
    
    # Build rationale based on recommendation type
    if action in ["Strong Buy", "Buy"]:
        focus_factors = positives[:2]  # Top 2 positive factors
        
        rationale_parts = []
        
        # Growth and fundamentals
        if any("growth" in factor.lower() for factor in focus_factors):
            rationale_parts.append("robust earnings growth trajectory")
        elif fund.get("roe") and fund["roe"] > 0.15:
            rationale_parts.append("strong return on equity metrics")
        else:
            rationale_parts.append("favorable fundamental indicators")
            
        # Technical or market position
        if any("technical" in factor.lower() or "momentum" in factor.lower() for factor in focus_factors):
            rationale_parts.append("positive technical momentum")
        elif any("position" in factor.lower() or "competitive" in factor.lower() for factor in focus_factors):
            rationale_parts.append("competitive market positioning")
        else:
            rationale_parts.append("supportive market dynamics")
            
        # Financial strength
        if cashflow.get("fcf_positive"):
            rationale_parts.append("solid free cash flow generation")
        elif fund.get("operatingMargins") and fund["operatingMargins"] > 0.15:
            rationale_parts.append("healthy operating margins")
        else:
            rationale_parts.append("sound financial foundation")
            
        if action == "Strong Buy":
            return f"Based on {', '.join(rationale_parts[:2])}, and {rationale_parts[2] if len(rationale_parts) > 2 else 'favorable industry trends'}, the equity demonstrates exceptional upside potential with a compelling risk-adjusted return profile over the next 12-18 months."
        else:
            return f"Supported by {', '.join(rationale_parts[:2])}, the stock presents attractive upside potential, though investors should monitor {negatives[0].lower() if negatives else 'market volatility'} as a key risk factor."
            
    elif action == "Hold":
        balanced_view = []
        if positives:
            balanced_view.append(f"while {positives[0].lower()} provides support")
        if negatives:
            balanced_view.append(f"{negatives[0].lower()} creates near-term uncertainty")
            
        return f"The investment thesis remains balanced, {' and '.join(balanced_view) if balanced_view else 'with mixed fundamental indicators'}. Current valuation appears fairly priced, warranting a cautious approach until greater clarity emerges on key operational metrics."
        
    else:  # Sell or Strong Sell
        risk_factors = negatives[:2] if negatives else ["deteriorating fundamentals", "unfavorable market conditions"]
        
        if action == "Strong Sell":
            return f"Significant concerns regarding {risk_factors[0].lower()} and {risk_factors[1].lower() if len(risk_factors) > 1 else 'operational headwinds'} present substantial downside risk. The current risk-reward profile is unfavorable, suggesting defensive positioning is prudent."
        else:
            return f"Given {risk_factors[0].lower()} and {risk_factors[1].lower() if len(risk_factors) > 1 else 'sector headwinds'}, the near-term outlook appears challenging. Profit-taking may be warranted while monitoring for potential re-entry opportunities."


def _safe_get_letter_grade(score: float) -> str:
    """Safe wrapper for letter grade generation"""
    try:
        if score is None or not isinstance(score, (int, float)):
            return "C"
        result = _score_to_letter_grade(score)
        logger.info(f"Generated letter grade: {result} from score: {score}")
        return result if result else "C"
    except Exception as e:
        logger.error(f"Error generating letter grade: {e}")
        return "C"


def _safe_get_star_display(score: float) -> str:
    """Safe wrapper for star display generation"""
    try:
        if score is None or not isinstance(score, (int, float)):
            return "★★★☆☆"
        result = _generate_star_display(score)
        logger.info(f"Generated stars: {result} from score: {score}")
        return result if result else "★★★☆☆"
    except Exception as e:
        logger.error(f"Error generating star display: {e}")
        return "★★★☆☆"


def _safe_get_professional_rationale(score: float, action: str, positives: list, negatives: list, analysis: dict) -> str:
    """Safe wrapper for professional rationale generation"""
    try:
        if score is None or not isinstance(score, (int, float)):
            score = 0.5
        if not action:
            action = "Hold"
        result = _generate_professional_rationale(score, action, positives or [], negatives or [], analysis or {})
        logger.info(f"Generated rationale: {result[:50]}... from score: {score}, action: {action}")
        return result if result else f"Analysis supports a {action.lower()} recommendation based on current market conditions."
    except Exception as e:
        logger.error(f"Error generating professional rationale: {e}")
        return f"Analysis based on current market conditions and fundamental metrics supports a {action.lower() if action else 'hold'} recommendation with appropriate risk management considerations."


def _safe_get_professional_recommendation(action: str, score: float) -> str:
    """Safe wrapper for professional recommendation generation"""
    try:
        if score is None or not isinstance(score, (int, float)):
            score = 0.5
        if not action:
            action = "Hold"
        stars = _generate_star_display(score)[:5]
        result = f"{action} ({round(score * 5, 1)}/5 {stars})"
        logger.info(f"Generated professional recommendation: {result}")
        return result
    except Exception as e:
        logger.error(f"Error generating professional recommendation: {e}")
        return f"{action} ({round(score * 5, 1) if score else 2.5}/5)"


def _build_executive_summary(action: str, score: float, analysis: dict, positives: list, negatives: list) -> str:
    """Create a concise one-line executive summary.
    Uses comprehensive fundamentals (DCF) if available; otherwise omits gracefully.
    """
    try:
        parts: list[str] = []
        parts.append(f"{action}: {round(score * 100)}")

        comp = analysis.get("comprehensive_fundamentals") or {}
        dcf = comp.get("dcf_valuation") or {}
        iv = dcf.get("intrinsic_value")
        mos = dcf.get("margin_of_safety")

        if isinstance(iv, (int, float)):
            parts.append(f"IV {iv:.2f}")
        if isinstance(mos, (int, float)):
            parts.append(f"MoS {round(mos * 100)}%")

        if positives:
            parts.append("Key: " + ", ".join([p for p in positives[:2] if isinstance(p, str) and p]))
        if negatives:
            parts.append("Risks: " + ", ".join([n for n in negatives[:2] if isinstance(n, str) and n]))

        return "; ".join([p for p in parts if p])
    except Exception:
        try:
            return f"{action}: {round(score * 100)}; Key: {', '.join((positives or [])[:2])} | Risks: {', '.join((negatives or [])[:2])}"
        except Exception:
            return f"{action}: {round(score * 100)}"

def _create_comprehensive_fundamentals_output(comprehensive_fund: dict) -> dict:
    """Create comprehensive fundamentals output for API response"""
    try:
        trading_recs = comprehensive_fund.get("trading_recommendations", {})
        entry_zone = trading_recs.get("entry_zone", (0.0, 0.0))
        
        # Get basic fundamentals data
        basic_fundamentals = comprehensive_fund.get("basic_fundamentals", {})
        
        return {
            "overall_score": comprehensive_fund.get("overall_score", 50.0),
            "overall_grade": comprehensive_fund.get("overall_grade", "C"),
            "recommendation": comprehensive_fund.get("recommendation", "Hold"),
            "confidence_level": comprehensive_fund.get("confidence_level", 0.5),
            
            # Basic fundamental metrics (from Yahoo Finance)
            "pe_ratio": basic_fundamentals.get("pe_ratio"),
            "pb_ratio": basic_fundamentals.get("pb_ratio"),
            "market_cap": basic_fundamentals.get("market_cap"),
            "current_price": basic_fundamentals.get("current_price"),
            "roe": basic_fundamentals.get("roe"),
            "debt_to_equity": basic_fundamentals.get("debt_to_equity"),
            "current_ratio": basic_fundamentals.get("current_ratio"),
            "gross_margins": basic_fundamentals.get("gross_margins"),
            "operating_margins": basic_fundamentals.get("operating_margins"),
            "dividend_yield": basic_fundamentals.get("dividend_yield"),
            "beta": basic_fundamentals.get("beta"),
            "volume": basic_fundamentals.get("volume"),
            "avg_volume": basic_fundamentals.get("avg_volume"),
            "eps": basic_fundamentals.get("eps"),
            "target_price": basic_fundamentals.get("target_price"),
            
            # DCF Valuation
            "intrinsic_value": comprehensive_fund.get("dcf_valuation", {}).get("intrinsic_value"),
            "margin_of_safety": comprehensive_fund.get("dcf_valuation", {}).get("margin_of_safety"),
            "upside_potential": comprehensive_fund.get("dcf_valuation", {}).get("upside_potential"),
            
            # Pillar scores
            "financial_health_score": comprehensive_fund.get("pillar_scores", {}).get("financial_health", {}).get("score", 50.0),
            "valuation_score": comprehensive_fund.get("pillar_scores", {}).get("valuation", {}).get("score", 50.0),
            "growth_prospects_score": comprehensive_fund.get("pillar_scores", {}).get("growth_prospects", {}).get("score", 50.0),
            "governance_score": comprehensive_fund.get("pillar_scores", {}).get("governance", {}).get("score", 50.0),
            "macro_sensitivity_score": comprehensive_fund.get("pillar_scores", {}).get("macro_sensitivity", {}).get("score", 50.0),
            
            # Trading recommendations
            "position_sizing_pct": trading_recs.get("position_sizing_pct", 1.0),
            "entry_zone_low": entry_zone[0] if isinstance(entry_zone, (list, tuple)) and len(entry_zone) > 0 else 0.0,
            "entry_zone_high": entry_zone[1] if isinstance(entry_zone, (list, tuple)) and len(entry_zone) > 1 else 0.0,
            "entry_zone_explanation": trading_recs.get("entry_explanation", "Entry zone calculated using technical analysis"),
            "target_price": trading_recs.get("target_price", 0.0),
            "stop_loss": trading_recs.get("stop_loss", 0.0),
            "time_horizon_months": trading_recs.get("time_horizon_months", 12),
            
            # Risk assessment
            "risk_rating": comprehensive_fund.get("risk_assessment", {}).get("risk_rating", "Medium"),
            "key_risks": comprehensive_fund.get("risk_assessment", {}).get("key_risks", []),
            "key_catalysts": comprehensive_fund.get("risk_assessment", {}).get("key_catalysts", []),
            "key_insights": comprehensive_fund.get("key_insights", []),
            
            # Data quality
            "data_quality": comprehensive_fund.get("data_quality", {}).get("overall_quality", "medium")
        }
    except Exception as e:
        logger.error(f"Error creating comprehensive fundamentals output: {e}")
        return {
            "overall_score": 50.0,
            "overall_grade": "C",
            "recommendation": "Hold",
            "confidence_level": 0.1,
            "error": str(e)
        }


def _generate_senior_analyst_recommendation(
    ticker: str,
    action: str,
    score: float,
    analysis: dict,
    positives: List[str],
    negatives: List[str],
    expected_return: float,
    horizon_short_days: int = 30,
    horizon_long_days: int = 365
) -> Dict[str, Any]:
    """
    Generate comprehensive senior equity analyst recommendation with all components.
    
    This function creates a detailed, data-driven investment recommendation suitable
    for sophisticated investors, following institutional equity research standards.
    """
    
    # Extract all available data
    fund = analysis.get("comprehensive_fundamentals", {})
    tech = analysis.get("technicals", {})
    news = analysis.get("news_sentiment", {})
    analyst = analysis.get("analyst_recommendations", {})
    cashflow = analysis.get("cashflow", {})
    growth = analysis.get("growth_prospects", {})
    valuation = analysis.get("valuation", {})
    peer = analysis.get("peer_analysis", {})
    sector_macro = analysis.get("sector_macro", {})
    strategic_conviction = analysis.get("strategic_conviction", {})
    leadership = analysis.get("leadership", {})
    
    # 1. EXECUTIVE SUMMARY - One concise paragraph
    exec_summary_parts = []
    
    # Company basics
    dcf = fund.get("dcf_valuation", {})
    intrinsic_value = dcf.get("intrinsic_value")
    margin_of_safety = dcf.get("margin_of_safety")
    current_price = fund.get("current_price") or tech.get("current_price")
    
    exec_summary = f"We rate {ticker} as {action} with {round(score * 100)}% conviction. "
    
    if intrinsic_value and margin_of_safety and current_price:
        mos_pct = margin_of_safety * 100
        if mos_pct > 0:
            exec_summary += f"Our DCF analysis indicates an intrinsic value of {intrinsic_value:.2f}, suggesting {abs(mos_pct):.0f}% upside potential from current levels ({current_price:.2f}). "
        else:
            exec_summary += f"Current valuation ({current_price:.2f}) trades {abs(mos_pct):.0f}% above our intrinsic value estimate of {intrinsic_value:.2f}. "
    
    # Add key thesis point
    if positives:
        exec_summary += f"The investment case is supported by {positives[0].lower()}. "
    
    if negatives:
        exec_summary += f"However, investors should monitor {negatives[0].lower()}."
    
    # 2. FINANCIAL CONDITION SUMMARY
    financial_condition = _build_financial_condition_summary(fund, cashflow, analysis)
    
    # 3. LATEST PERFORMANCE SUMMARY  
    latest_performance = _build_latest_performance_summary(fund, tech, news, analysis)
    
    # 4. KEY TRENDS
    key_trends = _identify_key_trends(growth, sector_macro, tech, fund)
    
    # 5. GROWTH DRIVERS
    growth_drivers = _identify_growth_drivers(growth, strategic_conviction, fund)
    
    # 6. COMPETITIVE ADVANTAGES
    competitive_advantages = _identify_competitive_advantages(growth, strategic_conviction, fund, peer)
    
    # 7. KEY RISKS
    key_risks = _identify_key_risks(negatives, strategic_conviction, fund, sector_macro)
    
    # 8. QUANTITATIVE EVIDENCE
    quantitative_evidence = _build_quantitative_evidence(fund, cashflow, valuation, dcf)
    
    # 9. KEY RATIOS SUMMARY
    key_ratios_summary = _build_key_ratios_summary(fund, valuation)
    
    # 10. RECENT DEVELOPMENTS
    recent_developments = _extract_recent_developments(news, analyst, leadership)
    
    # 11. INDUSTRY CONTEXT
    industry_context = _build_industry_context(sector_macro, peer, analysis)
    
    # 12. SHORT-TERM OUTLOOK (user-specified horizon)
    short_term_outlook = _build_short_term_outlook(action, score, tech, news, analyst, fund, valuation, horizon_short_days)
    
    # 13. LONG-TERM OUTLOOK (user-specified horizon)
    long_term_outlook = _build_long_term_outlook(action, score, growth, strategic_conviction, fund, horizon_long_days)
    
    # 14. PRICE TARGET
    # Get DCF data from comprehensive fundamentals
    comprehensive_dcf = fund.get("dcf_valuation", {}) if fund else {}
    price_target_12m, price_target_source = _determine_price_target(analyst, comprehensive_dcf, current_price, expected_return)
    
    # 15. VALUATION BENCHMARK
    valuation_benchmark = _build_valuation_benchmark(valuation, fund, peer)
    
    return {
        "executive_summary": exec_summary,
        "financial_condition_summary": financial_condition,
        "latest_performance_summary": latest_performance,
        "key_trends": key_trends,
        "growth_drivers": growth_drivers,
        "competitive_advantages": competitive_advantages,
        "key_risks": key_risks,
        "quantitative_evidence": quantitative_evidence,
        "key_ratios_summary": key_ratios_summary,
        "recent_developments": recent_developments,
        "industry_context": industry_context,
        "short_term_outlook": short_term_outlook,
        "long_term_outlook": long_term_outlook,
        "price_target_12m": price_target_12m,
        "price_target_source": price_target_source,
        "valuation_benchmark": valuation_benchmark
    }


def _build_financial_condition_summary(fund: dict, cashflow: dict, analysis: dict) -> str:
    """Build financial condition summary paragraph"""
    parts = []
    
    # Balance sheet strength
    debt_to_equity = fund.get("debt_to_equity") or fund.get("debtToEquity")
    current_ratio = fund.get("current_ratio") or fund.get("currentRatio")
    
    if debt_to_equity is not None:
        if debt_to_equity < 30:
            parts.append(f"maintains a conservative balance sheet with minimal debt (D/E: {debt_to_equity:.1f})")
        elif debt_to_equity < 100:
            parts.append(f"operates with moderate leverage (D/E: {debt_to_equity:.1f})")
        else:
            parts.append(f"carries elevated debt levels (D/E: {debt_to_equity:.1f})")
    
    # Liquidity position
    if current_ratio:
        if current_ratio > 2.0:
            parts.append(f"strong liquidity position (Current Ratio: {current_ratio:.2f})")
        elif current_ratio > 1.2:
            parts.append(f"adequate liquidity (Current Ratio: {current_ratio:.2f})")
        else:
            parts.append(f"tight liquidity (Current Ratio: {current_ratio:.2f})")
    
    # Cash flow generation
    fcf_positive = cashflow.get("fcf_positive")
    ocf_trend = cashflow.get("ocf_trend")
    
    if fcf_positive:
        parts.append("generates positive free cash flow")
    
    if ocf_trend == "improving":
        parts.append("with improving operating cash flow trends")
    elif ocf_trend == "declining":
        parts.append("though operating cash flow shows declining trends")
    
    if not parts:
        return "Financial condition analysis pending complete data availability."
    
    return "The company " + ", ".join(parts) + "."


def _build_latest_performance_summary(fund: dict, tech: dict, news: dict, analysis: dict) -> str:
    """Build latest performance summary"""
    parts = []
    
    # Revenue and earnings growth
    revenue_growth = fund.get("revenue_growth") or fund.get("revenueGrowth")
    earnings_growth = fund.get("earnings_growth") or fund.get("earningsGrowth")
    
    if revenue_growth is not None:
        if revenue_growth > 0.15:
            parts.append(f"strong revenue growth of {revenue_growth:.1f}%")
        elif revenue_growth > 0:
            parts.append(f"revenue growth of {revenue_growth:.1f}%")
        else:
            parts.append(f"revenue contraction of {abs(revenue_growth):.1f}%")
    
    if earnings_growth is not None:
        if earnings_growth > 0.20:
            parts.append(f"robust earnings growth of {earnings_growth:.1f}%")
        elif earnings_growth > 0:
            parts.append(f"earnings growth of {earnings_growth:.1f}%")
        else:
            parts.append(f"earnings decline of {abs(earnings_growth):.1f}%")
    
    # Profitability
    operating_margins = fund.get("operating_margins") or fund.get("operatingMargins")
    if operating_margins:
        if operating_margins > 0.20:
            parts.append(f"excellent operating margins of {operating_margins*100:.1f}%")
        elif operating_margins > 0.10:
            parts.append(f"healthy operating margins of {operating_margins*100:.1f}%")
        else:
            parts.append(f"margins of {operating_margins*100:.1f}%")
    
    # Recent price performance
    signals = tech.get("signals", {})
    rsi = signals.get("rsi")
    if rsi:
        if rsi > 70:
            parts.append("recent price momentum in overbought territory")
        elif rsi < 30:
            parts.append("oversold technical conditions")
        else:
            parts.append("balanced technical momentum")
    
    if not parts:
        return "Latest performance metrics under review as data becomes available."
    
    return "Recent performance reflects " + ", ".join(parts) + "."


def _identify_key_trends(growth: dict, sector_macro: dict, tech: dict, fund: dict) -> List[str]:
    """Identify 3-5 key trends"""
    trends = []
    
    # Secular trends from growth analysis
    secular_trends = growth.get("secular_trends", {})
    if isinstance(secular_trends, dict) and secular_trends.get("trends"):
        trends.extend(secular_trends["trends"][:2])
    
    # Sector trends
    sector_outlook = sector_macro.get("sector_outlook", {})
    if isinstance(sector_outlook, dict) and sector_outlook.get("trend"):
        trends.append(f"Sector trend: {sector_outlook['trend']}")
    elif isinstance(sector_outlook, str) and sector_outlook:
        trends.append(f"Sector outlook: {sector_outlook}")
    
    # Technical trends
    signals = tech.get("signals", {})
    if isinstance(signals, dict):
        trend = signals.get("trend")
        if trend:
            trends.append(f"Price trend: {trend}")
    
    # Profitability trends
    roe = fund.get("roe") or fund.get("returnOnEquity")
    if roe and roe > 0.15:
        trends.append(f"Strong ROE of {roe:.1f}% indicating efficient capital utilization")
    
    return trends[:5] if trends else ["Market dynamics under continuous assessment"]


def _identify_growth_drivers(growth: dict, strategic_conviction: dict, fund: dict) -> List[str]:
    """Identify top 3-5 growth drivers"""
    drivers = []
    
    # PRIORITY 1: From growth prospects analysis (most specific and data-driven)
    if growth:
        # Use sector-specific growth drivers from growth prospects
        sector_analysis = growth.get("sector_analysis", {})
        if sector_analysis.get("growth_drivers"):
            drivers.extend(sector_analysis["growth_drivers"])
        
        # Use key metrics as additional drivers
        if sector_analysis.get("key_metrics"):
            drivers.extend(sector_analysis["key_metrics"])
        
        # Use growth outlook key factors
        growth_outlook = growth.get("growth_outlook", {})
        for period in ["short_term", "medium_term", "long_term"]:
            period_data = growth_outlook.get(period, {})
            if period_data.get("key_factors"):
                drivers.extend(period_data["key_factors"])
        
        # Add specific growth metrics
        historical_growth = growth.get("historical_growth", {})
        metrics = historical_growth.get("metrics", {})
        if metrics.get("revenue_growth_ttm") and metrics["revenue_growth_ttm"] > 0.05:
            drivers.append(f"Strong revenue growth momentum ({metrics['revenue_growth_ttm']*100:.1f}% TTM)")
        
        if metrics.get("earnings_growth_ttm") and metrics["earnings_growth_ttm"] > 0.20:
            drivers.append(f"Robust earnings growth ({metrics['earnings_growth_ttm']*100:.1f}% TTM)")
        
        # Add sector-specific insights
        sector = sector_analysis.get("sector", "").lower()
        if "energy" in sector or "oil" in sector:
            drivers.append("Energy transition and renewable investments")
            drivers.append("Global energy demand recovery")
        elif "technology" in sector:
            drivers.append("Digital transformation acceleration")
        elif "banking" in sector or "financial" in sector:
            drivers.append("Financial inclusion expansion")
        elif "pharmaceutical" in sector:
            drivers.append("Healthcare innovation and aging demographics")
    
    # PRIORITY 2: From strategic conviction growth catalysts (more specific than TAM)
    if strategic_conviction:
        growth_runway = strategic_conviction.get("growth_runway", {})
        if growth_runway:
            # Use specific growth catalysts from strategic conviction
            catalysts = growth_runway.get("growth_catalysts", [])
            if catalysts:
                for catalyst in catalysts[:2]:
                    if isinstance(catalyst, dict):
                        drivers.append(catalyst.get("name") or catalyst.get("description", "Strategic growth catalyst"))
                    elif isinstance(catalyst, str):
                        drivers.append(catalyst)
            
            # Use geographic expansion insights
            geo_expansion = growth_runway.get("geographic_expansion", {})
            if geo_expansion.get("expansion_potential") == "High":
                drivers.append("Strong international expansion opportunities")
    
    # PRIORITY 3: From comprehensive fundamentals (company-specific metrics)
    if fund:
        # Revenue growth as a driver
        revenue_growth = fund.get("revenue_growth") or fund.get("revenueGrowth")
        if revenue_growth and revenue_growth > 0.15:
            drivers.append(f"Sustained revenue growth momentum ({revenue_growth:.1f}% YoY)")
        
        # R&D and innovation
        if fund.get("rd_intensity") and fund["rd_intensity"] > 0.10:
            drivers.append("Strong R&D investment supporting innovation pipeline")
        
        # Market expansion opportunities
        market_cap = fund.get("market_cap") or fund.get("marketCap")
        if market_cap and market_cap > 10e9:  # Large cap
            drivers.append("Scale advantages enabling market expansion")
        
        # Profitability-driven growth
        operating_margin = fund.get("operating_margins") or fund.get("operatingMargins")
        if operating_margin and operating_margin > 0.20:
            drivers.append(f"High operating margins ({operating_margin*100:.1f}%) supporting reinvestment")
        
        # Debt capacity for growth
        debt_to_equity = fund.get("debt_to_equity") or fund.get("debtToEquity")
        if debt_to_equity and debt_to_equity < 0.5:
            drivers.append("Low leverage providing capacity for strategic investments")
        
        # Cash generation for growth
        free_cash_flow = fund.get("free_cash_flow") or fund.get("freeCashflow")
        if free_cash_flow and free_cash_flow > 0:
            drivers.append("Strong free cash flow generation supporting growth initiatives")
    
    # PRIORITY 4: Fallback to generic TAM analysis only if no specific drivers found
    if not drivers and strategic_conviction:
        growth_runway = strategic_conviction.get("growth_runway", {})
        if growth_runway:
            tam_analysis = growth_runway.get("tam_analysis", {})
            if tam_analysis.get("estimated_cagr"):
                cagr = tam_analysis["estimated_cagr"]
                drivers.append(f"TAM expanding at {cagr}% CAGR")
    
    # Remove duplicates and limit to top 5
    unique_drivers = []
    for driver in drivers:
        if driver not in unique_drivers:
            unique_drivers.append(driver)
    
    return unique_drivers[:5] if unique_drivers else ["Core business expansion opportunities"]


def _identify_competitive_advantages(growth: dict, strategic_conviction: dict, fund: dict, peer: dict) -> List[str]:
    """Identify 3-5 competitive advantages (moats)"""
    advantages = []
    
    # PRIORITY 1: From growth prospects sector analysis (most specific)
    if growth:
        sector_analysis = growth.get("sector_analysis", {})
        if sector_analysis.get("competitive_position"):
            advantages.append(sector_analysis["competitive_position"])
        
        # Add sector-specific competitive advantages
        sector = sector_analysis.get("sector", "").lower()
        if "banking" in sector or "financial" in sector:
            advantages.append("Branch network and customer relationships")
            advantages.append("Regulatory compliance expertise")
        elif "energy" in sector or "oil" in sector:
            advantages.append("Integrated energy value chain")
            advantages.append("Refining and petrochemicals expertise")
        elif "technology" in sector:
            advantages.append("Technology platform and ecosystem")
        elif "pharmaceutical" in sector:
            advantages.append("R&D pipeline and regulatory expertise")
    
    # PRIORITY 2: From strategic conviction analysis
    if strategic_conviction:
        business_quality = strategic_conviction.get("business_quality", {})
        if business_quality:
            moats = business_quality.get("competitive_moats", [])
            for moat in moats[:2]:
                if isinstance(moat, dict) and moat.get("strength", 0) > 60:
                    moat_type = moat.get("type", "Competitive advantage")
                    evidence = moat.get("evidence", [])
                    if evidence:
                        advantages.append(f"{moat_type}: {evidence[0]}")
                    else:
                        advantages.append(moat_type)
            
            # Also check for key strengths
            key_strengths = business_quality.get("key_strengths", [])
            if key_strengths:
                for strength in key_strengths[:2]:
                    if isinstance(strength, str):
                        advantages.append(strength)
    
    # PRIORITY 3: From comprehensive fundamentals (company-specific metrics)
    if fund:
        # Market position advantage
        market_cap = fund.get("market_cap") or fund.get("marketCap")
        if market_cap and market_cap > 50e9:
            advantages.append("Scale advantages from large market capitalization")
        
        # Profitability advantage
        gross_margins = fund.get("gross_margins") or fund.get("grossMargins")
        if gross_margins and gross_margins > 0.50:
            advantages.append(f"Superior gross margins ({gross_margins*100:.1f}%) indicating pricing power")
        
        # Operating efficiency
        operating_margin = fund.get("operating_margins") or fund.get("operatingMargins")
        if operating_margin and operating_margin > 0.20:
            advantages.append(f"High operating margins ({operating_margin*100:.1f}%) showing operational excellence")
        
        # Financial strength
        debt_to_equity = fund.get("debt_to_equity") or fund.get("debtToEquity")
        if debt_to_equity and debt_to_equity < 0.3:
            advantages.append("Strong balance sheet with low leverage")
        
        # ROE advantage
        roe = fund.get("roe")
        if roe and roe > 0.15:
            advantages.append(f"Superior return on equity ({roe*100:.1f}%) indicating efficient capital use")
    
    # PRIORITY 4: From peer analysis
    if peer and peer.get("relative_position"):
        pos = peer["relative_position"].lower()
        if "leader" in pos or "outperform" in pos:
            advantages.append("Market leadership position")
        elif "average" in pos:
            advantages.append("Competitive market position")
    
    # Remove duplicates and limit to top 5
    unique_advantages = []
    for advantage in advantages:
        if advantage not in unique_advantages:
            unique_advantages.append(advantage)
    
    return unique_advantages[:5] if unique_advantages else ["Established market presence"]


def _identify_key_risks(negatives: List[str], strategic_conviction: dict, fund: dict, sector_macro: dict) -> List[str]:
    """Identify 3-5 key risks"""
    risks = []
    
    # Start with negatives from main analysis
    if isinstance(negatives, list):
        risks.extend(negatives[:2])
    
    # Add valuation risk if relevant
    pe_ratio = fund.get("pe") or fund.get("trailingPE")
    if pe_ratio and isinstance(pe_ratio, (int, float)) and pe_ratio > 40:
        risks.append(f"Elevated valuation multiple (P/E: {pe_ratio:.1f}) may limit upside")
    
    # Debt risk
    debt_to_equity = fund.get("debt_to_equity") or fund.get("debtToEquity")
    if debt_to_equity and isinstance(debt_to_equity, (int, float)) and debt_to_equity > 100:
        risks.append(f"High leverage (D/E: {debt_to_equity:.1f}) increases financial risk")
    
    # Macro risks from strategic conviction
    if strategic_conviction and isinstance(strategic_conviction, dict):
        macro_resilience = strategic_conviction.get("macro_resilience", {})
        if isinstance(macro_resilience, dict):
            cyclicality = macro_resilience.get("cyclicality_assessment", {})
            if isinstance(cyclicality, dict) and cyclicality.get("score", 100) < 50:
                risks.append("High cyclicality exposes company to economic downturn risk")
    
    # Sector risks
    sector_risks = sector_macro.get("key_risks", [])
    if isinstance(sector_risks, list) and sector_risks:
        risks.extend(sector_risks[:1])
    
    return risks[:5] if risks else ["Standard market volatility"]


def _build_quantitative_evidence(fund: dict, cashflow: dict, valuation: dict, dcf: dict) -> Dict[str, Any]:
    """Build dictionary of key quantitative metrics"""
    evidence = {}
    
    # Valuation metrics
    if fund.get("pe"):
        evidence["pe_ratio"] = round(fund["pe"], 2)
    if fund.get("pb"):
        evidence["price_to_book"] = round(fund["pb"], 2)
    if fund.get("peg_ratio") or fund.get("pegRatio"):
        evidence["peg_ratio"] = round(fund.get("peg_ratio") or fund.get("pegRatio"), 2)
    
    # Profitability metrics
    if fund.get("roe") or fund.get("returnOnEquity"):
        roe = fund.get("roe") or fund.get("returnOnEquity")
        evidence["roe"] = f"{roe:.1f}%"
    
    if fund.get("operating_margins") or fund.get("operatingMargins"):
        om = fund.get("operating_margins") or fund.get("operatingMargins")
        evidence["operating_margin"] = f"{om*100:.1f}%"
    
    # Growth metrics
    if fund.get("revenue_growth") or fund.get("revenueGrowth"):
        rg = fund.get("revenue_growth") or fund.get("revenueGrowth")
        evidence["revenue_growth"] = f"{rg:.1f}%"
    
    # Cash flow metrics
    if cashflow.get("fcf_yield"):
        evidence["fcf_yield"] = f"{cashflow['fcf_yield']*100:.1f}%"
    
    # DCF metrics
    if dcf.get("intrinsic_value"):
        evidence["intrinsic_value"] = round(dcf["intrinsic_value"], 2)
    if dcf.get("margin_of_safety"):
        evidence["margin_of_safety"] = f"{dcf['margin_of_safety']*100:.1f}%"
    
    return evidence


def _build_key_ratios_summary(fund: dict, valuation: dict) -> str:
    """Build one-paragraph summary of key ratios"""
    parts = []
    
    # Valuation ratios
    pe = fund.get("pe") or fund.get("trailingPE")
    if pe:
        parts.append(f"P/E of {pe:.1f}")
    
    pb = fund.get("pb") or fund.get("priceToBook")
    if pb:
        parts.append(f"P/B of {pb:.1f}")
    
    # Profitability ratios
    roe = fund.get("roe") or fund.get("returnOnEquity")
    if roe:
        parts.append(f"ROE of {roe:.1f}%")
    
    # Efficiency ratios
    asset_turnover = fund.get("asset_turnover") or fund.get("assetTurnover")
    if asset_turnover:
        parts.append(f"asset turnover of {asset_turnover:.2f}x")
    
    # Financial health ratios
    debt_to_equity = fund.get("debt_to_equity") or fund.get("debtToEquity")
    if debt_to_equity is not None:
        parts.append(f"D/E of {debt_to_equity:.1f}")
    
    if not parts:
        return "Key financial ratios under evaluation."
    
    return "Key metrics include " + ", ".join(parts) + "."


def _extract_recent_developments(news: dict, analyst: dict, leadership: dict) -> List[str]:
    """Extract recent developments from news and other sources"""
    developments = []
    
    # From news sentiment
    news_summary = news.get("summary", "")
    if news_summary and len(news_summary) > 20:
        # Extract first substantive sentence
        sentences = news_summary.split(". ")
        if sentences:
            developments.append(sentences[0])
    
    # From analyst recommendations changes
    analyst_summary = analyst.get("summary", "")
    if "upgrade" in analyst_summary.lower() or "downgrade" in analyst_summary.lower():
        developments.append(analyst_summary.split(".")[0])
    
    # Analyst consensus changes
    consensus = analyst.get("consensus_analysis", {})
    if consensus.get("summary"):
        developments.append(consensus["summary"])
    
    # Leadership changes
    if leadership.get("recent_changes"):
        developments.append("Leadership team changes noted in recent period")
    
    return developments[:3] if developments else ["No significant recent developments"]


def _build_industry_context(sector_macro: dict, peer: dict, analysis: dict) -> str:
    """Build industry context paragraph"""
    parts = []
    
    # Sector outlook
    sector_outlook = sector_macro.get("sector_outlook", {})
    if isinstance(sector_outlook, dict):
        outlook = sector_outlook.get("overall_outlook", "")
        if outlook:
            parts.append(f"sector outlook is {outlook.lower()}")
    elif isinstance(sector_outlook, str) and sector_outlook:
        parts.append(f"sector outlook is {sector_outlook.lower()}")
    
    # Peer comparison
    peer_summary = peer.get("summary", "")
    if peer_summary and isinstance(peer_summary, str):
        # Extract first sentence
        peer_sentence = peer_summary.split(".")[0]
        if len(peer_sentence) < 200:
            parts.append(peer_sentence.lower())
    
    # Industry trends
    industry_trends = sector_macro.get("industry_trends", [])
    if isinstance(industry_trends, list) and industry_trends:
        parts.append(f"key industry trends include {', '.join(str(t) for t in industry_trends[:2])}")
    
    if not parts:
        return "Operating within a dynamic competitive landscape with evolving market conditions."
    
    return "Industry context: " + "; ".join(parts) + "."


def _adjust_recommendation_for_horizon(action: str, score: float, horizon_short_days: int, horizon_long_days: int, tech: dict, fund: dict) -> str:
    """
    Adjust recommendation based on investment horizon and timeframe-specific factors
    
    Args:
        action: Base recommendation
        score: Confidence score
        horizon_short_days: Short-term horizon in days
        horizon_long_days: Long-term horizon in days
        tech: Technical analysis data
        fund: Fundamental analysis data
        
    Returns:
        Adjusted recommendation with horizon-specific reasoning
    """
    # Extract technical indicators for horizon-specific analysis
    indicators = tech.get("indicators", {})
    signals = tech.get("signals", {})
    
    rsi = indicators.get("rsi14", 50)
    momentum_20d = indicators.get("momentum20d", 0)
    tech_score = signals.get("score", 0.5)
    
    # Extract fundamental metrics
    pe_ratio = fund.get("pe_ratio") if fund else None
    roe = fund.get("roe") if fund else None
    
    # Horizon-specific adjustments
    adjustments = []
    
    # Very short-term (1-7 days): Focus on technical momentum
    if horizon_short_days <= 7:
        if momentum_20d > 0.05:  # Strong momentum
            if action in ["Strong Buy", "Buy"]:
                adjustments.append("Strong technical momentum supports very short-term position")
            else:
                adjustments.append("Consider momentum-based exit strategy")
        elif momentum_20d < -0.05:  # Negative momentum
            if action in ["Sell", "Strong Sell"]:
                adjustments.append("Negative momentum confirms short-term bearish view")
            else:
                adjustments.append("Technical weakness suggests caution for very short-term holding")
    
    # Short-term (8-30 days): Balance technical and fundamental factors
    elif horizon_short_days <= 30:
        if rsi < 30 and action in ["Strong Buy", "Buy"]:
            adjustments.append("Oversold conditions provide attractive short-term entry")
        elif rsi > 70 and action in ["Hold", "Sell"]:
            adjustments.append("Overbought conditions suggest short-term profit-taking opportunity")
        
        if pe_ratio and pe_ratio < 15 and action in ["Strong Buy", "Buy"]:
            adjustments.append("Attractive valuation supports short-term accumulation")
    
    # Medium-term (31-90 days): Focus on earnings and sector trends
    elif horizon_short_days <= 90:
        if action in ["Strong Buy", "Buy"]:
            adjustments.append("Medium-term horizon allows for earnings cycle participation")
        elif action in ["Sell", "Strong Sell"]:
            adjustments.append("Medium-term horizon may not capture full recovery potential")
    
    # Long-term (91+ days): Focus on fundamental strength
    else:
        if roe and roe > 0.15 and action in ["Strong Buy", "Buy"]:
            adjustments.append("Strong fundamentals support long-term value creation")
        elif roe and roe < 0.05 and action in ["Hold", "Sell"]:
            adjustments.append("Weak fundamentals limit long-term upside potential")
    
    # Build adjusted recommendation
    if adjustments:
        return f"{action} - {adjustments[0]}"
    else:
        return action


def _build_short_term_outlook(action: str, score: float, tech: dict, news: dict, analyst: dict, fund: dict = None, valuation: dict = None, horizon_days: int = 30) -> str:
    """Build short-term outlook with actionable insights based on user-specified horizon"""
    
    # Extract specific data points for actionable insights
    indicators = tech.get("indicators", {})
    signals = tech.get("signals", {})
    
    # Technical indicators
    rsi = indicators.get("rsi14", 50)
    sma20 = indicators.get("sma20", 0)
    sma50 = indicators.get("sma50", 0)
    sma200 = indicators.get("sma200", 0)
    current_price = indicators.get("current_price") or indicators.get("last_close", 0)
    macd_data = indicators.get("macd", {})
    macd_hist = macd_data.get("hist", 0)
    momentum_20d = indicators.get("momentum20d", 0)
    
    # Technical signals
    regime = signals.get("regime", "sideways")
    tech_score = signals.get("score", 0.5)
    
    # News sentiment with specific details
    news_score = news.get("score", 0.5)
    recent_news = news.get("recent_news", [])
    
    # Analyst data
    analyst_consensus = analyst.get("consensus", "Hold")
    target_prices = analyst.get("target_prices", {})
    analyst_mean_target = target_prices.get("mean", 0)
    analyst_high_target = target_prices.get("high", 0)
    analyst_low_target = target_prices.get("low", 0)
    
    # Current price and valuation metrics
    current_price = fund.get("current_price") if fund else None
    pe_ratio = fund.get("pe_ratio") if fund else None
    pb_ratio = fund.get("pb_ratio") if fund else None
    
    # Build actionable insights based on data
    insights = []
    actionable_recommendations = []
    
    # Technical Analysis Insights
    if rsi < 30:
        insights.append(f"RSI at {rsi:.1f} indicates oversold conditions")
        if action in ["Strong Buy", "Buy"]:
            actionable_recommendations.append("Consider accumulating on any weakness below current levels")
    elif rsi > 70:
        insights.append(f"RSI at {rsi:.1f} suggests overbought territory")
        if action in ["Hold", "Sell", "Strong Sell"]:
            actionable_recommendations.append("Consider taking partial profits if holding long positions")
    
    # MACD Analysis
    if macd_hist > 0:
        insights.append("MACD histogram positive, indicating bullish momentum")
        if action in ["Strong Buy", "Buy"]:
            actionable_recommendations.append("Momentum supports near-term upside potential")
    elif macd_hist < 0:
        insights.append("MACD histogram negative, indicating bearish momentum")
        if action in ["Sell", "Strong Sell"]:
            actionable_recommendations.append("Momentum suggests continued weakness")
    
    # Moving Average Analysis
    if current_price and sma20 and sma50:
        if current_price > sma20 > sma50:
            insights.append(f"Price above key moving averages (SMA20: ₹{sma20:.2f}, SMA50: ₹{sma50:.2f})")
            if action in ["Strong Buy", "Buy"]:
                actionable_recommendations.append("Technical trend supports bullish outlook")
        elif current_price < sma20 < sma50:
            insights.append(f"Price below key moving averages (SMA20: ₹{sma20:.2f}, SMA50: ₹{sma50:.2f})")
            if action in ["Sell", "Strong Sell"]:
                actionable_recommendations.append("Technical trend suggests bearish pressure")
    
    # Momentum Analysis
    if momentum_20d > 0.05:  # 5% momentum
        insights.append(f"Strong 20-day momentum: {momentum_20d*100:.1f}%")
        if action in ["Strong Buy", "Buy"]:
            actionable_recommendations.append("Momentum supports continued upward movement")
    elif momentum_20d < -0.05:  # -5% momentum
        insights.append(f"Negative 20-day momentum: {momentum_20d*100:.1f}%")
        if action in ["Sell", "Strong Sell"]:
            actionable_recommendations.append("Momentum suggests continued downward pressure")
    
    # Valuation Insights
    if current_price and analyst_mean_target:
        upside_potential = ((analyst_mean_target - current_price) / current_price) * 100
        if upside_potential > 15:
            insights.append(f"Analyst consensus suggests {upside_potential:.1f}% upside potential")
            if action in ["Strong Buy", "Buy"]:
                actionable_recommendations.append(f"Target price of ₹{analyst_mean_target:.2f} provides attractive risk-reward")
        elif upside_potential < -10:
            insights.append(f"Analyst consensus indicates {abs(upside_potential):.1f}% downside risk")
            if action in ["Sell", "Strong Sell"]:
                actionable_recommendations.append("Analyst targets suggest limited upside from current levels")
    
    # PE Ratio Analysis
    if pe_ratio:
        if pe_ratio < 15:
            insights.append(f"PE ratio of {pe_ratio:.1f}x appears undervalued")
            if action in ["Strong Buy", "Buy"]:
                actionable_recommendations.append("Attractive valuation supports accumulation strategy")
        elif pe_ratio > 25:
            insights.append(f"PE ratio of {pe_ratio:.1f}x suggests premium valuation")
            if action in ["Hold", "Sell"]:
                actionable_recommendations.append("High valuation limits near-term upside potential")
    
    # News Sentiment Analysis
    if recent_news:
        positive_news_count = sum(1 for news_item in recent_news if news_item.get("sentiment", 0) > 0.5)
        total_news = len(recent_news)
        if positive_news_count / total_news > 0.7:
            insights.append(f"Recent news flow is {positive_news_count}/{total_news} positive")
            if action in ["Strong Buy", "Buy"]:
                actionable_recommendations.append("Positive news sentiment supports near-term momentum")
        elif positive_news_count / total_news < 0.3:
            insights.append(f"Recent news flow is {positive_news_count}/{total_news} positive")
            if action in ["Sell", "Strong Sell"]:
                actionable_recommendations.append("Negative news sentiment may continue to pressure the stock")
    
    # Build the outlook with specific recommendations and technical score
    # Convert days to appropriate timeframe description
    if horizon_days <= 7:
        timeframe_desc = f"{horizon_days} days"
        timeframe_type = "very short-term"
    elif horizon_days <= 30:
        timeframe_desc = f"{horizon_days} days"
        timeframe_type = "short-term"
    elif horizon_days <= 90:
        timeframe_desc = f"{horizon_days} days"
        timeframe_type = "near-term"
    else:
        timeframe_desc = f"{horizon_days} days"
        timeframe_type = "medium-term"
    
    if action in ["Strong Buy", "Buy"]:
        outlook = f"Outlook for {timeframe_desc} ({timeframe_type}) is constructive with technical score of {tech_score:.2f}. "
        if insights:
            outlook += f"Key factors: {', '.join(insights[:3])}. "
        if actionable_recommendations:
            outlook += f"Action: {actionable_recommendations[0]}. "
        
        # Add horizon-specific risk/reward analysis
        if horizon_days <= 7:
            outlook += f"For {horizon_days}-day holding: Focus on technical momentum and news catalysts. "
        elif horizon_days <= 30:
            outlook += f"For {horizon_days}-day holding: Monitor earnings announcements and sector rotation. "
        else:
            outlook += f"For {horizon_days}-day holding: Consider quarterly results and macro developments. "
        
        outlook += "Risk management through stop-loss recommended."
    
    elif action == "Hold":
        outlook = f"Outlook for {timeframe_desc} ({timeframe_type}) is neutral with technical score of {tech_score:.2f}. "
        if insights:
            outlook += f"Mixed signals: {', '.join(insights[:2])}. "
        outlook += f"For {horizon_days}-day holding: Wait for clearer directional cues. "
        if actionable_recommendations:
            outlook += f"Consider: {actionable_recommendations[0]}."
    
    else:  # Sell or Strong Sell
        outlook = f"Outlook for {timeframe_desc} ({timeframe_type}) is challenging with technical score of {tech_score:.2f}. "
        if insights:
            outlook += f"Concerning factors: {', '.join(insights[:3])}. "
        if actionable_recommendations:
            outlook += f"Recommendation: {actionable_recommendations[0]}. "
        
        # Add horizon-specific risk analysis
        if horizon_days <= 7:
            outlook += f"For {horizon_days}-day holding: High volatility risk, consider reducing position size. "
        elif horizon_days <= 30:
            outlook += f"For {horizon_days}-day holding: Downside risk outweighs upside potential. "
        else:
            outlook += f"For {horizon_days}-day holding: Structural challenges may persist. "
        
        outlook += "Risk management should be prioritized over potential upside."
    
    return outlook


def _build_long_term_outlook(action: str, score: float, growth: dict, strategic_conviction: dict, fund: dict, horizon_days: int = 365) -> str:
    """Build long-term outlook using comprehensive fundamentals data based on user-specified horizon"""
    
    # Use comprehensive fundamentals data (the correct source)
    comp_fund = fund.get("comprehensive_fundamentals", {}) if fund else {}
    
    # Extract specific scores from comprehensive analysis
    growth_score = comp_fund.get("growth_prospects_score", 50)
    financial_health_score = comp_fund.get("financial_health_score", 50)
    valuation_score = comp_fund.get("valuation_score", 50)
    overall_score = comp_fund.get("overall_score", 50)
    
    # Extract key insights, catalysts, and risks
    key_insights = comp_fund.get("key_insights", [])
    key_catalysts = comp_fund.get("key_catalysts", [])
    key_risks = comp_fund.get("key_risks", [])
    
    # Extract specific metrics
    upside_potential = comp_fund.get("upside_potential", 0)
    margin_of_safety = comp_fund.get("margin_of_safety", 0)
    
    # Build specific insights based on comprehensive analysis
    insights = []
    actionable_points = []
    
    # Growth Analysis based on comprehensive score
    if growth_score >= 70:
        insights.append(f"Strong growth prospects (score: {growth_score:.1f})")
        if action in ["Strong Buy", "Buy"]:
            actionable_points.append("Growth momentum supports long-term value creation")
    elif growth_score <= 40:
        insights.append(f"Weak growth prospects (score: {growth_score:.1f})")
        if action in ["Hold", "Sell"]:
            actionable_points.append("Limited growth potential constrains long-term upside")
    else:
        insights.append(f"Moderate growth prospects (score: {growth_score:.1f})")
    
    # Financial Health Analysis
    if financial_health_score >= 70:
        insights.append(f"Strong financial health (score: {financial_health_score:.1f})")
        if action in ["Strong Buy", "Buy"]:
            actionable_points.append("Robust financial position supports sustainable growth")
    elif financial_health_score <= 40:
        insights.append(f"Weak financial health (score: {financial_health_score:.1f})")
        if action in ["Sell", "Strong Sell"]:
            actionable_points.append("Financial concerns limit long-term value creation")
    else:
        insights.append(f"Moderate financial health (score: {financial_health_score:.1f})")
    
    # Valuation Analysis
    if valuation_score >= 70:
        insights.append(f"Attractive valuation (score: {valuation_score:.1f})")
        if action in ["Strong Buy", "Buy"]:
            actionable_points.append("Undervalued position provides margin of safety")
    elif valuation_score <= 40:
        insights.append(f"Poor valuation (score: {valuation_score:.1f})")
        if action in ["Hold", "Sell"]:
            actionable_points.append("Overvaluation limits upside potential")
    else:
        insights.append(f"Fair valuation (score: {valuation_score:.1f})")
    
    # Use key insights from comprehensive analysis
    if key_insights:
        # Extract the most relevant insight (remove emoji and get clean text)
        primary_insight = key_insights[0].replace("⚠️ ", "").replace("💰 ", "").replace("💸 ", "")
        insights.append(primary_insight)
    
    # Use key catalysts for positive actions
    if key_catalysts and action in ["Strong Buy", "Buy"]:
        primary_catalyst = key_catalysts[0]
        actionable_points.append(f"Key catalyst: {primary_catalyst}")
    
    # Use key risks for negative actions
    if key_risks and action in ["Hold", "Sell", "Strong Sell"]:
        primary_risk = key_risks[0]
        actionable_points.append(f"Key risk: {primary_risk}")
    
    # Build the outlook with comprehensive analysis
    # Convert days to appropriate timeframe description
    if horizon_days <= 180:
        timeframe_desc = f"{horizon_days} days"
        timeframe_type = "medium-term"
    elif horizon_days <= 365:
        timeframe_desc = f"{horizon_days} days"
        timeframe_type = "long-term"
    elif horizon_days <= 730:
        timeframe_desc = f"{horizon_days} days"
        timeframe_type = "extended-term"
    else:
        timeframe_desc = f"{horizon_days} days"
        timeframe_type = "very long-term"
    
    if action in ["Strong Buy", "Buy"]:
        outlook = f"Outlook for {timeframe_desc} ({timeframe_type}) is constructive with overall score of {overall_score:.1f}. "
        if insights:
            outlook += f"Key strengths: {', '.join(insights[:3])}. "
        if actionable_points:
            outlook += f"Strategy: {actionable_points[0]}. "
        
        # Add horizon-specific analysis
        if horizon_days <= 180:
            outlook += f"For {horizon_days}-day holding: Focus on quarterly execution and sector trends. "
        elif horizon_days <= 365:
            outlook += f"For {horizon_days}-day holding: Monitor annual performance and competitive positioning. "
        else:
            outlook += f"For {horizon_days}-day holding: Evaluate strategic initiatives and market expansion. "
        
        outlook += "Comprehensive analysis supports above-market returns potential."
    
    elif action == "Hold":
        outlook = f"Outlook for {timeframe_desc} ({timeframe_type}) is balanced with overall score of {overall_score:.1f}. "
        if insights:
            outlook += f"Mixed factors: {', '.join(insights[:2])}. "
        outlook += f"For {horizon_days}-day holding: Awaiting clearer growth catalysts or more attractive entry points. "
        if actionable_points:
            outlook += f"Monitor: {actionable_points[0]}."
    
    else:  # Sell or Strong Sell
        outlook = f"Outlook for {timeframe_desc} ({timeframe_type}) faces challenges with overall score of {overall_score:.1f}. "
        if insights:
            outlook += f"Concerning factors: {', '.join(insights[:3])}. "
        
        # Add horizon-specific risk analysis
        if horizon_days <= 180:
            outlook += f"For {horizon_days}-day holding: Near-term headwinds may persist. "
        elif horizon_days <= 365:
            outlook += f"For {horizon_days}-day holding: Structural challenges require monitoring. "
        else:
            outlook += f"For {horizon_days}-day holding: Long-term competitive pressures evident. "
        
        outlook += "Comprehensive analysis suggests below-market returns potential. "
        if actionable_points:
            outlook += f"Risk: {actionable_points[0]}."
    
    return outlook


def _determine_price_target(analyst: dict, dcf: dict, current_price: Optional[float], expected_return: float) -> Tuple[Optional[float], str]:
    """Determine 12-month price target and source"""
    
    # Priority 1: Analyst consensus target
    target_prices = analyst.get("target_prices", {})
    analyst_mean_target = target_prices.get("mean")
    
    if analyst_mean_target and analyst_mean_target > 0:
        return round(analyst_mean_target, 2), "Analyst consensus target"
    
    # Priority 2: DCF target price (not intrinsic value)
    dcf_target_price = dcf.get("target_price")
    if dcf_target_price and dcf_target_price > 0:
        return round(dcf_target_price, 2), "DCF-based target price estimate"
    
    # Priority 3: DCF intrinsic value with 20% premium
    intrinsic_value = dcf.get("intrinsic_value")
    if intrinsic_value and intrinsic_value > 0:
        target_with_premium = intrinsic_value * 1.20  # 20% premium
        return round(target_with_premium, 2), "DCF intrinsic value with 20% premium"
    
    # Priority 4: Calculate from expected return
    if current_price and expected_return:
        implied_target = current_price * (1 + expected_return / 100)
        return round(implied_target, 2), "Derived from expected return estimate"
    
    return None, "Price target under evaluation"


def _calculate_expected_return(analyst: dict, fund: dict, current_price: Optional[float]) -> float:
    """Calculate expected return using multiple methods: analyst targets, PE expansion/contraction, and DCF"""
    
    logger.info(f"DEBUG: _calculate_expected_return called with analyst={bool(analyst)}, fund={bool(fund)}, current_price={current_price}")
    
    # Priority 1: Analyst consensus target-based expected return
    target_prices = analyst.get("target_prices", {})
    analyst_mean_target = target_prices.get("mean")
    
    logger.info(f"DEBUG: analyst_mean_target={analyst_mean_target}")
    
    if analyst_mean_target and analyst_mean_target > 0 and current_price and current_price > 0:
        analyst_return = ((analyst_mean_target - current_price) / current_price) * 100
        if analyst_return > -50 and analyst_return < 200:  # Reasonable range
            logger.info(f"Using analyst consensus expected return: {analyst_return:.1f}%")
            return round(analyst_return, 1)
    
    # Priority 2: Analyst high/low target range (use midpoint)
    analyst_high = target_prices.get("high")
    analyst_low = target_prices.get("low")
    if analyst_high and analyst_low and current_price and current_price > 0:
        analyst_midpoint = (analyst_high + analyst_low) / 2
        analyst_return = ((analyst_midpoint - current_price) / current_price) * 100
        if analyst_return > -50 and analyst_return < 200:  # Reasonable range
            logger.info(f"Using analyst midpoint expected return: {analyst_return:.1f}%")
            return round(analyst_return, 1)
    
    # Priority 3: PE-based expected return (Trailing PE vs Forward PE)
    trailing_pe = fund.get("trailingPE")
    forward_pe = fund.get("forwardPE")
    
    if trailing_pe and forward_pe and trailing_pe > 0 and forward_pe > 0:
        # Calculate PE expansion/contraction
        pe_change_pct = ((trailing_pe - forward_pe) / trailing_pe) * 100
        
        # If forward PE is lower than trailing PE, it suggests earnings growth or multiple compression
        # This can indicate potential price appreciation if earnings are growing
        if pe_change_pct > 0:  # Forward PE < Trailing PE (earnings growth expected)
            # Conservative estimate: assume 50% of PE compression translates to price appreciation
            pe_based_return = pe_change_pct * 0.5
            if pe_based_return > -30 and pe_based_return < 50:  # Reasonable range
                logger.info(f"Using PE-based expected return: {pe_based_return:.1f}% (Trailing PE: {trailing_pe:.1f}, Forward PE: {forward_pe:.1f})")
                return round(pe_based_return, 1)
        else:  # Forward PE > Trailing PE (multiple expansion or earnings decline)
            # If forward PE is higher, it might indicate overvaluation or earnings decline
            pe_based_return = pe_change_pct * 0.3  # More conservative for negative scenarios
            if pe_based_return > -30 and pe_based_return < 50:  # Reasonable range
                logger.info(f"Using PE-based expected return: {pe_based_return:.1f}% (Trailing PE: {trailing_pe:.1f}, Forward PE: {forward_pe:.1f})")
                return round(pe_based_return, 1)
    
    # Priority 4: DCF target price-based expected return (not intrinsic value)
    dcf_valuation = fund.get("dcf_valuation", {})
    dcf_target_price = dcf_valuation.get("target_price")
    if dcf_target_price and dcf_target_price > 0 and current_price and current_price > 0:
        dcf_return = ((dcf_target_price - current_price) / current_price) * 100
        if dcf_return > -50 and dcf_return < 200:  # Reasonable range
            logger.info(f"Using DCF target price expected return: {dcf_return:.1f}%")
            return round(dcf_return, 1)
    
    # Priority 5: DCF intrinsic value with 20% premium
    intrinsic_value = dcf_valuation.get("intrinsic_value")
    if intrinsic_value and intrinsic_value > 0 and current_price and current_price > 0:
        target_with_premium = intrinsic_value * 1.20
        intrinsic_return = ((target_with_premium - current_price) / current_price) * 100
        if intrinsic_return > -50 and intrinsic_return < 200:  # Reasonable range
            logger.info(f"Using DCF intrinsic value + 20% premium expected return: {intrinsic_return:.1f}%")
            return round(intrinsic_return, 1)
    
    # Priority 6: Margin of safety (only if positive)
    margin_of_safety = dcf_valuation.get("margin_of_safety")
    if isinstance(margin_of_safety, (int, float)) and margin_of_safety > 0:
        logger.info(f"Using positive margin of safety expected return: {margin_of_safety * 100:.1f}%")
        return round(margin_of_safety * 100, 1)
    
    # Priority 7: Upside potential from trading recommendations
    trading_rec = fund.get("trading_recommendations", {})
    upside_potential = trading_rec.get("upside_potential")
    if isinstance(upside_potential, (int, float)) and upside_potential > 0:
        logger.info(f"Using upside potential expected return: {upside_potential * 100:.1f}%")
        return round(upside_potential * 100, 1)
    
    # Fallback: Score-based expected return
    overall_score = fund.get("overall_score", 50)
    score_based_return = (overall_score - 50) * 0.8  # Scale to reasonable range
    logger.info(f"Using score-based fallback expected return: {score_based_return:.1f}%")
    return round(score_based_return, 1)


def _build_valuation_benchmark(valuation: dict, fund: dict, peer: dict) -> str:
    """Build valuation benchmark comparison"""
    
    pe = fund.get("pe") or fund.get("trailingPE")
    pb = fund.get("pb") or fund.get("priceToBook")
    
    # Get peer averages if available
    peer_metrics = peer.get("peer_metrics", {})
    peer_avg_pe = peer_metrics.get("avg_pe")
    
    parts = []
    
    if pe and peer_avg_pe:
        premium_discount = ((pe - peer_avg_pe) / peer_avg_pe) * 100
        if premium_discount > 10:
            parts.append(f"trades at {premium_discount:.0f}% premium to peer average P/E")
        elif premium_discount < -10:
            parts.append(f"trades at {abs(premium_discount):.0f}% discount to peer average P/E")
        else:
            parts.append("trades in-line with peer group P/E")
    elif pe:
        parts.append(f"P/E of {pe:.1f}")
    
    # Add PEG if available
    peg = fund.get("peg_ratio") or fund.get("pegRatio")
    if peg and peg > 0:
        if peg < 1.0:
            parts.append(f"attractive PEG ratio of {peg:.2f} suggests growth undervalued")
        elif peg < 2.0:
            parts.append(f"reasonable PEG ratio of {peg:.2f}")
        else:
            parts.append(f"elevated PEG ratio of {peg:.2f} indicates premium valuation")
    
    # Add price-to-book context
    if pb:
        if pb < 1.0:
            parts.append(f"P/B below 1.0 ({pb:.2f}) suggests potential undervaluation")
        elif pb > 3.0:
            parts.append(f"P/B of {pb:.2f} reflects market's growth expectations")
    
    if not parts:
        return "Valuation assessment ongoing relative to historical ranges and peer comparables."
    
    return "Valuation benchmark: " + "; ".join(parts) + "."


def _calculate_base_score(analysis: dict) -> float:
    """Calculate a deterministic base score from quantitative metrics"""
    scores = []
    weights = []
    
    # Technical Analysis (25% weight) - reduced from 30%
    tech = analysis.get("technicals", {})
    signals = tech.get("signals", {})
    if signals.get("score") is not None:
        # Convert signal score from -1/+1 range to 0-1 range
        tech_score = max(0, min(1, (signals["score"] + 1) / 2))
        scores.append(tech_score)
        weights.append(0.25)
    
    # Fundamentals (20% weight) - reduced from 25%  
    fund = analysis.get("comprehensive_fundamentals", {})
    fund_score = 0.5  # Default neutral
    fund_factors = 0
    
    # P/E ratio scoring (lower is better, but not too low)
    pe = fund.get("pe")
    if pe and pe > 0:
        if 10 <= pe <= 20:
            fund_score += 0.2
        elif 20 < pe <= 30:
            fund_score += 0.1
        elif pe > 50:
            fund_score -= 0.2
        fund_factors += 1
    
    # ROE scoring (higher is better)
    roe = fund.get("roe")
    if roe:
        if roe >= 0.15:  # 15%+
            fund_score += 0.2
        elif roe >= 0.10:  # 10-15%
            fund_score += 0.1
        elif roe < 0:
            fund_score -= 0.3
        fund_factors += 1
    
    # Revenue growth scoring
    rev_growth = fund.get("revenueGrowth")
    if rev_growth:
        if rev_growth >= 0.20:  # 20%+
            fund_score += 0.2
        elif rev_growth >= 0.10:  # 10-20%
            fund_score += 0.1
        elif rev_growth < 0:  # Negative growth
            fund_score -= 0.2
        fund_factors += 1
    
    if fund_factors > 0:
        fund_score = max(0, min(1, fund_score))
        scores.append(fund_score)
        weights.append(0.20)
    
    # Cash Flow (15% weight) - reduced from 20%
    cashflow = analysis.get("cashflow", {})
    cf_score = 0.5
    if cashflow.get("fcf_positive"):
        cf_score += 0.3
    if cashflow.get("ocf_trend") == "improving":
        cf_score += 0.2
    cf_score = max(0, min(1, cf_score))
    scores.append(cf_score)
    weights.append(0.15)
    
    # Strategic Conviction (15% weight) - NEW
    strategic_conviction = analysis.get("strategic_conviction", {})
    if strategic_conviction.get("overall_conviction_score") is not None:
        conviction_score = strategic_conviction["overall_conviction_score"] / 100.0
        scores.append(conviction_score)
        weights.append(0.15)
    
    # Peer Analysis (10% weight) - reduced from 15%
    peer = analysis.get("peer_analysis", {})
    if peer.get("relative_position"):
        pos = peer["relative_position"].lower()
        if "outperform" in pos or "leader" in pos:
            peer_score = 0.8
        elif "average" in pos or "peer" in pos:
            peer_score = 0.5
        else:
            peer_score = 0.3
        scores.append(peer_score)
        weights.append(0.10)
    
    # Analyst Recommendations (10% weight) - unchanged
    analyst = analysis.get("analyst_recommendations", {})
    if analyst.get("consensus"):
        consensus = analyst["consensus"].lower()
        if "buy" in consensus:
            analyst_score = 0.8
        elif "hold" in consensus:
            analyst_score = 0.5
        else:
            analyst_score = 0.3
        scores.append(analyst_score)
        weights.append(0.10)
    
    # Sentiment Analysis (5% weight) - NEW
    news = analysis.get("news_sentiment", {})
    if news.get("score") is not None:
        sentiment_score = max(0, min(1, (news["score"] + 1) / 2))  # Convert -1/+1 to 0-1
        scores.append(sentiment_score)
        weights.append(0.05)
    
    # Calculate weighted average
    if scores and weights:
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        return max(0, min(1, weighted_score))
    
    return 0.5  # Default neutral if no data


async def synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    from app.tools.nlp import _ollama_chat
    import asyncio
    
    ticker = state["tickers"][0]
    a = state.get("analysis", {})
    
    # Log synthesis start
    logger.info(f"Starting synthesis for {ticker} with enhanced DCF scenarios")

    news = a.get("news_sentiment", {})
    yt = a.get("youtube", {})
    tech = a.get("technicals", {})
    # Get fundamentals data (prioritize fundamentals key for workflow compatibility)
    fund = a.get("fundamentals", {}) or a.get("comprehensive_fundamentals", {})
    peer = a.get("peer_analysis", {})
    analyst = a.get("analyst_recommendations", {})
    cash = a.get("cashflow", {})
    lead = a.get("leadership", {})
    sm = a.get("sector_macro", {})
    growth = a.get("growth_prospects", {})
    valuation = a.get("valuation", {})
    strategic_conviction = a.get("strategic_conviction", {})
    sector_rotation = a.get("sector_rotation", {})
    
    # Add detailed logging for data flow tracing
    logger.info(f"🔍 Synthesis sees comprehensive_fundamentals keys: {list(fund.keys()) if fund else 'empty'}")
    logger.info(f"🔍 Synthesis sees fundamentals data available: {bool(fund)}")
    logger.info(f"🔍 Synthesis sees deep_financial_analysis: {'deep_financial_analysis' in fund if fund else False}")
    logger.info(f"🔍 Synthesis sees dcf_valuation: {'dcf_valuation' in fund if fund else False}")
    
    # Get current price from comprehensive fundamentals or technicals
    current_price = fund.get("current_price") or tech.get("current_price")
    logger.info(f"DEBUG: current_price extracted: {current_price}")
    
    # DEBUG: Check what's in strategic_conviction
    logger.info(f"DEBUG synthesis: strategic_conviction data present: {bool(strategic_conviction)}, keys: {strategic_conviction.keys() if strategic_conviction else 'empty'}")
    if strategic_conviction:
        logger.info(f"DEBUG synthesis: strategic_conviction sample data - score: {strategic_conviction.get('overall_conviction_score')}, level: {strategic_conviction.get('conviction_level')}, recommendation: {strategic_conviction.get('strategic_recommendation')}")
    
    # DEBUG: Check what's in sector_rotation
    logger.info(f"DEBUG synthesis: sector_rotation data present: {bool(sector_rotation)}, keys: {sector_rotation.keys() if sector_rotation else 'empty'}")
    if sector_rotation:
        logger.info(f"DEBUG synthesis: sector_rotation sample data - score: {sector_rotation.get('overall_score')}, recommendation: {sector_rotation.get('recommendation')}")

    # Check if comprehensive fundamentals analysis is available
    fund = a.get("comprehensive_fundamentals", {})
    
    # Use comprehensive analysis if available, otherwise fall back to LLM
    if fund and fund.get("overall_score"):
        logger.info(f"Using comprehensive fundamentals analysis for {ticker}")
        
        # Convert 0-100 score to 0-1 scale
        composite_score = fund["overall_score"] / 100.0
        action = fund.get("recommendation", "Hold")
        
        # Calculate expected return prioritizing analyst consensus targets
        logger.info(f"DEBUG: About to calculate expected return with analyst={bool(analyst)}, fund={bool(fund)}, current_price={current_price}")
        if analyst:
            logger.info(f"DEBUG: Analyst data keys: {list(analyst.keys())}")
            target_prices = analyst.get('target_prices', {})
            logger.info(f"DEBUG: Target prices: {target_prices}")
        expected_return = _calculate_expected_return(analyst, fund, current_price)
        logger.info(f"DEBUG: Calculated expected return: {expected_return}%")
        
        # Extract factors from comprehensive analysis
        positives = []
        negatives = []
        
        # Collect positive factors from all pillars
        for pillar_name, pillar_data in fund.get("pillar_scores", {}).items():
            if isinstance(pillar_data, dict):
                positives.extend(pillar_data.get("positive_factors", [])[:1])  # Top 1 from each pillar
                negatives.extend(pillar_data.get("negative_factors", [])[:1])   # Top 1 from each pillar
        
        # Use key insights if available
        key_insights = fund.get("key_insights", [])
        if key_insights:
            positives.extend([insight for insight in key_insights if any(word in insight.lower() for word in ["strong", "good", "excellent", "positive", "attractive"])])
            negatives.extend([insight for insight in key_insights if any(word in insight.lower() for word in ["weak", "poor", "concern", "risk", "high"])])
        
        # Limit to top 3 each
        positives = positives[:3] if positives else ["Strong comprehensive analysis"]
        negatives = negatives[:3] if negatives else ["Market volatility risk"]
        
        llm_parsed = True  # Mark as parsed since we have structured data
        
    else:
        # Fall back to LLM analysis
        logger.info(f"Using LLM analysis for {ticker} (no comprehensive fundamentals available)")
        
        # Use LLM to analyze all data and make investment decision
        analysis_prompt = f"""You are an expert financial analyst. Analyze the following data for {ticker} and provide a comprehensive investment recommendation.

**Technical Analysis:**
{tech if tech else "No technical data available"}

**Fundamentals:**
PE Ratio: {fund.get('pe', 'N/A')}
Price-to-Book: {fund.get('pb', 'N/A')}
ROE: {fund.get('roe', 'N/A')}
Revenue Growth: {fund.get('revenueGrowth', 'N/A')}
Operating Margins: {fund.get('operatingMargins', 'N/A')}

**Peer Analysis:**
{peer.get('summary', 'No peer analysis available')}
Relative Position: {peer.get('relative_position', 'N/A')}

**Analyst Recommendations:**
{analyst.get('summary', 'No analyst data available')}
Consensus: {analyst.get('recommendation_summary', {}).get('consensus', 'N/A')}
Target Price Analysis: {analyst.get('consensus_analysis', {}).get('summary', 'N/A')}

**Sentiment:**
News Score: {news.get('score', 'N/A')} ({news.get('summary', 'No news analysis')})
YouTube Score: {yt.get('score', 'N/A')} ({yt.get('summary', 'No YouTube analysis')})

**Cash Flow:**
{cash if cash else "No cash flow data available"}

**Growth Prospects:**
{growth.get('summary', 'No growth analysis available')}
Overall Outlook: {growth.get('growth_outlook', {}).get('overall_outlook', 'N/A')}

**Valuation:**
{valuation.get('valuation_summary', 'No valuation data available')}

**Strategic Conviction Analysis:**
Conviction Score: {strategic_conviction.get('overall_conviction_score', 'N/A')}/100
Conviction Level: {strategic_conviction.get('conviction_level', 'N/A')}
Strategic Recommendation: {strategic_conviction.get('strategic_recommendation', 'N/A')}
Position Sizing: {strategic_conviction.get('position_sizing_pct', 'N/A')}%
Business Quality: {strategic_conviction.get('business_quality', {}).get('score', 'N/A')}/100
Growth Runway: {strategic_conviction.get('growth_runway', {}).get('score', 'N/A')}/100
Valuation Asymmetry: {strategic_conviction.get('valuation_asymmetry', {}).get('score', 'N/A')}/100
Macro Resilience: {strategic_conviction.get('macro_resilience', {}).get('score', 'N/A')}/100

Based on this analysis, provide:
1. Overall score from 0-1 (0=strong sell, 0.5=neutral, 1=strong buy)
2. Investment recommendation (Buy/Hold/Sell)
3. 2-3 key positive factors
4. 2-3 key risk factors
5. Expected return percentage

Format your response as:
SCORE: [0.XX]
ACTION: [Buy/Hold/Sell]
POSITIVES: [factor1], [factor2], [factor3]
NEGATIVES: [risk1], [risk2], [risk3]
RETURN: [X.X]%"""

        # Get LLM analysis
        llm_response = await asyncio.to_thread(_ollama_chat, analysis_prompt)
        
        # Debug logging
        if llm_response:
            logger.info(f"LLM response length: {len(llm_response)} chars")
            logger.info(f"LLM response preview: {llm_response[:500]}...")
        else:
            logger.warning("No LLM response received")
        
        # Parse LLM response with better error handling
        composite_score = 0.5  # default
        action = "Hold"
        positives = ["Analysis pending"]
        negatives = ["Analysis pending"]
        expected_return = 0.0
        llm_parsed = False
        
        if llm_response:
            try:
                # Truncate extremely long responses (might indicate an issue)
                if len(llm_response) > 10000:
                    logger.warning(f"Truncating very long LLM response: {len(llm_response)} chars")
                    llm_response = llm_response[:10000]
                
                response_lower = llm_response.lower()
                
                # Extract score with multiple patterns
                import re
                score_patterns = [
                    r'score[:\s]*([0-9]*\.?[0-9]+)',
                    r'overall[:\s]*([0-9]*\.?[0-9]+)',
                    r'rating[:\s]*([0-9]*\.?[0-9]+)'
                ]
                for pattern in score_patterns:
                    match = re.search(pattern, response_lower)
                    if match:
                        try:
                            parsed_score = float(match.group(1))
                            composite_score = min(1.0, max(0.0, parsed_score))
                            logger.info(f"Parsed LLM score: {parsed_score} -> {composite_score}")
                            llm_parsed = True
                            break
                        except Exception as parse_err:
                            logger.warning(f"Failed to parse score '{match.group(1)}': {parse_err}")
                            continue
                
                # Extract action with better patterns
                action_patterns = [
                    (r'action[:\s]*(buy|hold|sell)', 1),
                    (r'recommendation[:\s]*(buy|hold|sell)', 1),
                    (r'\b(strong\s+buy|buy|hold|sell|strong\s+sell)\b', 1)
                ]
                for pattern, group in action_patterns:
                    match = re.search(pattern, response_lower)
                    if match:
                        extracted_action = match.group(group).strip()
                        
                        # Get conviction level for threshold adjustment
                        conviction_level = strategic_conviction.get("conviction_level", "Medium Conviction") if strategic_conviction else "Medium Conviction"
                        
                        # Apply conviction-adjusted thresholds to LLM-extracted action
                        if 'buy' in extracted_action:
                            base_action = "Strong Buy" if 'strong' in extracted_action else "Buy"
                        elif 'sell' in extracted_action:
                            base_action = "Strong Sell" if 'strong' in extracted_action else "Sell"
                        elif 'hold' in extracted_action:
                            base_action = "Hold"
                        else:
                            base_action = "Hold"
                        
                        # Use conviction-adjusted thresholds to validate/adjust the LLM action
                        action = _score_to_action_with_conviction(composite_score, conviction_level)
                        logger.info(f"LLM extracted: {extracted_action} -> {base_action}, Conviction-adjusted: {action} (score: {composite_score}, conviction: {conviction_level})")
                        llm_parsed = True
                        break
                
                # Extract positives and negatives using simple string parsing
                pos_start = llm_response.find('**POSITIVES:**')
                pos_end = llm_response.find('**NEGATIVES:**')
                if pos_start >= 0 and pos_end >= 0:
                    pos_text = llm_response[pos_start+14:pos_end].strip()
                    logger.info(f"DEBUG: Positives text found: {repr(pos_text[:200])}")
                    
                    # Extract numbered list items with titles
                    pos_items = re.findall(r'(?:\d+\.|\*)\s*\*\*([^*]+)\*\*', pos_text)
                    if pos_items:
                        positives = [title.strip().rstrip(':') for title in pos_items[:3] if title.strip()]
                        logger.info(f"Parsed positives: {positives}")
                        llm_parsed = True
                    else:
                        positives = ["Strong fundamentals"]
                        logger.info("Using fallback positives")
                else:
                    positives = ["Strong fundamentals"]
                    logger.info("POSITIVES section not found")
                
                neg_start = llm_response.find('**NEGATIVES:**')
                neg_end_candidates = [
                    llm_response.find('**RETURN:'),
                    llm_response.find('**SCORE:'),
                    len(llm_response)
                ]
                neg_end = min([x for x in neg_end_candidates if x > neg_start]) if neg_start >= 0 else -1
                
                if neg_start >= 0 and neg_end > neg_start:
                    neg_text = llm_response[neg_start+13:neg_end].strip()
                    logger.info(f"DEBUG: Negatives text found: {repr(neg_text[:200])}")
                    
                    # Extract numbered list items with titles
                    neg_items = re.findall(r'(?:\d+\.|\*)\s*\*\*([^*]+)\*\*', neg_text)
                    if neg_items:
                        negatives = [title.strip().rstrip(':') for title in neg_items[:3] if title.strip()]
                        logger.info(f"Parsed negatives: {negatives}")
                        llm_parsed = True
                    else:
                        negatives = ["Market volatility"]
                        logger.info("Using fallback negatives")
                else:
                    negatives = ["Market volatility"]
                    logger.info("NEGATIVES section not found")
                
                # Extract expected return
                return_match = re.search(r'return[:\s]*([+-]?[0-9]*\.?[0-9]+)', response_lower)
                if return_match:
                    try:
                        expected_return = float(return_match.group(1))
                        logger.info(f"Parsed expected return: {expected_return}%")
                        llm_parsed = True
                    except Exception as ret_err:
                        logger.warning(f"Failed to parse return '{return_match.group(1)}': {ret_err}")
                    
            except Exception as e:
                logger.error(f"Error parsing LLM response: {e}")
                logger.debug(f"Full response: {llm_response}")
                pass
    
    # Calculate deterministic base score and combine with LLM adjustment
    base_score = _calculate_base_score(a)
    
    if llm_parsed and abs(composite_score - 0.5) > 0.1:
        # Use LLM score if it seems reasonable, but cap adjustment at ±0.2
        llm_adjustment = max(-0.2, min(0.2, composite_score - base_score))
        composite_score = base_score + llm_adjustment
        logger.info(f"Using LLM-adjusted score: {base_score} + {llm_adjustment} = {composite_score}")
    else:
        # Use deterministic score
        composite_score = base_score
        logger.info(f"Using deterministic score: {composite_score}")
        
        # Generate consistent fallback reasons based on the score
        if not llm_parsed:
            logger.info("LLM parsing failed, generating fallback reasons based on score")
            
            # Get conviction level for threshold adjustment
            conviction_level = "Medium Conviction"
            if strategic_conviction and "details" in strategic_conviction:
                conviction_level = strategic_conviction["details"].get("conviction_level", "Medium Conviction")
            logger.info(f"Using conviction level: {conviction_level} for action determination")
            
            # Use conviction-adjusted thresholds
            action = _score_to_action_with_conviction(composite_score, conviction_level)
            logger.info(f"Conviction-adjusted action: {action} (score: {composite_score}, conviction: {conviction_level})")
            
            if composite_score >= 0.6:
                positives = ["Strong fundamentals" if fund else "Favorable metrics", 
                           "Positive technicals" if tech else "Market position",
                           "Growth potential" if growth else "Analyst support"]
                negatives = ["Market volatility risk", "Sector headwinds"]
            elif composite_score >= 0.4:
                positives = ["Some positive signals", "Stable operations"]
                negatives = ["Mixed indicators", "Uncertain outlook", "Risk factors present"]
            else:
                positives = ["Limited upside potential", "Some defensive qualities"]
                negatives = ["Weak fundamentals" if fund else "Poor metrics",
                           "Negative technicals" if tech else "Underperformance", 
                           "High risk factors"]
                           
            # Calculate expected return based on score, but try analyst targets first
            expected_return = _calculate_expected_return(analyst, fund, current_price)
            
            logger.info(f"Generated fallback: action={action}, expected_return={expected_return}%")

    # Build robust executive summary string
    exec_summary = _build_executive_summary(action, composite_score, a, positives, negatives)

    state["final_output"] = {
        "tickers": state["tickers"],
        "reports": [
            {
                "ticker": ticker,
                "executive_summary": exec_summary,
                "news_sentiment": {"summary": news.get("summary", ""), "confidence": state.get("confidences", {}).get("news_sentiment", 0.5), "details": news},
                "youtube_sentiment": {"summary": yt.get("summary", ""), "confidence": state.get("confidences", {}).get("youtube", 0.5), "details": yt},
                "technicals": {"summary": "Computed indicators", "confidence": state.get("confidences", {}).get("technicals", 0.5), "details": tech},
                "fundamentals": {"summary": "Key ratios", "confidence": state.get("confidences", {}).get("fundamentals", 0.5), "details": fund},
                "peer_analysis": {"summary": peer.get("summary", ""), "confidence": state.get("confidences", {}).get("peer_analysis", 0.5), "details": peer},
                "analyst_recommendations": {"summary": analyst.get("summary", ""), "confidence": state.get("confidences", {}).get("analyst_recommendations", 0.5), "details": analyst},
                "cashflow": {"summary": "Cash flow trend", "confidence": state.get("confidences", {}).get("cashflow", 0.5), "details": cash},
                "leadership": {"summary": "Leadership and governance", "confidence": state.get("confidences", {}).get("leadership", 0.5), "details": lead},
                "sector_macro": {"summary": "Sector and macro outlook", "confidence": state.get("confidences", {}).get("sector_macro", 0.5), "details": sm},
                "growth_prospects": {"summary": growth.get("summary", ""), "confidence": state.get("confidences", {}).get("growth_prospects", 0.5), "details": growth},
                "valuation": {"summary": valuation.get("valuation_summary", ""), "confidence": state.get("confidences", {}).get("valuation", 0.5), "details": valuation},
                "strategic_conviction": {"summary": strategic_conviction.get("strategic_recommendation", ""), "confidence": state.get("confidences", {}).get("strategic_conviction", 0.5), "details": strategic_conviction} if strategic_conviction else None,
                "sector_rotation": {"summary": sector_rotation.get("recommendation", ""), "confidence": state.get("confidences", {}).get("sector_rotation", 0.5), "details": sector_rotation} if sector_rotation else None,
                "earnings_call_analysis": a.get("earnings_calls") if a.get("earnings_calls") else None,
                "comprehensive_fundamentals": _create_comprehensive_fundamentals_output(fund) if fund else None,
            }
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # DEBUG: About to create decision with professional fields
    logger.info(f"Creating decision object with score={composite_score}, action={action}")
    
    # DEBUG: Check earnings calls data
    logger.info(f"DEBUG synthesis: analysis keys available: {list(a.keys())}")
    logger.info(f"DEBUG synthesis: earnings_calls in analysis: {'earnings_calls' in a}")
    if 'earnings_calls' in a:
        logger.info(f"DEBUG synthesis: earnings_calls data: {a['earnings_calls']}")
    
    # Generate comprehensive senior equity analyst recommendation
    logger.info(f"Generating senior equity analyst recommendation for {ticker}")
    senior_recommendation = _generate_senior_analyst_recommendation(
        ticker=ticker,
        action=action,
        score=composite_score,
        analysis=a,
        positives=positives,
        negatives=negatives,
        expected_return=expected_return,
        horizon_short_days=state.get("horizon_short_days", 30),
        horizon_long_days=state.get("horizon_long_days", 365)
    )
    
    # Add decision to the first report with all senior analyst fields
    state["final_output"]["reports"][0]["decision"] = {
                    "action": action,
                    "rating": round(composite_score * 5, 2),
                    # Backward compatibility fields
                    "recommendation": action,
                    "score": round(composite_score * 5, 2),
                    "letter_grade": _safe_get_letter_grade(composite_score),
                    "stars": _safe_get_star_display(composite_score),
                    "professional_rationale": _safe_get_professional_rationale(
                        composite_score, action, positives, negatives, a
                    ),
                    "expected_return_pct": expected_return,
                    "top_reasons_for": positives,
                    "top_reasons_against": negatives,
                    "llm_parsed": llm_parsed,
                    "base_score": round(base_score, 3),
                    "professional_recommendation": _safe_get_professional_recommendation(action, composite_score),
                    "debug_test": "professional_fields_in_main_decision",
                    
                    # Strategic Conviction Integration
                    "conviction_level": strategic_conviction["details"].get("conviction_level", "Medium Conviction") if strategic_conviction and "details" in strategic_conviction else "Medium Conviction",
                    "conviction_score": strategic_conviction["details"].get("overall_conviction_score", 50.0) if strategic_conviction and "details" in strategic_conviction else 50.0,
                    "strategic_recommendation": strategic_conviction["details"].get("strategic_recommendation", "Hold") if strategic_conviction and "details" in strategic_conviction else "Hold",
                    
                    # Additional fields for frontend compatibility
                    "confidence_score": round(composite_score * 100, 1),
                    
                    # Senior Equity Analyst Report Components
                    "executive_summary": senior_recommendation["executive_summary"],
                    "financial_condition_summary": senior_recommendation["financial_condition_summary"],
                    "latest_performance_summary": senior_recommendation["latest_performance_summary"],
                    "key_trends": senior_recommendation["key_trends"],
                    "growth_drivers": senior_recommendation["growth_drivers"],
                    "competitive_advantages": senior_recommendation["competitive_advantages"],
                    "key_risks": senior_recommendation["key_risks"],
                    "quantitative_evidence": senior_recommendation["quantitative_evidence"],
                    "key_ratios_summary": senior_recommendation["key_ratios_summary"],
                    "recent_developments": senior_recommendation["recent_developments"],
                    "industry_context": senior_recommendation["industry_context"],
                    "short_term_outlook": senior_recommendation["short_term_outlook"],
                    "long_term_outlook": senior_recommendation["long_term_outlook"],
                    "price_target_12m": senior_recommendation["price_target_12m"],
                    "price_target_source": senior_recommendation["price_target_source"],
                    "valuation_benchmark": senior_recommendation["valuation_benchmark"]
    }
    
    # Convert all numpy types to Python native types for Pydantic serialization
    state["final_output"] = convert_numpy_types(state["final_output"])
    
    state.setdefault("confidences", {})["synthesis"] = 0.9
    return state
