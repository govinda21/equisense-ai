from __future__ import annotations

import asyncio
import logging
import math
import re
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
    format_currency, format_percentage, safe_get,
)

logger = logging.getLogger(__name__)


# ── Star display ─────────────────────────────────────────────────────────────

def _generate_star_display(score: float) -> str:
    n = score * 5
    full = int(n)
    stars = "★" * full
    if (n - full) >= 0.5 and full < 5:
        stars += "☆"
    return stars + "☆" * (5 - len(stars))


# ── Safe wrappers ─────────────────────────────────────────────────────────────

def _safe_get_letter_grade(score: float) -> str:
    try:
        return _score_to_letter_grade(score) or "C"
    except Exception:
        return "C"

def _safe_get_star_display(score: float) -> str:
    try:
        return _generate_star_display(score) or "★★★☆☆"
    except Exception:
        return "★★★☆☆"

def _safe_get_professional_rationale(score: float, action: str, positives: list, negatives: list, analysis: dict) -> str:
    try:
        return _generate_professional_rationale(score, action, positives or [], negatives or [], analysis or {})
    except Exception:
        return f"Analysis based on current market conditions supports a {action.lower() if action else 'hold'} recommendation."

def _safe_get_professional_recommendation(action: str, score: float) -> str:
    try:
        return f"{action} ({round(score * 5, 1)}/5 {_generate_star_display(score)[:5]})"
    except Exception:
        return f"{action} ({round(score * 5, 1) if score else 2.5}/5)"


# ── Professional rationale ────────────────────────────────────────────────────

def _generate_professional_rationale(score: float, action: str, positives: list, negatives: list, analysis: dict) -> str:
    fund = analysis.get("comprehensive_fundamentals", {})
    cashflow = analysis.get("cashflow", {})
    if action in ("Strong Buy", "Buy"):
        parts = []
        if any("growth" in f.lower() for f in positives[:2]):
            parts.append("robust earnings growth trajectory")
        elif (fund.get("roe") or 0) > 0.15:
            parts.append("strong return on equity metrics")
        else:
            parts.append("favorable fundamental indicators")
        if any(w in " ".join(positives[:2]).lower() for w in ("technical", "momentum")):
            parts.append("positive technical momentum")
        elif any(w in " ".join(positives[:2]).lower() for w in ("position", "competitive")):
            parts.append("competitive market positioning")
        else:
            parts.append("supportive market dynamics")
        if cashflow.get("fcf_positive"):
            parts.append("solid free cash flow generation")
        elif (fund.get("operatingMargins") or 0) > 0.15:
            parts.append("healthy operating margins")
        else:
            parts.append("sound financial foundation")
        if action == "Strong Buy":
            return (f"Based on {', '.join(parts[:2])}, and {parts[2] if len(parts) > 2 else 'favorable industry trends'}, "
                    "the equity demonstrates exceptional upside potential with a compelling risk-adjusted return profile over the next 12-18 months.")
        return (f"Supported by {', '.join(parts[:2])}, the stock presents attractive upside potential, though investors should "
                f"monitor {negatives[0].lower() if negatives else 'market volatility'} as a key risk factor.")
    elif action == "Hold":
        parts = []
        if positives: parts.append(f"while {positives[0].lower()} provides support")
        if negatives: parts.append(f"{negatives[0].lower()} creates near-term uncertainty")
        joined = " and ".join(parts) if parts else "with mixed fundamental indicators"
        return f"The investment thesis remains balanced, {joined}. Current valuation appears fairly priced, warranting caution until greater clarity emerges."
    else:
        risks = negatives[:2] or ["deteriorating fundamentals", "unfavorable market conditions"]
        r2 = risks[1].lower() if len(risks) > 1 else "operational headwinds"
        if action == "Strong Sell":
            return (f"Significant concerns regarding {risks[0].lower()} and {r2} present substantial downside risk. "
                    "The current risk-reward profile is unfavorable, suggesting defensive positioning is prudent.")
        return (f"Given {risks[0].lower()} and {r2}, the near-term outlook appears challenging. "
                "Profit-taking may be warranted while monitoring for potential re-entry opportunities.")


# ── Risk assessment ───────────────────────────────────────────────────────────

def _generate_institutional_risk_assessment(analysis: Dict, final_report: Dict, conviction_score: float) -> Dict:
    factors, risk_score = [], 0
    fund = (analysis.get("fundamentals") or {}).get("details", {})
    deep = fund.get("deep_financial_analysis", {})
    bs = deep.get("balance_sheet_strength", {}).get("overall_strength_score", {}).get("score", 50)
    eq = deep.get("earnings_quality", {}).get("overall_quality_score", {}).get("score", 50)
    if bs < 60: factors.append("Balance sheet weakness"); risk_score += 15
    if eq < 70: factors.append("Earnings quality concerns"); risk_score += 10
    tech_score = (analysis.get("technicals") or {}).get("overall_score", 50)
    if tech_score < 40: factors.append("Technical weakness"); risk_score += 12
    sent_score = (analysis.get("news_sentiment") or {}).get("overall_sentiment_score", 50)
    if sent_score < 40: factors.append("Negative sentiment"); risk_score += 8
    if conviction_score < 40: factors.append("Low strategic conviction"); risk_score += 10
    sector_score = (analysis.get("sector_macro") or {}).get("overall_score", 50)
    if sector_score < 45: factors.append("Sector headwinds"); risk_score += 8
    level = "High" if risk_score >= 40 else "Moderate" if risk_score >= 25 else "Low" if risk_score >= 15 else "Minimal"
    return {"overall_risk_level": level, "risk_score": min(risk_score, 50),
            "risk_factors": factors, "risk_factors_count": len(factors),
            "assessment": f"Risk assessment based on {len(factors)} identified factors"}


# ── Executive summary ─────────────────────────────────────────────────────────

