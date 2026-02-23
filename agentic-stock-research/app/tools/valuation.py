from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import yfinance as yf

from app.tools.finance import fetch_info

_OCF_KEYS = ["Total Cash From Operating Activities",
             "Cash Flow From Continuing Operating Activities",
             "Operating Cash Flow", "Net Cash From Operating Activities"]
_CAPEX_KEYS = ["Capital Expenditures", "Capital Expenditure", "Capex",
               "Purchase Of Property Plant Equipment"]
_INDUSTRY_PE = {
    "Technology": {"pe": 22.0, "pb": 4.5, "ev_ebitda": 15.0},
    "Healthcare": {"pe": 18.0, "pb": 3.2, "ev_ebitda": 12.0},
    "Financial Services": {"pe": 12.0, "pb": 1.2, "ev_ebitda": 8.0},
    "Consumer Cyclical": {"pe": 16.0, "pb": 2.8, "ev_ebitda": 10.0},
    "Consumer Defensive": {"pe": 15.0, "pb": 2.5, "ev_ebitda": 9.0},
    "Energy": {"pe": 12.0, "pb": 1.8, "ev_ebitda": 6.0},
    "Utilities": {"pe": 14.0, "pb": 1.5, "ev_ebitda": 8.0},
    "Real Estate": {"pe": 16.0, "pb": 1.4, "ev_ebitda": 12.0},
    "Basic Materials": {"pe": 13.0, "pb": 1.9, "ev_ebitda": 7.0},
    "Communication Services": {"pe": 20.0, "pb": 3.0, "ev_ebitda": 11.0},
}
_DEFAULT_MULTIPLES = {"pe": 16.0, "pb": 2.5, "ev_ebitda": 10.0}


def _f(x: Any) -> Optional[float]:
    try:
        v = float(x)
        return None if v != v else v  # NaN check
    except Exception:
        return None


def _get_fcf(ticker: str, info: Dict[str, Any]) -> Optional[float]:
    if fcf := _f(info.get("freeCashflow")):
        return fcf
    try:
        cf = yf.Ticker(ticker).cashflow
        if cf is None or getattr(cf, "empty", True):
            return None
        ocf = next((cf.loc[k].dropna() for k in _OCF_KEYS if k in cf.index), None)
        capex = next((cf.loc[k].dropna() for k in _CAPEX_KEYS if k in cf.index), None)
        if ocf is not None and capex is not None and len(ocf) > 0 and len(capex) > 0:
            o, c = _f(ocf.iloc[-1]), _f(capex.iloc[-1])
            return o + c if o is not None and c is not None else None
    except Exception:
        pass
    return None


def _dcf_band(fcf0: float, shares: Optional[float], mkt_cap: Optional[float],
              g: float, r: float, tg: float) -> Dict[str, Any]:
    def _pv(g, r, tg):
        fcf, pv = fcf0, 0.0
        for t in range(1, 6):
            fcf *= (1 + g)
            pv += fcf / (1 + r) ** t
        tv = fcf * (1 + tg) / (r - tg) if r > tg else 0.0
        return pv + tv / (1 + r) ** 5

    scenarios = {
        "low": {"g": max(0, g - 0.02), "r": max(0.05, r + 0.01), "tg": max(0, tg - 0.005)},
        "base": {"g": g, "r": r, "tg": tg},
        "high": {"g": g + 0.02, "r": max(0.05, r - 0.01), "tg": tg + 0.005},
    }
    caps = {k: _pv(**v) for k, v in scenarios.items()}
    prices = {k: cap / shares if shares and shares > 0 else None for k, cap in caps.items()}
    return {"market_cap": mkt_cap, "intrinsic_market_cap": caps, "intrinsic_price": prices}


def _dcf_analysis(fcf0, g, r, tg, shares, mkt_cap, price) -> Dict[str, Any]:
    if not fcf0 or fcf0 <= 0:
        return {"applicable": False, "reason": "Insufficient FCF data"}
    base = _dcf_band(fcf0, shares, mkt_cap, g, r, tg)
    return {
        "applicable": True, "base_case": base,
        "scenarios": {
            "conservative": _dcf_band(fcf0, shares, mkt_cap, max(0.02, g - 0.03), r + 0.01, max(0.02, tg - 0.005)),
            "optimistic": _dcf_band(fcf0, shares, mkt_cap, min(0.12, g + 0.03), max(0.08, r - 0.01), min(0.04, tg + 0.005)),
            "recession": _dcf_band(fcf0, shares, mkt_cap, max(0, g - 0.05), r + 0.02, max(0.015, tg - 0.01)),
        },
        "methodology": "5-year DCF with terminal value"
    }


