"""
Growth Prospects Analysis
Historical revenue/earnings growth, sector outlook, and forward projections
with mean-reversion modelling across 1-year, 3-year, and 5-year horizons.
"""
from __future__ import annotations

import asyncio
import statistics
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from app.tools.finance import fetch_info


# ---------- helpers ----------

def _safe(x: Any) -> Optional[float]:
    try:
        f = float(x)
        return None if f != f else f
    except Exception:
        return None


def _cagr(df: pd.DataFrame, metric: str) -> Dict[str, float]:
    """Compute 3-year and 5-year CAGR for a given income-statement row."""
    result = {}
    if df is None or df.empty or metric not in df.index:
        return result
    s = df.loc[metric].dropna().sort_index()
    cur = float(s.iloc[-1])
    if len(s) >= 3:
        base = float(s.iloc[-3])
        if base > 0:
            result["3year"] = (cur / base) ** (1 / 2) - 1
    if len(s) >= 5:
        base = float(s.iloc[-5])
        if base > 0:
            result["5year"] = (cur / base) ** (1 / 4) - 1
    return result


def _quarterly_trends(df: pd.DataFrame) -> Dict[str, Any]:
    """Average QoQ revenue growth and trend direction from last 4 quarters."""
    if df is None or df.empty or "Total Revenue" not in df.index:
        return {"note": "Insufficient quarterly data"}
    s = df.loc["Total Revenue"].dropna()
    if len(s) < 4:
        return {"note": "Insufficient quarterly data"}
    qoq = [(s.iloc[i] / s.iloc[i - 1] - 1) for i in range(1, len(s)) if s.iloc[i - 1]]
    avg = statistics.mean(qoq[-4:])
    return {
        "avg_qoq_growth": avg,
        "latest_qoq":     qoq[-1] if qoq else None,
        "trend":          "Accelerating" if qoq[-1] > avg else "Decelerating",
        "consistency":    "High" if all(g > -0.05 for g in qoq[-4:]) else "Variable",
    }


# ---------- sector profiles ----------

_SECTORS: Dict[str, Dict] = {
    "Technology":          {"drivers": ["Digital transformation", "Cloud", "AI/ML", "IoT"],           "outlook": "Strong",   "cyclicality": "Low",       "disruption": "High"},
    "Healthcare":          {"drivers": ["Aging population", "Medical innovation", "Emerging markets"], "outlook": "Stable",   "cyclicality": "Low",       "disruption": "Medium"},
    "Financial Services":  {"drivers": ["Economic growth", "Interest rates", "Digital banking"],       "outlook": "Moderate", "cyclicality": "High",      "disruption": "Medium"},
    "Consumer Cyclical":   {"drivers": ["Consumer spending", "Demographics", "Market share"],          "outlook": "Variable", "cyclicality": "High",      "disruption": "Medium"},
    "Energy":              {"drivers": ["Commodity prices", "Energy transition", "Global demand"],     "outlook": "Volatile", "cyclicality": "Very High", "disruption": "High"},
}
_DEFAULT_SECTOR = {"drivers": ["Market expansion", "Efficiency"], "outlook": "Mixed", "cyclicality": "Medium", "disruption": "Medium"}

_OUTLOOK_GROWTH = {"Strong": 0.08, "Stable": 0.05, "Moderate": 0.04, "Variable": 0.03, "Volatile": 0.02}


def _sector_norm(outlook: str) -> float:
    return _OUTLOOK_GROWTH.get(outlook, 0.04)


def _mean_revert(base: float, norm: float, years: float, decay: float = 0.20) -> float:
    return norm + (base - norm) * ((1 - decay) ** years)


def _confidence(has_ttm: bool, has_3y: bool, has_5y: bool, has_qtrly: bool,
                consistency: str, cyclicality: str, disruption: str,
                horizon_years: int) -> float:
    data_score  = sum([has_ttm, has_3y, has_5y, has_qtrly]) / 4 * 0.30
    cons_score  = {"High": 0.30, "Variable": 0.15}.get(consistency, 0.05)
    sector_score = 0.20 if (cyclicality == "Low" and disruption == "Low") \
                   else 0.12 if cyclicality in ("Low","Medium") \
                   else 0.05
    time_score  = {1: 0.20, 3: 0.12}.get(horizon_years, 0.05)
    return round(max(0.2, min(0.9, data_score + cons_score + sector_score + time_score)), 2)


# ---------- main logic ----------