def _build_executive_summary(action: str, score: float, analysis: dict, positives: list, negatives: list) -> str:
    try:
        parts = [f"{action}: {round(score * 100)}"]
        comp = analysis.get("comprehensive_fundamentals") or {}
        dcf = comp.get("dcf_valuation") or {}
        iv, mos = dcf.get("intrinsic_value"), dcf.get("margin_of_safety")
        if isinstance(iv, (int, float)): parts.append(f"IV {iv:.2f}")
        if isinstance(mos, (int, float)): parts.append(f"MoS {round(mos * 100)}%")
        if positives: parts.append("Key: " + ", ".join(p for p in positives[:2] if isinstance(p, str)))
        if negatives: parts.append("Risks: " + ", ".join(n for n in negatives[:2] if isinstance(n, str)))
        return "; ".join(p for p in parts if p)
    except Exception:
        return f"{action}: {round(score * 100)}"


# ── Comprehensive fundamentals output ─────────────────────────────────────────

def _create_comprehensive_fundamentals_output(fund: dict) -> dict:
    try:
        rec = fund.get("trading_recommendations", {})
        ez = rec.get("entry_zone", (0.0, 0.0))
        basic = fund.get("basic_fundamentals", {})
        def _pil(name): return fund.get("pillar_scores", {}).get(name, {}).get("score", 50.0)
        return {
            "overall_score": fund.get("overall_score", 50.0),
            "overall_grade": fund.get("overall_grade", "C"),
            "recommendation": fund.get("recommendation", "Hold"),
            "confidence_level": fund.get("confidence_level", 0.5),
            **{k: basic.get(k) for k in ["pe_ratio", "pb_ratio", "market_cap", "current_price", "roe",
                                          "debt_to_equity", "current_ratio", "gross_margins",
                                          "operating_margins", "dividend_yield", "beta", "volume",
                                          "avg_volume", "eps", "target_price"]},
            "intrinsic_value": fund.get("dcf_valuation", {}).get("intrinsic_value"),
            "margin_of_safety": fund.get("dcf_valuation", {}).get("margin_of_safety"),
            "upside_potential": fund.get("dcf_valuation", {}).get("upside_potential"),
            "financial_health_score": _pil("financial_health"),
            "valuation_score": _pil("valuation"),
            "growth_prospects_score": _pil("growth_prospects"),
            "governance_score": _pil("governance"),
            "macro_sensitivity_score": _pil("macro_sensitivity"),
            "position_sizing_pct": rec.get("position_sizing_pct", 1.0),
            "entry_zone_low": ez[0] if isinstance(ez, (list, tuple)) and len(ez) > 0 else 0.0,
            "entry_zone_high": ez[1] if isinstance(ez, (list, tuple)) and len(ez) > 1 else 0.0,
            "entry_zone_explanation": rec.get("entry_explanation", "Entry zone calculated using technical analysis"),
            "target_price": rec.get("target_price", 0.0),
            "stop_loss": rec.get("stop_loss", 0.0),
            "time_horizon_months": rec.get("time_horizon_months", 12),
            "risk_rating": fund.get("risk_assessment", {}).get("risk_rating", "Medium"),
            "key_risks": fund.get("risk_assessment", {}).get("key_risks", []),
            "key_catalysts": fund.get("risk_assessment", {}).get("key_catalysts", []),
            "key_insights": fund.get("key_insights", []),
            "data_quality": fund.get("data_quality", {}).get("overall_quality", "medium"),
        }
    except Exception as e:
        logger.error(f"Error creating comprehensive fundamentals output: {e}")
        return {"overall_score": 50.0, "overall_grade": "C", "recommendation": "Hold",
                "confidence_level": 0.1, "error": str(e)}


# ── Senior analyst sub-components ────────────────────────────────────────────

def _build_financial_condition_summary(fund: dict, cashflow: dict, analysis: dict) -> str:
    parts = []
    de = fund.get("debt_to_equity") or fund.get("debtToEquity")
    cr = fund.get("current_ratio") or fund.get("currentRatio")
    if de is not None:
        if de < 30: parts.append(f"maintains a conservative balance sheet (D/E: {de:.1f})")
        elif de < 100: parts.append(f"operates with moderate leverage (D/E: {de:.1f})")
        else: parts.append(f"carries elevated debt levels (D/E: {de:.1f})")
    if cr:
        if cr > 2.0: parts.append(f"strong liquidity (Current Ratio: {cr:.2f})")
        elif cr > 1.2: parts.append(f"adequate liquidity (Current Ratio: {cr:.2f})")
        else: parts.append(f"tight liquidity (Current Ratio: {cr:.2f})")
    if cashflow.get("fcf_positive"): parts.append("generates positive free cash flow")
    ocf = cashflow.get("ocf_trend")
    if ocf == "improving": parts.append("with improving operating cash flow trends")
    elif ocf == "declining": parts.append("though operating cash flow shows declining trends")
    return ("The company " + ", ".join(parts) + ".") if parts else "Financial condition analysis pending."


def _build_latest_performance_summary(fund: dict, tech: dict, news: dict, analysis: dict) -> str:
    parts = []
    rg = fund.get("revenue_growth") or fund.get("revenueGrowth")
    eg = fund.get("earnings_growth") or fund.get("earningsGrowth")
    om = fund.get("operating_margins") or fund.get("operatingMargins")
    rsi = tech.get("signals", {}).get("rsi")
    if rg is not None:
        if rg > 0.15: parts.append(f"strong revenue growth of {rg:.1f}%")
        elif rg > 0: parts.append(f"revenue growth of {rg:.1f}%")
        else: parts.append(f"revenue contraction of {abs(rg):.1f}%")
    if eg is not None:
        if eg > 0.20: parts.append(f"robust earnings growth of {eg:.1f}%")
        elif eg > 0: parts.append(f"earnings growth of {eg:.1f}%")
        else: parts.append(f"earnings decline of {abs(eg):.1f}%")
    if om:
        if om > 0.20: parts.append(f"excellent operating margins of {om*100:.1f}%")
        elif om > 0.10: parts.append(f"healthy operating margins of {om*100:.1f}%")
    if rsi:
        if rsi > 70: parts.append("recent price momentum in overbought territory")
        elif rsi < 30: parts.append("oversold technical conditions")
        else: parts.append("balanced technical momentum")
    return ("Recent performance reflects " + ", ".join(parts) + ".") if parts else "Latest performance metrics under review."