def _ddm(info: Dict[str, Any], r: float) -> Dict[str, Any]:
    dy = _f(info.get("dividendYield"))
    dr = _f(info.get("dividendRate"))
    if not dy or dy < 0.01:
        return {"applicable": False, "reason": "No meaningful dividend yield"}
    dg = min((_f(info.get("earningsGrowth")) or 0.05) * 0.8, 0.08)
    if dg >= r:
        dg = r * 0.8
    if not dr or dg >= r:
        return {"applicable": False, "reason": "Insufficient dividend data"}
    return {"applicable": True, "current_dividend": dr, "estimated_growth": dg,
            "ddm_value_per_share": dr * (1 + dg) / (r - dg),
            "yield_on_cost": dy, "methodology": "Gordon Growth Model"}


def _comps(ticker: str, info: Dict[str, Any], price: Optional[float]) -> Dict[str, Any]:
    mults = _INDUSTRY_PE.get(info.get("sector", ""), _DEFAULT_MULTIPLES)
    analysis = {}
    pe, pb, ev_eb, ev_r, peg = (_f(info.get(k)) for k in
                                  ["trailingPE", "priceToBook", "enterpriseToEbitda",
                                   "enterpriseToRevenue", "pegRatio"])
    if pe and price:
        analysis["pe_based"] = {"current_multiple": pe, "industry_average": mults.get("pe"),
                                 "implied_price": price / pe * mults.get("pe", pe)}
    if pb and price:
        analysis["pb_based"] = {"current_multiple": pb, "industry_average": mults.get("pb"),
                                 "implied_price": price / pb * mults.get("pb", pb)}
    if ev_eb:
        analysis["ev_ebitda"] = {"current_multiple": ev_eb, "industry_average": mults.get("ev_ebitda")}
    return {"applicable": bool(analysis), "multiples_analysis": analysis, "methodology": "Industry peer comparison"}


def _sotp(info: Dict[str, Any]) -> Dict[str, Any]:
    summary = info.get("businessSummary", "")
    if len(summary) < 200:
        return {"applicable": False, "reason": "Insufficient business segment data"}
    indicators = ["segment", "division", "subsidiary", "unit", "business", "operation"]
    if sum(1 for kw in indicators if kw in summary.lower()) < 3:
        return {"applicable": False, "reason": "Appears to be single-business company"}
    return {"applicable": True, "note": "Multi-segment company identified",
            "recommendation": "Detailed segment analysis recommended",
            "methodology": "Sum-of-the-Parts approach suggested"}


def _sensitivity(fcf0, g, r, tg, shares) -> Dict[str, Any]:
    if not fcf0 or fcf0 <= 0 or not shares:
        return {"applicable": False, "reason": "Insufficient data"}
    gr = [g - 0.02, g, g + 0.02]
    dr = [r - 0.01, r, r + 0.01]
    tr = [max(0.015, tg - 0.005), tg, tg + 0.005]
    matrix = [[_dcf_band(fcf0, shares, None, gg, dd, tg).get("intrinsic_price", {}).get("base")
               if gg < dd else None for dd in dr] for gg in gr]
    term_sens = [_dcf_band(fcf0, shares, None, g, r, t).get("intrinsic_price", {}).get("base")
                 if g < r else None for t in tr]
    return {"applicable": True,
            "sensitivity_matrix": {
                "growth_vs_discount": {"growth_rates": gr, "discount_rates": dr, "price_matrix": matrix},
                "terminal_growth": {"terminal_rates": tr, "prices": term_sens},
            },
            "methodology": "Monte Carlo-style sensitivity analysis"}


