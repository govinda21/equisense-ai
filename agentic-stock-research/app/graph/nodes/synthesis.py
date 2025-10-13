from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.config import AppSettings
from app.graph.state import ResearchState
from app.graph.nodes.synthesis_common import (
    convert_numpy_types,
    score_to_action as _score_to_action,
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
    fund = analysis.get("fundamentals", {})
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

        comp = analysis.get("fundamentals") or {}
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
        
        return {
            "overall_score": comprehensive_fund.get("overall_score", 50.0),
            "overall_grade": comprehensive_fund.get("overall_grade", "C"),
            "recommendation": comprehensive_fund.get("recommendation", "Hold"),
            "confidence_level": comprehensive_fund.get("confidence_level", 0.5),
            
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
    expected_return: float
) -> Dict[str, Any]:
    """
    Generate comprehensive senior equity analyst recommendation with all components.
    
    This function creates a detailed, data-driven investment recommendation suitable
    for sophisticated investors, following institutional equity research standards.
    """
    
    # Extract all available data
    fund = analysis.get("fundamentals", {})
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
    competitive_advantages = _identify_competitive_advantages(strategic_conviction, fund, peer)
    
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
    
    # 12. SHORT-TERM OUTLOOK (3-6 months)
    short_term_outlook = _build_short_term_outlook(action, score, tech, news, analyst)
    
    # 13. LONG-TERM OUTLOOK (12-36 months)
    long_term_outlook = _build_long_term_outlook(action, score, growth, strategic_conviction, fund)
    
    # 14. PRICE TARGET
    price_target_12m, price_target_source = _determine_price_target(analyst, dcf, current_price, expected_return)
    
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
    
    # From growth prospects analysis
    growth_catalysts = growth.get("growth_catalysts", [])
    if growth_catalysts:
        for catalyst in growth_catalysts[:2]:
            if isinstance(catalyst, dict):
                drivers.append(catalyst.get("name") or catalyst.get("description", "Growth catalyst identified"))
            elif isinstance(catalyst, str):
                drivers.append(catalyst)
    
    # From strategic conviction
    if strategic_conviction:
        growth_runway = strategic_conviction.get("growth_runway", {})
        if growth_runway:
            tam_analysis = growth_runway.get("tam_analysis", {})
            if tam_analysis.get("estimated_cagr"):
                cagr = tam_analysis["estimated_cagr"]
                drivers.append(f"TAM expanding at {cagr}% CAGR")
    
    # Revenue growth as a driver
    revenue_growth = fund.get("revenue_growth") or fund.get("revenueGrowth")
    if revenue_growth and revenue_growth > 0.15:
        drivers.append(f"Sustained revenue growth momentum ({revenue_growth:.1f}% YoY)")
    
    # R&D and innovation
    if fund.get("rd_intensity") and fund["rd_intensity"] > 0.10:
        drivers.append("Strong R&D investment supporting innovation pipeline")
    
    return drivers[:5] if drivers else ["Core business expansion opportunities"]


def _identify_competitive_advantages(strategic_conviction: dict, fund: dict, peer: dict) -> List[str]:
    """Identify 3-5 competitive advantages (moats)"""
    advantages = []
    
    # From strategic conviction analysis
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
    
    # Market position advantage
    market_cap = fund.get("market_cap") or fund.get("marketCap")
    if market_cap and market_cap > 50e9:
        advantages.append("Scale advantages from large market capitalization")
    
    # Profitability advantage
    gross_margins = fund.get("gross_margins") or fund.get("grossMargins")
    if gross_margins and gross_margins > 0.50:
        advantages.append(f"Superior gross margins ({gross_margins*100:.1f}%) indicating pricing power")
    
    # Peer comparison advantage
    relative_position = peer.get("relative_position", "")
    if "outperform" in relative_position.lower() or "leader" in relative_position.lower():
        advantages.append("Market leadership position relative to peers")
    
    return advantages[:5] if advantages else ["Established market presence"]


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


def _build_short_term_outlook(action: str, score: float, tech: dict, news: dict, analyst: dict) -> str:
    """Build 3-6 month short-term outlook"""
    
    # Determine technical momentum
    signals = tech.get("signals", {})
    trend = signals.get("trend", "neutral")
    
    # Determine sentiment
    news_score = news.get("score", 0.5)
    sentiment = "positive" if news_score > 0.6 else "neutral" if news_score > 0.4 else "cautious"
    
    if action in ["Strong Buy", "Buy"]:
        outlook = f"Near-term outlook remains {sentiment} supported by {trend} technical momentum. "
        outlook += "We expect the stock to continue its positive trajectory over the next 3-6 months, "
        outlook += "driven by operational momentum and favorable market conditions. "
        outlook += "Any pullbacks should be viewed as accumulation opportunities for long-term investors."
    
    elif action == "Hold":
        outlook = f"Short-term outlook is mixed with {trend} technical setup and {sentiment} sentiment. "
        outlook += "We recommend patience while the investment thesis develops further clarity. "
        outlook += "Monitor upcoming quarterly results and management guidance for directional cues. "
        outlook += "Position adjustments may be warranted based on price action and fundamental developments."
    
    else:  # Sell or Strong Sell
        outlook = f"Near-term outlook appears challenging with {trend} technical momentum and {sentiment} sentiment. "
        outlook += "We anticipate continued pressure over the next 3-6 months. "
        outlook += "Investors should consider reducing exposure or implementing defensive strategies. "
        outlook += "Re-evaluation warranted if fundamental conditions materially improve."
    
    return outlook


def _build_long_term_outlook(action: str, score: float, growth: dict, strategic_conviction: dict, fund: dict) -> str:
    """Build 12-36 month long-term outlook"""
    
    # Assess growth runway
    growth_outlook = growth.get("growth_outlook", {})
    if isinstance(growth_outlook, dict):
        overall_outlook = growth_outlook.get("overall_outlook", "moderate")
    else:
        overall_outlook = "moderate"
    
    # Assess conviction level
    conviction_level = strategic_conviction.get("conviction_level", "Medium Conviction")
    if not isinstance(conviction_level, str):
        conviction_level = "Medium Conviction"
    
    if action in ["Strong Buy", "Buy"]:
        outlook = f"Long-term investment thesis remains compelling with {overall_outlook.lower()} growth prospects. "
        
        # Add growth drivers
        growth_catalysts = growth.get("growth_catalysts", [])
        if isinstance(growth_catalysts, list) and growth_catalysts:
            first_catalyst = growth_catalysts[0]
            if isinstance(first_catalyst, dict):
                catalyst_name = first_catalyst.get('name', 'strategic initiatives')
            else:
                catalyst_name = str(first_catalyst)
            outlook += f"Key catalysts include {catalyst_name}. "
        
        outlook += f"Our {conviction_level.lower()} suggests the company is well-positioned to deliver "
        outlook += "above-market returns over the next 12-36 months. "
        
        # Add valuation perspective
        dcf_val = fund.get("dcf_valuation", {})
        if isinstance(dcf_val, dict) and dcf_val.get("upside_potential"):
            upside = dcf_val["upside_potential"] * 100
            outlook += f"Target upside potential of {upside:.0f}% reflects attractive risk-reward asymmetry for patient capital."
    
    elif action == "Hold":
        outlook = f"Long-term outlook is balanced with {overall_outlook.lower()} growth visibility. "
        outlook += "While the business fundamentals remain sound, current valuation limits asymmetric upside potential. "
        outlook += "We maintain a neutral stance awaiting more favorable entry points or improved growth catalysts. "
        outlook += "The investment thesis may evolve as the company executes on strategic initiatives and market conditions develop."
    
    else:  # Sell or Strong Sell
        outlook = f"Long-term outlook faces structural challenges with {overall_outlook.lower()} growth trajectory. "
        outlook += "Fundamental concerns regarding competitive positioning and market dynamics suggest "
        outlook += "below-market returns over the next 12-36 months. "
        outlook += "Risk-reward profile remains unfavorable even for long-term investors. "
        outlook += "Significant operational improvements and strategic repositioning required to revise our cautious stance."
    
    return outlook


def _determine_price_target(analyst: dict, dcf: dict, current_price: Optional[float], expected_return: float) -> Tuple[Optional[float], str]:
    """Determine 12-month price target and source"""
    
    # Priority 1: Analyst consensus target
    target_prices = analyst.get("target_prices", {})
    analyst_mean_target = target_prices.get("mean")
    
    if analyst_mean_target and analyst_mean_target > 0:
        return round(analyst_mean_target, 2), "Analyst consensus target"
    
    # Priority 2: DCF intrinsic value
    intrinsic_value = dcf.get("intrinsic_value")
    if intrinsic_value and intrinsic_value > 0:
        return round(intrinsic_value, 2), "DCF-based intrinsic value estimate"
    
    # Priority 3: Calculate from expected return
    if current_price and expected_return:
        implied_target = current_price * (1 + expected_return / 100)
        return round(implied_target, 2), "Derived from expected return estimate"
    
    return None, "Price target under evaluation"


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
    
    # Technical Analysis (30% weight)
    tech = analysis.get("technicals", {})
    signals = tech.get("signals", {})
    if signals.get("score") is not None:
        # Convert signal score from -1/+1 range to 0-1 range
        tech_score = max(0, min(1, (signals["score"] + 1) / 2))
        scores.append(tech_score)
        weights.append(0.30)
    
    # Fundamentals (25% weight)  
    fund = analysis.get("fundamentals", {})
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
        weights.append(0.25)
    
    # Cash Flow (20% weight)
    cashflow = analysis.get("cashflow", {})
    cf_score = 0.5
    if cashflow.get("fcf_positive"):
        cf_score += 0.3
    if cashflow.get("ocf_trend") == "improving":
        cf_score += 0.2
    cf_score = max(0, min(1, cf_score))
    scores.append(cf_score)
    weights.append(0.20)
    
    # Peer Analysis (15% weight)
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
        weights.append(0.15)
    
    # Analyst Recommendations (10% weight)
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
    
    # DEBUG: Check what keys are in the analysis dictionary
    logger.info(f"DEBUG synthesis: analysis keys available: {list(a.keys())}")

    news = a.get("news_sentiment", {})
    yt = a.get("youtube", {})
    tech = a.get("technicals", {})
    fund = a.get("fundamentals", {})
    peer = a.get("peer_analysis", {})
    analyst = a.get("analyst_recommendations", {})
    cash = a.get("cashflow", {})
    lead = a.get("leadership", {})
    sm = a.get("sector_macro", {})
    growth = a.get("growth_prospects", {})
    valuation = a.get("valuation", {})
    strategic_conviction = a.get("strategic_conviction", {})
    
    # DEBUG: Check what's in strategic_conviction
    logger.info(f"DEBUG synthesis: strategic_conviction data present: {bool(strategic_conviction)}, keys: {strategic_conviction.keys() if strategic_conviction else 'empty'}")
    if strategic_conviction:
        logger.info(f"DEBUG synthesis: strategic_conviction sample data - score: {strategic_conviction.get('overall_conviction_score')}, level: {strategic_conviction.get('conviction_level')}, recommendation: {strategic_conviction.get('strategic_recommendation')}")

    # Check if comprehensive fundamentals analysis is available
    fund = a.get("fundamentals", {})
    
    # Use comprehensive analysis if available, otherwise fall back to LLM
    if fund and fund.get("overall_score"):
        logger.info(f"Using comprehensive fundamentals analysis for {ticker}")
        
        # Convert 0-100 score to 0-1 scale
        composite_score = fund["overall_score"] / 100.0
        action = fund.get("recommendation", "Hold")
        # Prefer comprehensive expected return if present, else infer from intrinsic value
        tr = fund.get("trading_recommendations", {})
        expected_return = None
        try:
            mos = fund.get("dcf_valuation", {}).get("margin_of_safety")
            if isinstance(mos, (int, float)):
                expected_return = round(mos * 100, 1)
        except Exception:
            expected_return = None
        if expected_return is None:
            try:
                upside = tr.get("upside_potential")
                if isinstance(upside, (int, float)):
                    expected_return = round(upside * 100, 1)
            except Exception:
                pass
        if expected_return is None:
            expected_return = 0.0
        
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
                        if 'buy' in extracted_action:
                            action = "Strong Buy" if 'strong' in extracted_action else "Buy"
                        elif 'sell' in extracted_action:
                            action = "Strong Sell" if 'strong' in extracted_action else "Sell"
                        elif 'hold' in extracted_action:
                            action = "Hold"
                        logger.info(f"Parsed LLM action: {extracted_action} -> {action}")
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
            action = _score_to_action(composite_score)
            
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
                           
            # Calculate expected return based on score
            expected_return = round((composite_score - 0.5) * 40, 1)
            
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
                "comprehensive_fundamentals": _create_comprehensive_fundamentals_output(fund) if fund else None,
            }
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # DEBUG: About to create decision with professional fields
    logger.info(f"Creating decision object with score={composite_score}, action={action}")
    
    # Generate comprehensive senior equity analyst recommendation
    logger.info(f"Generating senior equity analyst recommendation for {ticker}")
    senior_recommendation = _generate_senior_analyst_recommendation(
        ticker=ticker,
        action=action,
        score=composite_score,
        analysis=a,
        positives=positives,
        negatives=negatives,
        expected_return=expected_return
    )
    
    # Add decision to the first report with all senior analyst fields
    state["final_output"]["reports"][0]["decision"] = {
                    "action": action,
                    "rating": round(composite_score * 5, 2),
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