def _identify_key_trends(growth: dict, sector_macro: dict, tech: dict, fund: dict) -> List[str]:
    trends = []
    sec = growth.get("secular_trends", {})
    if isinstance(sec, dict) and sec.get("trends"):
        trends.extend(sec["trends"][:2])
    so = sector_macro.get("sector_outlook", {})
    if isinstance(so, dict) and so.get("trend"): trends.append(f"Sector trend: {so['trend']}")
    elif isinstance(so, str) and so: trends.append(f"Sector outlook: {so}")
    tr = tech.get("signals", {}).get("trend")
    if tr: trends.append(f"Price trend: {tr}")
    roe = fund.get("roe") or fund.get("returnOnEquity")
    if roe and roe > 0.15: trends.append(f"Strong ROE of {roe:.1f}% indicating efficient capital utilization")
    return trends[:5] or ["Market dynamics under continuous assessment"]


def _identify_growth_drivers(growth: dict, strategic_conviction: dict, fund: dict) -> List[str]:
    drivers = []
    if growth:
        sa = growth.get("sector_analysis", {})
        drivers.extend(sa.get("growth_drivers", []))
        drivers.extend(sa.get("key_metrics", []))
        for period in ("short_term", "medium_term", "long_term"):
            drivers.extend(growth.get("growth_outlook", {}).get(period, {}).get("key_factors", []))
        m = growth.get("historical_growth", {}).get("metrics", {})
        if m.get("revenue_growth_ttm", 0) > 0.05:
            drivers.append(f"Strong revenue growth momentum ({m['revenue_growth_ttm']*100:.1f}% TTM)")
        if m.get("earnings_growth_ttm", 0) > 0.20:
            drivers.append(f"Robust earnings growth ({m['earnings_growth_ttm']*100:.1f}% TTM)")
        sector = sa.get("sector", "").lower()
        if "energy" in sector or "oil" in sector:
            drivers += ["Energy transition and renewable investments", "Global energy demand recovery"]
        elif "technology" in sector: drivers.append("Digital transformation acceleration")
        elif "banking" in sector or "financial" in sector: drivers.append("Financial inclusion expansion")
        elif "pharmaceutical" in sector: drivers.append("Healthcare innovation and aging demographics")
    if strategic_conviction:
        gr = strategic_conviction.get("details", {}).get("growth_runway", {})
        for cat in (gr.get("growth_catalysts") or [])[:2]:
            drivers.append(cat.get("name") or cat.get("description", "") if isinstance(cat, dict) else cat)
        if (gr.get("geographic_expansion") or {}).get("expansion_potential") == "High":
            drivers.append("Strong international expansion opportunities")
    if fund:
        rg = fund.get("revenue_growth") or fund.get("revenueGrowth")
        if rg and rg > 0.15: drivers.append(f"Sustained revenue growth momentum ({rg:.1f}% YoY)")
        om = fund.get("operating_margins") or fund.get("operatingMargins")
        if om and om > 0.20: drivers.append(f"High operating margins ({om*100:.1f}%) supporting reinvestment")
        de = fund.get("debt_to_equity") or fund.get("debtToEquity")
        if de and de < 0.5: drivers.append("Low leverage providing capacity for strategic investments")
        fcf = fund.get("free_cash_flow") or fund.get("freeCashflow")
        if fcf and fcf > 0: drivers.append("Strong free cash flow generation supporting growth initiatives")
    unique = list(dict.fromkeys(d for d in drivers if d))
    return unique[:5] or ["Core business expansion opportunities"]


def _identify_competitive_advantages(growth: dict, strategic_conviction: dict, fund: dict, peer: dict) -> List[str]:
    adv = []
    if growth:
        sa = growth.get("sector_analysis", {})
        if sa.get("competitive_position"): adv.append(sa["competitive_position"])
        sector = sa.get("sector", "").lower()
        if "banking" in sector or "financial" in sector:
            adv += ["Branch network and customer relationships", "Regulatory compliance expertise"]
        elif "energy" in sector or "oil" in sector:
            adv += ["Integrated energy value chain", "Refining and petrochemicals expertise"]
        elif "technology" in sector: adv.append("Technology platform and ecosystem")
        elif "pharmaceutical" in sector: adv.append("R&D pipeline and regulatory expertise")
    if strategic_conviction:
        bq = strategic_conviction.get("details", {}).get("business_quality", {})
        for moat in (bq.get("competitive_moats") or [])[:2]:
            if isinstance(moat, dict) and moat.get("strength", 0) > 60:
                ev = moat.get("evidence", [])
                adv.append(f"{moat.get('type')}: {ev[0]}" if ev else moat.get("type", ""))
        adv.extend((s for s in (bq.get("key_strengths") or [])[:2] if isinstance(s, str)))
    if fund:
        mc = fund.get("market_cap") or fund.get("marketCap")
        if mc and mc > 50e9: adv.append("Scale advantages from large market capitalization")
        gm = fund.get("gross_margins") or fund.get("grossMargins")
        if gm and gm > 0.50: adv.append(f"Superior gross margins ({gm*100:.1f}%) indicating pricing power")
        om = fund.get("operating_margins") or fund.get("operatingMargins")
        if om and om > 0.20: adv.append(f"High operating margins ({om*100:.1f}%) showing operational excellence")
        de = fund.get("debt_to_equity") or fund.get("debtToEquity")
        if de and de < 0.3: adv.append("Strong balance sheet with low leverage")
        roe = fund.get("roe")
        if roe and roe > 0.15: adv.append(f"Superior ROE ({roe*100:.1f}%) indicating efficient capital use")
    if peer and peer.get("relative_position"):
        pos = peer["relative_position"].lower()
        if "leader" in pos or "outperform" in pos: adv.append("Market leadership position")
        elif "average" in pos: adv.append("Competitive market position")
    return list(dict.fromkeys(a for a in adv if a))[:5] or ["Established market presence"]