def _consolidate(valuations: Dict[str, Any], price: Optional[float]) -> Dict[str, Any]:
    prices, weights = [], {}
    if valuations.get("dcf", {}).get("applicable"):
        if p := valuations["dcf"].get("base_case", {}).get("intrinsic_price", {}).get("base"):
            prices.append(p); weights["dcf"] = 0.4
    if valuations.get("ddm", {}).get("applicable"):
        if p := valuations["ddm"].get("ddm_value_per_share"):
            prices.append(p); weights["ddm"] = 0.3
    if valuations.get("comparables", {}).get("applicable"):
        comp_prices = [valuations["comparables"]["multiples_analysis"].get(k, {}).get("implied_price")
                       for k in ["pe_based", "pb_based"]]
        comp_prices = [p for p in comp_prices if p]
        if comp_prices:
            prices.append(sum(comp_prices) / len(comp_prices))
            weights["comparables"] = 0.3
    if not prices:
        return {"target_price": None, "valuation_range": {}, "confidence": "Low",
                "summary": "Insufficient data for consolidated valuation"}
    tw = sum(weights.values())
    target = (sum(p * w for p, w in zip(prices, weights.values())) / tw
              if tw > 0 else sum(prices) / len(prices))
    spread = (max(prices) - min(prices)) / target if target else 0
    confidence = "High" if spread < 0.15 else "Medium" if spread < 0.30 else "Low"
    upside = ((target - price) / price * 100) if price and target else None
    return {
        "target_price": target,
        "valuation_range": {"low": min(prices), "high": max(prices)},
        "upside_downside_pct": upside,
        "models_used": list(weights),
        "confidence": confidence,
        "summary": (f"Consolidated target: ${target:.2f} ({upside:+.1f}% vs current)"
                    if target and upside else "Valuation analysis completed")
    }


async def compute_valuation(ticker: str) -> Dict[str, Any]:
    """Enhanced multi-model valuation: DCF, DDM, Comparables, sensitivity analysis."""
    def _run() -> Dict[str, Any]:
        try:
            info = yf.Ticker(ticker).info or {}
            price = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
            shares = _f(info.get("sharesOutstanding"))
            mkt_cap = _f(info.get("marketCap"))
            beta = _f(info.get("beta")) or 1.0
            fcf0 = _get_fcf(ticker, info)
            g = max(0.0, min(0.15, _f(info.get("revenueGrowth")) or 0.05))
            r = max(0.08, min(0.15, 0.045 + beta * 0.065))
            tg = 0.025

            valuations: Dict[str, Any] = {}
            try:
                from app.tools.dcf_valuation import perform_dcf_valuation
                dcf_result = asyncio.run(perform_dcf_valuation(ticker))
                if dcf_result:
                    valuations["dcf"] = {"applicable": True,
                                         "base_case": {"intrinsic_price": {"base": dcf_result.get("intrinsic_value")}},
                                         "methodology": "Enhanced DCF"}
                else:
                    valuations["dcf"] = _dcf_analysis(fcf0, g, r, tg, shares, mkt_cap, price)
            except Exception:
                valuations["dcf"] = _dcf_analysis(fcf0, g, r, tg, shares, mkt_cap, price)

            ddm = _ddm(info, r)
            if ddm.get("applicable"):
                valuations["ddm"] = ddm
            valuations["comparables"] = _comps(ticker, info, price)
            sotp = _sotp(info)
            if sotp.get("applicable"):
                valuations["sum_of_parts"] = sotp

            consolidated = _consolidate(valuations, price)
            return {
                "inputs": {"fcf0": fcf0, "revenue_growth": g, "discount_rate": r,
                           "terminal_growth": tg, "shares_outstanding": shares,
                           "market_cap": mkt_cap, "current_price": price,
                           "dividend_yield": _f(info.get("dividendYield")), "beta": beta},
                "models": valuations,
                "sensitivity_analysis": _sensitivity(fcf0, g, r, tg, shares),
                "consolidated_valuation": consolidated,
                "valuation_summary": consolidated.get("summary", "Multi-model valuation completed")
            }
        except Exception as e:
            return {"inputs": {}, "models": {}, "sensitivity_analysis": {},
                    "consolidated_valuation": {},
                    "valuation_summary": f"Valuation analysis failed: {e}"}

    return await asyncio.to_thread(_run)
