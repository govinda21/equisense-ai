"""
Deep Financial Analysis Engine
5-10 year financial statement analysis with margins, ratios, CAGR, and earnings quality.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf

from app.utils.validation import DataValidator
from app.utils.rate_limiter import get_yahoo_client

logger = logging.getLogger(__name__)

# --- Config ---

_IS_METRICS = {
    "total_revenue": ["Total Revenue", "Operating Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "EBIT"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "research_development": ["Research Development"],
    "selling_general_admin": ["Selling General And Administration"],
}

_BS_METRICS = {
    "total_assets": ["Total Assets"],
    "total_liabilities": ["Total Liabilities Net Minority Interest"],
    "total_equity": ["Stockholders Equity", "Common Stock Equity"],
    "cash_and_equivalents": ["Cash And Cash Equivalents", "Cash Financial"],
    "total_debt": ["Total Debt", "Long Term Debt"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "working_capital": ["Working Capital"],
    "retained_earnings": ["Retained Earnings"],
}

_CF_METRICS = {
    "operating_cash_flow": ["Total Cash From Operating Activities", "Operating Cash Flow"],
    "investing_cash_flow": ["Total Cash From Investing Activities", "Investing Cash Flow"],
    "financing_cash_flow": ["Total Cash From Financing Activities", "Financing Cash Flow"],
    "free_cash_flow": ["Free Cash Flow"],
    "capital_expenditures": ["Capital Expenditures", "CapEx"],
    "dividends_paid": ["Dividends Paid"],
}

_SCORE_MAP = {"excellent": 85, "good": 75, "fair": 65, "moderate": 60, "poor": 45, "weak": 35, "unknown": 50}


# --- Helpers ---

def _extract(df: pd.DataFrame, keys: List[str]) -> List[float]:
    for k in keys:
        if k in df.index:
            series = df.loc[k].dropna()
            # Ensure chronological order (oldest → newest)
            series = series.sort_index()
            return [float(v) for v in series.values if v is not None]
    return []


def _cagr(values: List[float], years: int) -> Optional[float]:
    if len(values) < 2 or years <= 0:
        return None
    n = min(years, len(values) - 1)
    logger.info(f"CAGR calculation for values: {values}, years: {years}, n: {n}")  
    first, last = values[-n - 1], values[-1]
    if first and last and first > 0 and last > 0:
        try:
            return (last / first) ** (1.0 / n) - 1.0
        except Exception:
            return None
    return None


def _yoy_growth(values: List[float]) -> Optional[float]:
    if len(values) < 2 or values[-2] == 0:
        return None
    return (values[-1] - values[-2]) / abs(values[-2])


def _volatility(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = float(np.mean(values))
    return float(np.std(values)) / abs(mean) if mean != 0 else None


def _trend(values: List[float]) -> str:
    if len(values) < 3:
        return "unknown"
    slope = np.polyfit(range(len(values)), values, 1)[0]
    mean = abs(float(np.mean(values)))
    if mean == 0:
        return "stable"
    rel = slope / mean
    return "increasing" if rel > 0.02 else "decreasing" if rel < -0.02 else "stable"


def _metric_stats(values: List[float]) -> Dict[str, Any]:
    return {
        "values": values,
        "latest": values[-1] if values else None,
        "previous": values[-2] if len(values) > 1 else None,
        "yoy_growth": _yoy_growth(values),
        "cagr_5y": _cagr(values, 5),
        "cagr_10y": _cagr(values, 10),
        "volatility": _volatility(values),
    }


def _margin_stats(numerator: List[float], denominator: List[float]) -> Dict[str, Any]:
    if not numerator or not denominator:
        return {}
    vals = [n / d if d != 0 else 0 for n, d in zip(numerator, denominator)]
    return {
        "values": vals,
        "latest": vals[-1] if vals else None,
        "average": float(np.mean(vals)) if vals else None,
        "trend": _trend(vals),
    }


def _ratio_stats(numerator: List[float], denominator: List[float],
                 skip_zero_denom: bool = True) -> Dict[str, Any]:
    if not numerator or not denominator:
        return {}
    pairs = [(n, d) for n, d in zip(numerator, denominator) if not (skip_zero_denom and d == 0)]
    if not pairs:
        return {}
    vals = [n / d for n, d in pairs]
    return {"values": vals, "latest": vals[-1], "average": float(np.mean(vals)), "trend": _trend(vals)}


def _quality_label(volatility: Optional[float]) -> str:
    if volatility is None:
        return "unknown"
    return "excellent" if volatility < 0.1 else "good" if volatility < 0.2 else "fair" if volatility < 0.3 else "poor"


def _score_to_grade(score: float) -> str:
    if score >= 85: return "A"
    if score >= 75: return "B"
    if score >= 65: return "C+"
    if score >= 55: return "C"
    if score >= 45: return "C-"
    if score >= 35: return "D"
    return "F"


def _label_to_numeric(label: str) -> float:
    return _SCORE_MAP.get(label, 50)


# --- Analysis functions ---

def _analyze_statement(df: pd.DataFrame, metric_config: Dict[str, List[str]]) -> Dict[str, Any]:
    return {name: _metric_stats(_extract(df, keys)) for name, keys in metric_config.items()
            if _extract(df, keys)}


def _analyze_margins(is_df: pd.DataFrame) -> Dict[str, Any]:
    # logger.info(f"is_df: {is_df}")
    revenue = _extract(is_df, ["Total Revenue", "Revenue"])
    gross = _extract(is_df, ["Gross Profit"])
    operating = _extract(is_df, ["Operating Income", "EBIT"])
    net = _extract(is_df, ["Net Income"])
    logger.info(f"Extracted revenue: {revenue}, gross: {gross}, operating: {operating}, net: {net}")
    out: Dict[str, Any] = {}
    if revenue:
        out["revenue"] = {"values": revenue, "cagr_5y": _cagr(revenue, 5),
                          "cagr_10y": _cagr(revenue, 10), "volatility": _volatility(revenue)}
    if revenue and gross: out["gross_margin"] = _margin_stats(gross, revenue)
    if revenue and operating: out["operating_margin"] = _margin_stats(operating, revenue)
    if revenue and net: out["net_margin"] = _margin_stats(net, revenue)
    return out


def _analyze_growth(is_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, keys, src in [
        ("revenue_growth", ["Total Revenue", "Revenue"], is_df),
        ("earnings_growth", ["Net Income"], is_df),
        ("asset_growth", ["Total Assets"], bs_df),
        ("equity_growth", ["Stockholders Equity", "Common Stock Equity"], bs_df),
    ]:
        vals = _extract(src, keys)
        if len(vals) > 1:
            out[name] = {
                "yoy_growth": _yoy_growth(vals),
                "cagr_3y": _cagr(vals, 3), "cagr_5y": _cagr(vals, 5), "cagr_10y": _cagr(vals, 10),
                "volatility": _volatility(vals),
            }
    return out


def _analyze_ratios(is_df: pd.DataFrame, bs_df: pd.DataFrame, cf_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    ratios: Dict[str, Any] = {}
    rev = _extract(is_df, ["Total Revenue", "Revenue"])
    ni = _extract(is_df, ["Net Income", "Net Income Common Stockholders"])
    ebit = _extract(is_df, ["EBIT", "Operating Income"])
    ie = _extract(is_df, ["Interest Expense", "Total Interest Expense"])
    ta = _extract(bs_df, ["Total Assets"])
    te = _extract(bs_df, ["Stockholders Equity", "Common Stock Equity"])
    td = _extract(bs_df, ["Total Debt", "Long Term Debt"])
    ca = _extract(bs_df, ["Current Assets"])
    cl = _extract(bs_df, ["Current Liabilities"])
    cash = _extract(bs_df, ["Cash And Cash Equivalents", "Cash Financial"])
    inv = _extract(bs_df, ["Inventory"])

    if ni and te: ratios["roe"] = _ratio_stats(ni, te)
    if ni and ta: ratios["roa"] = _ratio_stats(ni, ta)
    if rev and ta: ratios["asset_turnover"] = _ratio_stats(rev, ta)
    if td and te: ratios["debt_to_equity"] = _ratio_stats(td, te)
    if td and ta: ratios["debt_to_assets"] = _ratio_stats(td, ta)
    if ca and cl: ratios["current_ratio"] = _ratio_stats(ca, cl)
    if cash and cl: ratios["cash_ratio"] = _ratio_stats(cash, cl)
    if ebit and ie:
        pairs = [(e, abs(i)) for e, i in zip(ebit, ie) if i != 0]
        if pairs:
            vals = [e / i for e, i in pairs]
            ratios["interest_coverage"] = {"values": vals, "latest": vals[-1],
                                           "average": float(np.mean(vals)), "trend": _trend(vals)}
    if ca and cl:
        quick = [c - (iv if iv else 0) for c, iv in zip(ca, inv)] if inv else ca
        ratios["quick_ratio"] = _ratio_stats(quick, cl)
    if cf_df is not None and not cf_df.empty:
        fcf = _extract(cf_df, ["Free Cash Flow"])
        if fcf and rev: ratios["fcf_margin"] = _margin_stats(fcf, rev)
        if fcf: ratios["fcf_trend"] = _metric_stats(fcf)
    return ratios


def _assess_earnings_quality(is_df: pd.DataFrame, cf_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
    ni = _extract(is_df, ["Net Income", "Net Income Common Stockholders"])
    cfo = _extract(cf_df, ["Total Cash From Operating Activities", "Operating Cash Flow"])
    rev = _extract(is_df, ["Total Revenue", "Operating Revenue"])

    quality: Dict[str, Any] = {}

    # CFO vs Net Income
    if ni and cfo:
        ratios = [c / n for c, n in zip(cfo, ni) if n != 0]
        if ratios:
            avg = float(np.mean(ratios))
            quality["cfo_to_net_income"] = {
                "ratios": ratios, "average": avg,
                "quality_score": "excellent" if avg > 1.2 else "good" if avg > 1.0 else
                                 "fair" if avg > 0.8 else "poor",
                "red_flag": avg < 0.5
            }

    # Accrual quality
    if ni and cfo:
        accruals = [n - c for n, c in zip(ni[:len(cfo)], cfo[:len(ni)])]
        ta = _extract(bs_df, ["Total Assets"])
        norm = [a / t for a, t in zip(accruals, ta) if t != 0] if ta else []
        if len(accruals) >= 3:
            vol = _volatility(accruals)
            quality["accrual_quality"] = {
                "values": accruals, "normalized": norm,
                "quality_score": _quality_label(vol)
            }

    # Revenue quality
    if rev and len(rev) >= 3:
        growth = [((rev[i] - rev[i-1]) / abs(rev[i-1])) if rev[i-1] else 0 for i in range(1, len(rev))]
        pos_pct = sum(1 for g in growth if g > 0) / len(growth)
        vol = _volatility(growth)
        quality["revenue_quality"] = {
            "growth_rates": growth,
            "consistency_score": "excellent" if pos_pct >= 0.8 else "good" if pos_pct >= 0.6 else "fair",
            "volatility": vol,
            "quality_score": "excellent" if pos_pct >= 0.8 and (vol or 1) < 0.15 else
                             "good" if pos_pct >= 0.6 else "fair"
        }

    # Manipulation indicators
    indicators: Dict[str, Any] = {}
    if ni and cfo and len(ni) >= 3:
        ratios = [c / n for c, n in zip(cfo, ni) if n != 0]
        if ratios:
            avg = float(np.mean(ratios))
            indicators["cfo_ni_divergence"] = {
                "average_ratio": avg, "red_flag": avg < 0.5,
                "severity": "high" if avg < 0.3 else "medium" if avg < 0.5 else "low"
            }
    if rev and cfo:
        ratios = [c / r for c, r in zip(cfo, rev) if r != 0]
        if ratios:
            avg = float(np.mean(ratios))
            indicators["revenue_cf_divergence"] = {
                "average_ratio": avg, "red_flag": avg < 0.05,
                "severity": "high" if avg < 0.02 else "medium" if avg < 0.05 else "low"
            }
    flags = [v for k, v in indicators.items() if isinstance(v, dict) and v.get("red_flag")]
    if flags:
        sev_scores = {"low": 1, "medium": 2, "high": 3}
        avg_sev = float(np.mean([sev_scores.get(f.get("severity", "low"), 1) for f in flags]))
        risk = "high" if avg_sev >= 2.5 else "medium" if avg_sev >= 1.5 else "low"
    else:
        risk, avg_sev = "low", 0.0
    quality["manipulation_indicators"] = {**indicators,
        "overall_risk_score": {"risk_level": risk, "risk_score": avg_sev,
                               "overall_assessment": "clean" if risk == "low" else "monitor" if risk == "medium" else "investigate"}}

    # Overall quality score
    scores = [(quality.get("cfo_to_net_income", {}).get("quality_score", "unknown"), 0.4),
              (quality.get("accrual_quality", {}).get("quality_score", "unknown"), 0.25),
              (quality.get("revenue_quality", {}).get("quality_score", "unknown"), 0.20)]
    numeric = [(_label_to_numeric(label), w) for label, w in scores]
    total_w = sum(w for _, w in numeric)
    ws = sum(s * w for s, w in numeric) / total_w if total_w > 0 else 50
    quality["overall_quality_score"] = {"score": ws, "grade": _score_to_grade(ws)}

    return quality


def _assess_balance_sheet_strength(bs_df: pd.DataFrame, is_df: pd.DataFrame, cf_df: pd.DataFrame) -> Dict[str, Any]:
    td = _extract(bs_df, ["Total Debt", "Long Term Debt"])
    te = _extract(bs_df, ["Stockholders Equity", "Common Stock Equity"])
    ta = _extract(bs_df, ["Total Assets"])
    ca = _extract(bs_df, ["Current Assets"])
    cl = _extract(bs_df, ["Current Liabilities"])
    cash = _extract(bs_df, ["Cash And Cash Equivalents", "Cash"])
    ebit = _extract(is_df, ["EBIT", "Operating Income"])
    ie = _extract(is_df, ["Interest Expense"])

    strength: Dict[str, Any] = {}

    if td and te:
        de_ratios = [d / e if e != 0 else 0 for d, e in zip(td, te)]
        avg_de = float(np.mean(de_ratios)) if de_ratios else 0
        de_label = "excellent" if avg_de < 0.2 else "good" if avg_de < 0.4 else "fair" if avg_de < 0.6 else "poor"
        da_ratios = [d / a if a != 0 else 0 for d, a in zip(td, ta)] if ta else []
        strength["debt_analysis"] = {
            "debt_equity_ratio": {"latest": de_ratios[-1] if de_ratios else None,
                                  "average": avg_de, "trend": _trend(de_ratios), "strength_score": de_label},
            "debt_asset_ratio": {"latest": da_ratios[-1] if da_ratios else None,
                                 "average": float(np.mean(da_ratios)) if da_ratios else None}
        }

    if ebit and ie:
        ic_vals = [e / abs(i) for e, i in zip(ebit, ie) if i != 0]
        if ic_vals:
            min_ic, avg_ic = min(ic_vals), float(np.mean(ic_vals))
            ic_label = ("excellent" if min_ic >= 5 and avg_ic >= 8 else
                        "good" if min_ic >= 3 and avg_ic >= 5 else
                        "fair" if min_ic >= 2 and avg_ic >= 3 else "poor")
            strength["interest_coverage"] = {"coverage_ratios": ic_vals, "latest": ic_vals[-1],
                                              "average": avg_ic, "minimum": min_ic,
                                              "trend": _trend(ic_vals), "adequacy_score": ic_label}

    if ca and cl:
        cr_vals = [c / l if l != 0 else 0 for c, l in zip(ca, cl)]
        avg_cr = float(np.mean(cr_vals)) if cr_vals else 0
        cr_label = "excellent" if avg_cr >= 2.0 else "good" if avg_cr >= 1.5 else "fair" if avg_cr >= 1.2 else "poor"
        strength["liquidity"] = {
            "current_ratio": {"latest": cr_vals[-1] if cr_vals else None, "average": avg_cr,
                              "trend": _trend(cr_vals), "strength_score": cr_label}
        }
        if cash:
            cash_r = [c / l if l != 0 else 0 for c, l in zip(cash, cl)]
            strength["liquidity"]["cash_ratio"] = {"latest": cash_r[-1] if cash_r else None,
                                                   "average": float(np.mean(cash_r)) if cash_r else None}

    if cash and ta:
        car = [c / a if a != 0 else 0 for c, a in zip(cash, ta)]
        avg_car = float(np.mean(car)) if car else 0
        cash_label = "excellent" if avg_car > 0.15 else "good" if avg_car > 0.10 else "fair" if avg_car > 0.05 else "poor"
        strength["cash_position"] = {
            "cash_asset_ratio": {"latest": car[-1] if car else None, "average": avg_car},
            "trend": _trend(cash), "adequacy_score": cash_label
        }

    # Overall balance sheet score
    component_scores = [
        (_label_to_numeric(strength.get("debt_analysis", {}).get("debt_equity_ratio", {}).get("strength_score", "unknown")), 0.25),
        (_label_to_numeric(strength.get("interest_coverage", {}).get("adequacy_score", "unknown")), 0.20),
        (_label_to_numeric(strength.get("liquidity", {}).get("current_ratio", {}).get("strength_score", "unknown")), 0.25),
        (_label_to_numeric(strength.get("cash_position", {}).get("adequacy_score", "unknown")), 0.20),
    ]
    total_w = sum(w for _, w in component_scores)
    ws = sum(s * w for s, w in component_scores) / total_w if total_w > 0 else 50
    strength["overall_balance_sheet_score"] = {
        "score": ws, "grade": _score_to_grade(ws),
        "strength_level": "strong" if ws >= 75 else "moderate" if ws >= 55 else "weak"
    }
    return strength


# --- Main class ---

class DeepFinancialAnalyzer:

    def __init__(self):
        self.validator = DataValidator()
        self.yahoo_client = get_yahoo_client()

    async def analyze_financial_history(self, ticker: str, years_back: int = 10) -> Dict[str, Any]:
        try:
            logger.info(f"Starting deep financial analysis for {ticker} ({years_back} years)")
            financial_data = await self._fetch_statements(ticker)
            if not financial_data:
                return self._empty()

            is_df = financial_data["income_statement"]
            bs_df = financial_data["balance_sheet"]
            cf_df = financial_data["cash_flow"]

            results = await asyncio.gather(
                asyncio.to_thread(lambda: _analyze_statement(is_df, _IS_METRICS)),
                asyncio.to_thread(lambda: _analyze_statement(bs_df, _BS_METRICS)),
                asyncio.to_thread(lambda: _analyze_statement(cf_df, _CF_METRICS)),
                asyncio.to_thread(lambda: _analyze_ratios(is_df, bs_df, cf_df)),
                asyncio.to_thread(lambda: _analyze_margins(is_df)),
                asyncio.to_thread(lambda: _analyze_growth(is_df, bs_df)),
                asyncio.to_thread(lambda: _assess_earnings_quality(is_df, cf_df, bs_df)),
                asyncio.to_thread(lambda: _assess_balance_sheet_strength(bs_df, is_df, cf_df)),
                return_exceptions=True
            )
            labels = ["income_statement_trends", "balance_sheet_trends", "cash_flow_trends",
                      "financial_ratios", "margins_and_efficiency", "growth_metrics",
                      "earnings_quality", "balance_sheet_strength"]

            return {
                "ticker": ticker, "analysis_period_years": years_back,
                "analysis_date": datetime.now().isoformat(),
                **{lbl: (r if not isinstance(r, Exception) else {}) for lbl, r in zip(labels, results)},
                "summary": {"overall_grade": "B", "key_strengths": [], "key_concerns": []}
            }
        except Exception as e:
            logger.error(f"Error in deep financial analysis for {ticker}: {e}")
            return self._empty()

    async def _fetch_statements(self, ticker: str) -> Optional[Dict[str, pd.DataFrame]]:
        try:
            t = yf.Ticker(ticker)
            fs = t.financials
            bs = t.balance_sheet
            cf = t.cashflow
            if fs.empty and bs.empty and cf.empty:
                return None
            return {
                "income_statement": fs, "balance_sheet": bs, "cash_flow": cf,
                "quarters": t.quarterly_financials,
                "quarters_balance": t.quarterly_balance_sheet,
                "quarters_cashflow": t.quarterly_cashflow
            }
        except Exception as e:
            logger.error(f"Error fetching financial statements for {ticker}: {e}")
            return None

    def _empty(self) -> Dict[str, Any]:
        return {
            "ticker": "", "analysis_period_years": 0,
            "analysis_date": datetime.now().isoformat(),
            "income_statement_trends": {}, "balance_sheet_trends": {},
            "cash_flow_trends": {}, "financial_ratios": {},
            "margins_and_efficiency": {}, "growth_metrics": {},
            "earnings_quality": {}, "balance_sheet_strength": {},
            "summary": {"overall_grade": "Unknown", "key_strengths": [],
                        "key_concerns": ["Insufficient financial data"]}
        }


# Global instance
deep_financial_analyzer = DeepFinancialAnalyzer()