def _identify_key_risks(negatives: List[str], strategic_conviction: dict, fund: dict, sector_macro: dict) -> List[str]:
    risks = list(negatives[:2])
    pe = fund.get("pe") or fund.get("trailingPE")
    if isinstance(pe, (int, float)) and pe > 40:
        risks.append(f"Elevated valuation multiple (P/E: {pe:.1f}) may limit upside")
    de = fund.get("debt_to_equity") or fund.get("debtToEquity")
    if isinstance(de, (int, float)) and de > 100:
        risks.append(f"High leverage (D/E: {de:.1f}) increases financial risk")
    if strategic_conviction:
        cyc = strategic_conviction.get("details", {}).get("macro_resilience", {}).get("cyclicality_assessment", {})
        if isinstance(cyc, dict) and cyc.get("score", 100) < 50:
            risks.append("High cyclicality exposes company to economic downturn risk")
    sr = sector_macro.get("key_risks", [])
    if isinstance(sr, list) and sr: risks.extend(sr[:1])
    return risks[:5] or ["Standard market volatility"]


def _build_quantitative_evidence(fund: dict, cashflow: dict, valuation: dict, dcf: dict) -> Dict:
    ev: Dict[str, Any] = {}
    for k, label in [("pe", "pe_ratio"), ("pb", "price_to_book")]:
        if fund.get(k): ev[label] = round(fund[k], 2)
    peg = fund.get("peg_ratio") or fund.get("pegRatio")
    if peg: ev["peg_ratio"] = round(peg, 2)
    roe = fund.get("roe") or fund.get("returnOnEquity")
    if roe: ev["roe"] = f"{roe:.1f}%"
    om = fund.get("operating_margins") or fund.get("operatingMargins")
    if om: ev["operating_margin"] = f"{om*100:.1f}%"
    rg = fund.get("revenue_growth") or fund.get("revenueGrowth")
    if rg: ev["revenue_growth"] = f"{rg:.1f}%"
    if cashflow.get("fcf_yield"): ev["fcf_yield"] = f"{cashflow['fcf_yield']*100:.1f}%"
    if not dcf.get("dcf_applicable", True):
        sm = dcf.get("suggested_metrics", {})
        if sm.get("revenue"): ev["revenue"] = f"₹{sm['revenue']:,.0f} Cr"
        if sm.get("price_to_sales_ratio"): ev["price_to_sales"] = f"{sm['price_to_sales_ratio']:.1f}x"
        if sm.get("revenue_growth_yoy"): ev["revenue_growth"] = f"{sm['revenue_growth_yoy']*100:.1f}%"
        ev["dcf_status"] = "Not applicable (loss-making company)"
    else:
        if dcf.get("intrinsic_value"): ev["intrinsic_value"] = round(dcf["intrinsic_value"], 2)
        if dcf.get("margin_of_safety"): ev["margin_of_safety"] = f"{dcf['margin_of_safety']*100:.1f}%"
    return ev


def _build_key_ratios_summary(fund: dict, valuation: dict) -> str:
    parts = []
    pe = fund.get("pe") or fund.get("trailingPE")
    pb = fund.get("pb") or fund.get("priceToBook")
    roe = fund.get("roe") or fund.get("returnOnEquity")
    at = fund.get("asset_turnover") or fund.get("assetTurnover")
    de = fund.get("debt_to_equity") or fund.get("debtToEquity")
    if pe: parts.append(f"P/E of {pe:.1f}")
    if pb: parts.append(f"P/B of {pb:.1f}")
    if roe: parts.append(f"ROE of {roe:.1f}%")
    if at: parts.append(f"asset turnover of {at:.2f}x")
    if de is not None: parts.append(f"D/E of {de:.1f}")
    return ("Key metrics include " + ", ".join(parts) + ".") if parts else "Key financial ratios under evaluation."


def _extract_recent_developments(news: dict, analyst: dict, leadership: dict) -> List[str]:
    devs = []
    ns = news.get("summary", "")
    if ns and len(ns) > 20:
        devs.append(ns.split(". ")[0])
    als = analyst.get("summary", "")
    if any(w in als.lower() for w in ("upgrade", "downgrade")):
        devs.append(als.split(".")[0])
    cs = analyst.get("consensus_analysis", {}).get("summary")
    if cs: devs.append(cs)
    if leadership.get("recent_changes"): devs.append("Leadership team changes noted in recent period")
    return devs[:3] or ["No significant recent developments"]


def _build_industry_context(sector_macro: dict, peer: dict, analysis: dict) -> str:
    parts = []
    so = sector_macro.get("sector_outlook", {})
    if isinstance(so, dict) and so.get("overall_outlook"): parts.append(f"sector outlook is {so['overall_outlook'].lower()}")
    elif isinstance(so, str) and so: parts.append(f"sector outlook is {so.lower()}")
    ps = peer.get("summary", "")
    if ps and isinstance(ps, str):
        sent = ps.split(".")[0]
        if len(sent) < 200: parts.append(sent.lower())
    it = sector_macro.get("industry_trends", [])
    if isinstance(it, list) and it: parts.append(f"key industry trends include {', '.join(str(t) for t in it[:2])}")
    return ("Industry context: " + "; ".join(parts) + ".") if parts else "Operating within a dynamic competitive landscape."