def _analyze(ticker: str) -> Dict[str, Any]:
    t = yf.Ticker(ticker)
    info = t.info or {}
    financials = getattr(t, "financials", None)
    quarterly  = getattr(t, "quarterly_financials", None)

    sector   = info.get("sector", "Unknown")
    industry = info.get("industry", "Unknown")
    sp       = _SECTORS.get(sector, _DEFAULT_SECTOR)

    # Historical growth
    rev_ttm  = _safe(info.get("revenueGrowth"))
    earn_ttm = _safe(info.get("earningsGrowth"))
    cagr     = _cagr(financials, "Total Revenue") if financials is not None else {}
    qtrly    = _quarterly_trends(quarterly) if quarterly is not None else {}

    consistency = qtrly.get("consistency", "Variable")
    has_ttm, has_3y, has_5y = rev_ttm is not None, "3year" in cagr, "5year" in cagr
    has_qtrly = isinstance(qtrly.get("avg_qoq_growth"), float)

    base_growth = rev_ttm or cagr.get("3year") or 0.05
    norm        = _sector_norm(sp["outlook"])

    # Maturity factor by market cap
    mktcap = _safe(info.get("marketCap")) or 0
    mat = 0.85 if mktcap > 100e9 else 1.10 if mktcap < 10e9 else 1.0

    # Strategic boost (innovation / financial flexibility)
    bus = (info.get("businessSummary") or "").lower()
    innov  = sum(1 for w in ["innovation","technology","research","patent"] if w in bus)
    innov_boost = 0.02 if innov >= 3 else 0.01 if innov >= 1 else 0
    flex_score = 0.015 if (_safe(info.get("debtToEquity")) or 99) < 50 else 0.005
    boost = innov_boost + flex_score

    # Build horizons
    def _horizon(years_ahead: float, hz_int: int, cap_lo: float, cap_hi: float, boost_factor: float):
        g = (_mean_revert(base_growth, norm, years_ahead) + boost * boost_factor) * mat
        g = round(max(cap_lo, min(cap_hi, g)), 4)
        conf = _confidence(has_ttm, has_3y, has_5y, has_qtrly,
                           consistency, sp["cyclicality"], sp["disruption"], hz_int)
        return g, conf

    g1, c1 = _horizon(0.5, 1, -0.05, 0.30, 1.0)
    g3, c3 = _horizon(2.0, 3, -0.02, 0.20, 0.8)
    g5, c5 = _horizon(5.0, 5,  0.00, 0.12, 0.5)

    avg_g = statistics.mean([g1, g3, g5])
    avg_c = statistics.mean([c1, c3, c5])
    outlook_label = ("Strong" if avg_g > 0.08 else "Moderate" if avg_g > 0.05
                     else "Slow" if avg_g > 0.02 else "Limited") + " Growth Expected"

    # Quality assessment
    quality = {}
    if rev_ttm and earn_ttm:
        quality["profitability_trend"] = (
            "Improving margins" if earn_ttm > rev_ttm > 0
            else "Margin pressure" if rev_ttm > 0 > earn_ttm else "Mixed"
        )
    if has_3y and has_5y:
        quality["consistency"] = "High" if abs(cagr["3year"] - cagr["5year"]) < 0.03 else "Variable"

    return {
        "historical_growth": {
            "metrics": {
                "revenue_growth_ttm": rev_ttm, "earnings_growth_ttm": earn_ttm,
                "revenue_cagr_3y": cagr.get("3year"), "revenue_cagr_5y": cagr.get("5year"),
                "quarterly_trends": qtrly,
            },
            "quality_assessment": quality,
        },
        "sector_analysis": {
            "sector": sector, "industry": industry,
            "sector_outlook": sp["outlook"], "growth_drivers": sp["drivers"],
            "cyclicality": sp["cyclicality"], "disruption_risk": sp["disruption"],
        },
        "growth_outlook": {
            "short_term": {"period": "1 year",  "revenue_growth_estimate": g1, "confidence_score": c1,
                           "confidence_level": "High" if c1 > 0.7 else "Medium" if c1 > 0.5 else "Low"},
            "medium_term": {"period": "3 years", "revenue_growth_estimate": g3, "confidence_score": c3,
                            "confidence_level": "High" if c3 > 0.7 else "Medium" if c3 > 0.5 else "Low"},
            "long_term":  {"period": "5+ years","revenue_growth_estimate": g5, "confidence_score": c5,
                           "confidence_level": "High" if c5 > 0.7 else "Medium" if c5 > 0.5 else "Low"},
            "overall_outlook": outlook_label,
            "average_growth_rate": round(avg_g, 4),
            "average_confidence":  round(avg_c, 2),
            "sector_long_term_norm": round(norm, 4),
            "summary": f"{outlook_label}. Key drivers: {', '.join(sp['drivers'][:2])}",
        },
        "summary": f"{outlook_label}. Key drivers: {', '.join(sp['drivers'][:2])}",
    }


async def analyze_growth_prospects(ticker: str) -> Dict[str, Any]:
    """Analyze historical growth patterns and forward prospects for a ticker."""
    return await asyncio.to_thread(_analyze, ticker)