def _build_short_term_outlook(action: str, score: float, tech: dict, news: dict, analyst: dict,
                               fund: dict = None, valuation: dict = None, horizon_days: int = 30) -> str:
    ind = tech.get("indicators", {})
    sig = tech.get("signals", {})
    rsi = ind.get("rsi14", 50)
    sma20, sma50 = ind.get("sma20", 0), ind.get("sma50", 0)
    cp = (fund or {}).get("current_price") or ind.get("current_price") or ind.get("last_close", 0)
    macd_hist = ind.get("macd", {}).get("hist", 0)
    mom20 = ind.get("momentum20d", 0)
    ts = sig.get("score", 0.5)
    amt = analyst.get("target_prices", {}).get("mean", 0)
    pe = (fund or {}).get("pe_ratio")
    insights, actions = [], []
    if rsi < 30:
        insights.append(f"RSI at {rsi:.1f} indicates oversold conditions")
        if "Buy" in action: actions.append("Consider accumulating on weakness")
    elif rsi > 70:
        insights.append(f"RSI at {rsi:.1f} suggests overbought territory")
        if action in ("Hold", "Sell", "Strong Sell"): actions.append("Consider taking partial profits")
    if macd_hist > 0:
        insights.append("MACD histogram positive, indicating bullish momentum")
        if "Buy" in action: actions.append("Momentum supports near-term upside")
    elif macd_hist < 0:
        insights.append("MACD histogram negative, indicating bearish momentum")
        if action in ("Sell", "Strong Sell"): actions.append("Momentum suggests continued weakness")
    if cp and sma20 and sma50:
        if cp > sma20 > sma50:
            insights.append(f"Price above key MAs (SMA20: ₹{sma20:.2f}, SMA50: ₹{sma50:.2f})")
            if "Buy" in action: actions.append("Technical trend supports bullish outlook")
        elif cp < sma20 < sma50:
            insights.append(f"Price below key MAs (SMA20: ₹{sma20:.2f}, SMA50: ₹{sma50:.2f})")
            if action in ("Sell", "Strong Sell"): actions.append("Technical trend suggests bearish pressure")
    if abs(mom20) > 0.05:
        dir_ = "Strong" if mom20 > 0 else "Negative"
        insights.append(f"{dir_} 20-day momentum: {mom20*100:.1f}%")
    if cp and amt:
        upside = (amt - cp) / cp * 100
        if upside > 15:
            insights.append(f"Analyst consensus suggests {upside:.1f}% upside")
            if "Buy" in action: actions.append(f"Target ₹{amt:.2f} provides attractive risk-reward")
        elif upside < -10:
            insights.append(f"Analyst consensus indicates {abs(upside):.1f}% downside risk")
    if pe:
        if pe < 15 and "Buy" in action: actions.append("Attractive valuation supports accumulation")
        elif pe > 25 and action in ("Hold", "Sell"): actions.append("High valuation limits near-term upside")
    td = f"{horizon_days} days"
    tt = "very short-term" if horizon_days <= 7 else "short-term" if horizon_days <= 30 else "near-term" if horizon_days <= 90 else "medium-term"
    key_str = f"Key factors: {', '.join(insights[:3])}. " if insights else ""
    act_str = f"Action: {actions[0]}. " if actions else ""
    if "Buy" in action:
        return f"Outlook for {td} ({tt}) is constructive (tech score {ts:.2f}). {key_str}{act_str}Risk management through stop-loss recommended."
    elif action == "Hold":
        return f"Outlook for {td} ({tt}) is neutral (tech score {ts:.2f}). {key_str}Wait for clearer directional cues."
    else:
        return f"Outlook for {td} ({tt}) is challenging (tech score {ts:.2f}). {key_str}{act_str}Risk management should be prioritized."


def _build_long_term_outlook(action: str, score: float, growth: dict, strategic_conviction: dict,
                              fund: dict, horizon_days: int = 365) -> str:
    comp = (fund or {}).get("comprehensive_fundamentals", {}) if fund else {}
    gs = comp.get("growth_prospects_score", 50)
    fhs = comp.get("financial_health_score", 50)
    vs = comp.get("valuation_score", 50)
    overall = comp.get("overall_score", 50)
    insights = []
    if gs >= 70: insights.append(f"Strong growth prospects (score: {gs:.1f})")
    elif gs <= 40: insights.append(f"Weak growth prospects (score: {gs:.1f})")
    else: insights.append(f"Moderate growth prospects (score: {gs:.1f})")
    if fhs >= 70: insights.append(f"Strong financial health (score: {fhs:.1f})")
    elif fhs <= 40: insights.append(f"Weak financial health (score: {fhs:.1f})")
    else: insights.append(f"Moderate financial health (score: {fhs:.1f})")
    if vs >= 70: insights.append(f"Attractive valuation (score: {vs:.1f})")
    elif vs <= 40: insights.append(f"Poor valuation (score: {vs:.1f})")
    else: insights.append(f"Fair valuation (score: {vs:.1f})")
    ki = comp.get("key_insights", [])
    if ki: insights.append(ki[0].replace("⚠️ ", "").replace("💰 ", "").replace("💸 ", ""))
    tt = ("medium-term" if horizon_days <= 180 else "long-term" if horizon_days <= 365
          else "extended-term" if horizon_days <= 730 else "very long-term")
    key_str = f"Key factors: {', '.join(insights[:3])}. " if insights else ""
    if "Buy" in action:
        return f"Outlook for {horizon_days} days ({tt}) is constructive (overall score {overall:.1f}). {key_str}Comprehensive analysis supports above-market returns potential."
    elif action == "Hold":
        return f"Outlook for {horizon_days} days ({tt}) is balanced (overall score {overall:.1f}). {key_str}Awaiting clearer growth catalysts or more attractive entry points."
    else:
        return f"Outlook for {horizon_days} days ({tt}) faces challenges (overall score {overall:.1f}). {key_str}Comprehensive analysis suggests below-market returns potential."


def _determine_price_target(analyst: dict, dcf: dict, current_price: Optional[float], expected_return: float) -> Tuple[Optional[float], str]:
    if not dcf.get("dcf_applicable", True):
        if current_price and expected_return:
            return round(current_price * (1 + expected_return / 100), 2), f"Expected return-based target ({expected_return:.1f}%)"
        return None, "DCF not applicable - insufficient data for alternative valuation"
    amt = analyst.get("target_prices", {}).get("mean")
    if amt and amt > 0: return round(amt, 2), "Analyst consensus target"
    tp = dcf.get("target_price")
    if tp and tp > 0: return round(tp, 2), "DCF-based target price estimate"
    iv = dcf.get("intrinsic_value")
    if iv and iv > 0: return round(iv * 1.20, 2), "DCF intrinsic value with 20% premium"
    if current_price and expected_return:
        return round(current_price * (1 + expected_return / 100), 2), "Derived from expected return estimate"
    return None, "Price target under evaluation"


def _build_valuation_benchmark(valuation: dict, fund: dict, peer: dict) -> str:
    pe = fund.get("pe") or fund.get("trailingPE")
    peg = fund.get("peg_ratio") or fund.get("pegRatio")
    pb = fund.get("pb") or fund.get("priceToBook")
    peer_pe = peer.get("peer_metrics", {}).get("avg_pe")
    parts = []
    if pe and peer_pe:
        disc = (pe - peer_pe) / peer_pe * 100
        if disc > 10: parts.append(f"trades at {disc:.0f}% premium to peer average P/E")
        elif disc < -10: parts.append(f"trades at {abs(disc):.0f}% discount to peer average P/E")
        else: parts.append("trades in-line with peer group P/E")
    elif pe: parts.append(f"P/E of {pe:.1f}")
    if peg and peg > 0:
        if peg < 1.0: parts.append(f"attractive PEG ratio of {peg:.2f}")
        elif peg < 2.0: parts.append(f"reasonable PEG ratio of {peg:.2f}")
        else: parts.append(f"elevated PEG ratio of {peg:.2f}")
    if pb:
        if pb < 1.0: parts.append(f"P/B below 1.0 ({pb:.2f}) suggests potential undervaluation")
        elif pb > 3.0: parts.append(f"P/B of {pb:.2f} reflects market's growth expectations")
    return ("Valuation benchmark: " + "; ".join(parts) + ".") if parts else "Valuation assessment ongoing."


def _generate_senior_analyst_recommendation(ticker: str, action: str, score: float, analysis: dict,
                                             positives: List[str], negatives: List[str],
                                             expected_return: float, horizon_short_days: int = 30,
                                             horizon_long_days: int = 365) -> Dict:
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
    dcf = fund.get("dcf_valuation", {})
    current_price = fund.get("current_price") or fund.get("basic_fundamentals", {}).get("current_price") or tech.get("current_price")

    # Executive summary
    exec_s = f"We rate {ticker} as {action} with {round(score * 100)}% conviction. "
    if not dcf.get("dcf_applicable", True):
        sm = dcf.get("suggested_metrics", {})
        if sm.get("revenue") and sm.get("price_to_sales_ratio") and current_price:
            exec_s += (f"As a loss-making company, DCF is not applicable. Valuation at "
                       f"{sm['price_to_sales_ratio']:.1f}x revenue (₹{sm['revenue']:,.0f} Cr). ")
        else:
            exec_s += "As a loss-making company, DCF is not applicable. Investment thesis depends on growth and path to profitability. "
    elif dcf.get("intrinsic_value") and dcf.get("margin_of_safety") and current_price:
        iv, mos = dcf["intrinsic_value"], dcf["margin_of_safety"]
        mos_pct = mos * 100
        if mos_pct > 0:
            exec_s += f"DCF intrinsic value of {iv:.2f} suggests {abs(mos_pct):.0f}% upside from {current_price:.2f}. "
        else:
            exec_s += f"Current price ({current_price:.2f}) trades {abs(mos_pct):.0f}% above intrinsic value {iv:.2f}. "
    if positives: exec_s += f"Investment case supported by {positives[0].lower()}. "
    if negatives: exec_s += f"Investors should monitor {negatives[0].lower()}."

    price_target, pt_source = _determine_price_target(analyst, dcf, current_price, expected_return)
    return {
        "executive_summary": exec_s,
        "financial_condition_summary": _build_financial_condition_summary(fund, cashflow, analysis),
        "latest_performance_summary": _build_latest_performance_summary(fund, tech, news, analysis),
        "key_trends": _identify_key_trends(growth, sector_macro, tech, fund),
        "growth_drivers": _identify_growth_drivers(growth, strategic_conviction, fund),
        "competitive_advantages": _identify_competitive_advantages(growth, strategic_conviction, fund, peer),
        "key_risks": _identify_key_risks(negatives, strategic_conviction, fund, sector_macro),
        "quantitative_evidence": _build_quantitative_evidence(fund, cashflow, valuation, dcf),
        "key_ratios_summary": _build_key_ratios_summary(fund, valuation),
        "recent_developments": _extract_recent_developments(news, analyst, leadership),
        "industry_context": _build_industry_context(sector_macro, peer, analysis),
        "short_term_outlook": _build_short_term_outlook(action, score, tech, news, analyst, fund, valuation, horizon_short_days),
        "long_term_outlook": _build_long_term_outlook(action, score, growth, strategic_conviction, fund, horizon_long_days),
        "price_target_12m": price_target,
        "price_target_source": pt_source,
        "valuation_benchmark": _build_valuation_benchmark(valuation, fund, peer),
    }


# ── Base score calculation ────────────────────────────────────────────────────

def _calculate_base_score(analysis: dict) -> float:
    scores, weights = [], []

    tech = analysis.get("technicals", {})
    ts = tech.get("signals", {}).get("score")
    if ts is not None:
        scores.append(max(0, min(1, (ts + 1) / 2))); weights.append(0.25)

    fund = analysis.get("comprehensive_fundamentals", {})
    fs = 0.5; factors = 0
    pe = fund.get("pe")
    if pe and pe > 0:
        fs += 0.2 if 10 <= pe <= 20 else 0.1 if 20 < pe <= 30 else -0.2 if pe > 50 else 0
        factors += 1
    roe = fund.get("roe")
    if roe:
        fs += 0.2 if roe >= 0.15 else 0.1 if roe >= 0.10 else -0.3 if roe < 0 else 0
        factors += 1
    rg = fund.get("revenueGrowth")
    if rg:
        fs += 0.2 if rg >= 0.20 else 0.1 if rg >= 0.10 else -0.2 if rg < 0 else 0
        factors += 1
    if factors:
        scores.append(max(0, min(1, fs))); weights.append(0.20)

    cf = analysis.get("cashflow", {})
    cfs = min(1, max(0, 0.5 + (0.3 if cf.get("fcf_positive") else 0) + (0.2 if cf.get("ocf_trend") == "improving" else 0)))
    scores.append(cfs); weights.append(0.15)

    sc = analysis.get("strategic_conviction", {})
    if sc:
        cv = sc.get("details", {}).get("overall_conviction_score")
        if cv is not None:
            scores.append(cv / 100.0); weights.append(0.15)

    peer = analysis.get("peer_analysis", {})
    if peer.get("relative_position"):
        pos = peer["relative_position"].lower()
        ps = 0.8 if ("outperform" in pos or "leader" in pos) else 0.3 if "below" in pos else 0.5
        scores.append(ps); weights.append(0.10)

    ar = analysis.get("analyst_recommendations", {})
    if ar.get("consensus"):
        con = ar["consensus"].lower()
        als = 0.8 if "buy" in con else 0.3 if "sell" in con else 0.5
        scores.append(als); weights.append(0.10)

    ns = analysis.get("news_sentiment", {})
    if ns.get("score") is not None:
        scores.append(max(0, min(1, (ns["score"] + 1) / 2))); weights.append(0.05)

    if not scores: return 0.5
    total_w = sum(weights)
    return max(0, min(1, sum(s * w for s, w in zip(scores, weights)) / total_w))


# ── Expected return calculation ───────────────────────────────────────────────

def _calculate_expected_return(analyst: dict, fund: dict, current_price: Optional[float]) -> float:
    tp = analyst.get("target_prices", {})
    amt = tp.get("mean")
    if amt and amt > 0 and current_price and current_price > 0:
        r = (amt - current_price) / current_price * 100
        if -50 < r < 200: return round(r, 1)
    ah, al = tp.get("high"), tp.get("low")
    if ah and al and current_price and current_price > 0:
        r = ((ah + al) / 2 - current_price) / current_price * 100
        if -50 < r < 200: return round(r, 1)
    tpe = fund.get("trailingPE"); fpe = fund.get("forwardPE")
    if tpe and fpe and tpe > 0 and fpe > 0:
        pct = (tpe - fpe) / tpe * 100
        r = pct * (0.5 if pct > 0 else 0.3)
        if -30 < r < 50: return round(r, 1)
    dcf = fund.get("dcf_valuation", {})
    if not dcf.get("dcf_applicable", True):
        rg = dcf.get("suggested_metrics", {}).get("revenue_growth_yoy")
        if rg: return round(min(rg * 0.5, 25), 1)
    dtp = dcf.get("target_price")
    if dtp and dtp > 0 and current_price and current_price > 0:
        r = (dtp - current_price) / current_price * 100
        if -50 < r < 200: return round(r, 1)
    iv = dcf.get("intrinsic_value")
    if iv and iv > 0 and current_price and current_price > 0:
        r = (iv * 1.20 - current_price) / current_price * 100
        if -50 < r < 200: return round(r, 1)
    mos = dcf.get("margin_of_safety")
    if isinstance(mos, (int, float)) and mos > 0: return round(mos * 100, 1)
    up = fund.get("trading_recommendations", {}).get("upside_potential")
    if isinstance(up, (int, float)) and up > 0: return round(up * 100, 1)
    return round((fund.get("overall_score", 50) - 50) * 0.8, 1)


# ── Main synthesis node ───────────────────────────────────────────────────────

async def synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    from app.tools.nlp import _ollama

    ticker = state["tickers"][0]

    # Validate raw_data ticker consistency
    raw = state.get("raw_data", {})
    if isinstance(raw, dict):
        keys = list(raw.keys())
        if keys and keys[0] != ticker:
            if len(keys) == 1:
                state["raw_data"] = {ticker: raw[keys[0]]}
            elif ticker in raw:
                state["raw_data"] = {ticker: raw[ticker]}

    a = state.get("analysis", {})

    news = a.get("news_sentiment", {})
    yt   = a.get("youtube", {})
    tech = a.get("technicals", {})
    fund = a.get("fundamentals", {}) or a.get("comprehensive_fundamentals", {})
    peer = a.get("peer_analysis", {})
    analyst = a.get("analyst_recommendations", {})
    cash = a.get("cashflow", {})
    lead = a.get("leadership", {})
    sm   = a.get("sector_macro", {})
    growth = a.get("growth_prospects", {})
    valuation = a.get("valuation", {})

    # Strategic conviction - try multiple locations
    sc_data = (a.get("strategic_conviction") or
               state.get("analysis", {}).get("strategic_conviction") or {})
    if not sc_data and state.get("final_output", {}).get("reports"):
        sc_data = state["final_output"]["reports"][0].get("strategic_conviction", {})
    sc_details = sc_data.get("details", {}) if sc_data else {}
    conviction_score = float(sc_details.get("overall_conviction_score", 50.0))
    conviction_level = str(sc_details.get("conviction_level", "Medium Conviction"))
    strategic_rec = str(sc_details.get("strategic_recommendation", "Hold"))

    # Sector rotation
    sr_data = (a.get("sector_rotation") or
               state.get("analysis", {}).get("sector_rotation") or {})
    if not sr_data and state.get("final_output", {}).get("reports"):
        sr_data = state["final_output"]["reports"][0].get("sector_rotation", {})

    current_price = fund.get("current_price") or tech.get("current_price")

    # Use comprehensive fundamentals if available
    comp_fund = a.get("comprehensive_fundamentals", {})
    if comp_fund and comp_fund.get("overall_score"):
        composite_score = comp_fund["overall_score"] / 100.0
        action = comp_fund.get("recommendation", "Hold")
        expected_return = _calculate_expected_return(analyst, comp_fund, current_price)
        positives, negatives = [], []
        for pillar_data in comp_fund.get("pillar_scores", {}).values():
            if isinstance(pillar_data, dict):
                positives.extend(pillar_data.get("positive_factors", [])[:1])
                negatives.extend(pillar_data.get("negative_factors", [])[:1])
        for insight in comp_fund.get("key_insights", []):
            (positives if any(w in insight.lower() for w in ("strong", "good", "excellent", "positive", "attractive")) else
             negatives if any(w in insight.lower() for w in ("weak", "poor", "concern", "risk", "high")) else []).append(insight)
        positives = (positives or ["Strong comprehensive analysis"])[:3]
        negatives = (negatives or ["Market volatility risk"])[:3]
        llm_parsed = True
    else:
        # LLM fallback
        analysis_prompt = f"""You are an expert financial analyst. Analyze {ticker} and provide:
Technical score: {tech.get('signals', {}).get('score', 'N/A')}
PE: {fund.get('pe', 'N/A')}, ROE: {fund.get('roe', 'N/A')}, Revenue Growth: {fund.get('revenueGrowth', 'N/A')}
Analyst consensus: {analyst.get('recommendation_summary', {}).get('consensus', 'N/A')}
Strategic Conviction Score: {sc_details.get('overall_conviction_score', 'N/A')}/100

Respond ONLY with:
SCORE: [0.XX]
ACTION: [Buy/Hold/Sell]
POSITIVES: [factor1], [factor2]
NEGATIVES: [risk1], [risk2]
RETURN: [X.X]%"""

        llm_response = await asyncio.to_thread(_ollama, analysis_prompt)
        composite_score, action, positives, negatives, expected_return = 0.5, "Hold", ["Analysis pending"], ["Analysis pending"], 0.0
        llm_parsed = False

        if llm_response:
            try:
                r = llm_response[:10000].lower()
                for pat in [r'score[:\s]*([0-9]*\.?[0-9]+)', r'overall[:\s]*([0-9]*\.?[0-9]+)']:
                    m = re.search(pat, r)
                    if m:
                        composite_score = min(1.0, max(0.0, float(m.group(1))))
                        llm_parsed = True
                        break
                for pat in [r'action[:\s]*(buy|hold|sell)', r'\b(strong\s+buy|buy|hold|sell|strong\s+sell)\b']:
                    m = re.search(pat, r)
                    if m:
                        action = _score_to_action_with_conviction(composite_score, conviction_level)
                        llm_parsed = True
                        break
                pos_m = re.search(r'\*\*positives:\*\*(.*?)\*\*negatives:', llm_response, re.DOTALL | re.IGNORECASE)
                if pos_m:
                    items = re.findall(r'(?:\d+\.|\*)\s*\*\*([^*]+)\*\*', pos_m.group(1))
                    if items: positives = [t.strip().rstrip(":") for t in items[:3]]
                neg_m = re.search(r'\*\*negatives:\*\*(.*?)(?:\*\*return:|$)', llm_response, re.DOTALL | re.IGNORECASE)
                if neg_m:
                    items = re.findall(r'(?:\d+\.|\*)\s*\*\*([^*]+)\*\*', neg_m.group(1))
                    if items: negatives = [t.strip().rstrip(":") for t in items[:3]]
                rm = re.search(r'return[:\s]*([+-]?[0-9]*\.?[0-9]+)', r)
                if rm:
                    expected_return = float(rm.group(1)); llm_parsed = True
            except Exception as e:
                logger.error(f"Error parsing LLM response: {e}")

    base_score = _calculate_base_score(a)
    if llm_parsed and abs(composite_score - 0.5) > 0.1:
        adj = max(-0.2, min(0.2, composite_score - base_score))
        composite_score = base_score + adj
    else:
        composite_score = base_score
        if not llm_parsed:
            action = _score_to_action_with_conviction(composite_score, conviction_level)
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
                negatives = ["Weak fundamentals", "Negative technicals", "High risk factors"]
            expected_return = _calculate_expected_return(analyst, fund, current_price)

    exec_summary = _build_executive_summary(action, composite_score, a, positives, negatives)

    state["final_output"] = {
        "tickers": [ticker],
        "reports": [{
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
            "strategic_conviction": {"summary": strategic_rec, "confidence": state.get("confidences", {}).get("strategic_conviction", 0.5), "details": sc_data} if sc_data else None,
            "sector_rotation": {"summary": sr_data.get("details", {}).get("recommendation", ""), "confidence": state.get("confidences", {}).get("sector_rotation", 0.5), "details": sr_data} if sr_data else None,
            "earnings_call_analysis": a.get("earnings_calls"),
            "comprehensive_fundamentals": _create_comprehensive_fundamentals_output(comp_fund) if comp_fund else None,
        }],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    senior_rec = _generate_senior_analyst_recommendation(
        ticker=ticker, action=action, score=composite_score, analysis=a,
        positives=positives, negatives=negatives, expected_return=expected_return,
        horizon_short_days=state.get("horizon_short_days", 30),
        horizon_long_days=state.get("horizon_long_days", 365),
    )

    # Re-resolve strategic conviction from final report
    final_report = state["final_output"]["reports"][0]
    fsc = final_report.get("strategic_conviction", {})
    if fsc:
        fd = fsc.get("details", {})
        conviction_score = float(fd.get("overall_conviction_score", 50.0))
        conviction_level = str(fd.get("conviction_level", "Medium Conviction"))
        strategic_rec = str(fd.get("strategic_recommendation", "Hold"))

    risk_assessment = _generate_institutional_risk_assessment(a, final_report, conviction_score)

    final_report["decision"] = {
        "action": action,
        "rating": round(composite_score * 5, 2),
        "recommendation": action,
        "score": round(composite_score * 5, 2),
        "letter_grade": _safe_get_letter_grade(composite_score),
        "stars": _safe_get_star_display(composite_score),
        "professional_rationale": _safe_get_professional_rationale(composite_score, action, positives, negatives, a),
        "expected_return_pct": expected_return,
        "top_reasons_for": positives,
        "top_reasons_against": negatives,
        "llm_parsed": llm_parsed,
        "base_score": round(base_score, 3),
        "professional_recommendation": _safe_get_professional_recommendation(action, composite_score),
        "conviction_level": conviction_level,
        "conviction_score": conviction_score,
        "strategic_recommendation": strategic_rec,
        "risk_assessment": risk_assessment,
        "confidence_score": round(composite_score * 100, 1),
        **{k: senior_rec[k] for k in [
            "executive_summary", "financial_condition_summary", "latest_performance_summary",
            "key_trends", "growth_drivers", "competitive_advantages", "key_risks",
            "quantitative_evidence", "key_ratios_summary", "recent_developments",
            "industry_context", "short_term_outlook", "long_term_outlook",
            "price_target_12m", "price_target_source", "valuation_benchmark",
        ]},
    }

    state["final_output"] = convert_numpy_types(state["final_output"])
    state.setdefault("confidences", {})["synthesis"] = 0.9
    return state
