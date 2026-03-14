from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import yfinance as yf

from app.tools.finance import fetch_info
import logging
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_OCF_KEYS = ["Total Cash From Operating Activities",
             "Cash Flow From Continuing Operating Activities",
             "Operating Cash Flow", "Net Cash From Operating Activities"]
_CAPEX_KEYS = ["Capital Expenditures", "Capital Expenditure", "Capex",
               "Purchase Of Property Plant Equipment"]

_INDUSTRY_PE = {
    "Technology": {"pe": 22.0, "pb": 4.5, "ev_ebitda": 15.0},
    "Healthcare": {"pe": 18.0, "pb": 3.2, "ev_ebitda": 12.0},
    "Financial Services": {"pe": 18.0, "pb": 2.5, "ev_ebitda": None},
    "Consumer Cyclical": {"pe": 16.0, "pb": 2.8, "ev_ebitda": 10.0},
    "Consumer Defensive": {"pe": 15.0, "pb": 2.5, "ev_ebitda": 9.0},
    "Energy": {"pe": 12.0, "pb": 1.8, "ev_ebitda": 6.0},
    "Utilities": {"pe": 14.0, "pb": 1.5, "ev_ebitda": 8.0},
    "Real Estate": {"pe": 16.0, "pb": 1.4, "ev_ebitda": 12.0},
    "Basic Materials": {"pe": 13.0, "pb": 1.9, "ev_ebitda": 7.0},
    "Communication Services": {"pe": 20.0, "pb": 3.0, "ev_ebitda": 11.0},
}
_DEFAULT_MULTIPLES = {"pe": 16.0, "pb": 2.5, "ev_ebitda": 10.0}

# Indian domestic peer groups for apples-to-apples comparison (all NSE tickers)
_INDIAN_PEER_GROUPS: Dict[str, Dict[str, Any]] = {
    # Financial Services — segmented by sub-industry
    "Private Banks":    {"tickers": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS"], "pb": 2.8, "pe": 20.0, "roe": 0.16},
    "Public Banks":     {"tickers": ["SBIN.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS"],                             "pb": 1.2, "pe": 10.0, "roe": 0.12},
    "NBFCs":            {"tickers": ["BAJFINANCE.NS", "BAJAJFINSV.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS"],              "pb": 3.5, "pe": 22.0, "roe": 0.18},
    "Insurance":        {"tickers": ["SBILIFE.NS", "HDFCLIFE.NS", "ICICIPRULI.NS"],                                 "pb": 6.0, "pe": 35.0, "roe": 0.14},
    # Other sectors
    "IT Services":      {"tickers": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],                   "pb": 8.0, "pe": 24.0, "ev_ebitda": 16.0},
    "Pharma":           {"tickers": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS"],                      "pb": 4.5, "pe": 28.0, "ev_ebitda": 18.0},
    "FMCG":             {"tickers": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"],                    "pb": 10.0,"pe": 45.0, "ev_ebitda": 30.0},
    "Oil & Gas":        {"tickers": ["RELIANCE.NS", "ONGC.NS", "IOC.NS", "BPCL.NS"],                               "pb": 1.5, "pe": 12.0, "ev_ebitda": 7.0},
    "Auto":             {"tickers": ["MARUTI.NS", "M&M.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS"],                      "pb": 3.5, "pe": 20.0, "ev_ebitda": 12.0},
    "Cement":           {"tickers": ["ULTRACEMCO.NS", "SHREECEM.NS", "AMBUJACEM.NS", "ACC.NS"],                     "pb": 3.8, "pe": 30.0, "ev_ebitda": 18.0},
}

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _f(x: Any) -> Optional[float]:
    try:
        v = float(x)
        return None if v != v else v  # NaN check
    except Exception:
        return None


def _is_indian(ticker: str) -> bool:
    return ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO")


def _risk_free_rate(ticker: str) -> float:
    """
    Return the appropriate risk-free rate.
    Indian stocks (.NS / .BO): India 10Y G-Sec ~7.0%
    All others: US 10Y Treasury ~4.5%
    Using 4.5% for Indian stocks artificially inflates valuations.
    """
    return 0.070 if _is_indian(ticker) else 0.045


def _cost_of_equity(ticker: str, beta: float) -> float:
    """CAPM: Ke = Rf + beta * ERP.  ERP = 6.5% (global), bounded [8%, 18%]."""
    rf = _risk_free_rate(ticker)
    erp = 0.065
    return max(0.08, min(0.18, rf + beta * erp))


def _detect_financial_sub_sector(info: Dict[str, Any]) -> Optional[str]:
    """Classify Financial Services into a fine-grained sub-sector."""
    sector = info.get("sector", "")
    industry = info.get("industry", "").lower()
    if sector != "Financial Services":
        return None
    if any(k in industry for k in ("bank", "banking")):
        # Distinguish private from public (rough heuristic: name contains known PSU names)
        name = info.get("shortName", "") + info.get("longName", "")
        psu_keywords = ("State Bank", "Bank of Baroda", "Punjab National", "Canara",
                        "Bank of India", "Union Bank", "UCO", "Central Bank", "Indian Bank")
        return "Public Banks" if any(k.lower() in name.lower() for k in psu_keywords) else "Private Banks"
    if any(k in industry for k in ("insurance", "life insurance", "general insurance")):
        return "Insurance"
    if any(k in industry for k in ("financial", "credit", "nbfc", "finance company", "consumer finance")):
        return "NBFCs"
    return "Private Banks"  # fallback for unclassified Financial Services


def _resolve_indian_peer_benchmarks(info: Dict[str, Any], ticker: str) -> Optional[Dict[str, Any]]:
    """Return domestic peer benchmark multiples for Indian tickers."""
    if not _is_indian(ticker):
        return None
    sector = info.get("sector", "")
    industry = info.get("industry", "").lower()

    if sector == "Financial Services":
        sub = _detect_financial_sub_sector(info)
        return _INDIAN_PEER_GROUPS.get(sub) if sub else None
    if sector == "Technology":
        return _INDIAN_PEER_GROUPS.get("IT Services")
    if sector in ("Healthcare", "Pharmaceuticals"):
        return _INDIAN_PEER_GROUPS.get("Pharma")
    if sector == "Consumer Defensive":
        return _INDIAN_PEER_GROUPS.get("FMCG")
    if sector == "Energy":
        return _INDIAN_PEER_GROUPS.get("Oil & Gas")
    if sector == "Consumer Cyclical" and "auto" in industry:
        return _INDIAN_PEER_GROUPS.get("Auto")
    if "cement" in industry:
        return _INDIAN_PEER_GROUPS.get("Cement")
    return None


def _get_fcf(ticker: str, info: Dict[str, Any]) -> Optional[float]:
    """
    FCF is NOT a valid metric for banks/financials — their operating cash flow
    includes deposit inflows/outflows (their inventory), making it meaningless.
    Return None for Financial Services so DCF is correctly skipped.
    """
    if info.get("sector") == "Financial Services":
        return None
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


def resolve_financial_inputs(info: Dict[str, Any], ticker: str,
                              price: Optional[float]) -> Dict[str, Any]:
    """
    Single source of truth for BVPS, ROE, and shares for financial-services
    valuation models (Excess Returns in valuation.py and _score_valuation in
    comprehensive_scoring.py).

    Derivation chains (each tried in priority order until a value is found):

    SHARES:
        1. info["sharesOutstanding"]          — direct field
        2. info["impliedSharesOutstanding"]   — alternate field
        3. marketCap / price                  — derived

    BVPS (book value per share):
        1. info["bookValue"]                  — direct per-share field
        2. price / info["priceToBook"]        — price ÷ P/B ratio
        3. info["totalStockholderEquity"] / shares — total equity ÷ shares

    ROE (as decimal, e.g. 0.18 for 18%):
        1. info["returnOnEquity"]             — direct field
        2. info["trailingEps"] / bvps         — EPS/BVPS = NI/sh ÷ Equity/sh = NI/Equity = ROE
                                                (universal fallback: both present for every
                                                 profitable listed company)
        3. info["netIncomeToCommon"] / (bvps * shares)
        4. info["netIncomeToCommon"] / info["totalStockholderEquity"]

    Returns a dict with keys:
        bvps         float | None
        roe          float | None   (decimal)
        shares       float | None
        bvps_source  str             e.g. "bookValue", "price/priceToBook", "equity/shares"
        roe_source   str             e.g. "returnOnEquity", "trailingEps/bookValue", etc.
    """
    result: Dict[str, Any] = {
        "bvps": None, "roe": None, "shares": None,
        "bvps_source": "unavailable", "roe_source": "unavailable",
    }

    # ── Shares ────────────────────────────────────────────────────────────────
    shares = (
        _f(info.get("sharesOutstanding"))
        or _f(info.get("impliedSharesOutstanding"))
    )
    if not shares and price and price > 0:
        mkt_cap = _f(info.get("marketCap"))
        if mkt_cap and mkt_cap > 0:
            shares = mkt_cap / price
    result["shares"] = shares

    # ── BVPS ─────────────────────────────────────────────────────────────────
    bvps = _f(info.get("bookValue"))
    bvps_source = "bookValue"

    if not bvps and price and price > 0:
        pb = _f(info.get("priceToBook"))
        if pb and pb > 0:
            bvps = price / pb
            bvps_source = "price/priceToBook"

    if not bvps and shares and shares > 0:
        equity = _f(info.get("totalStockholderEquity"))
        if equity and equity > 0:
            bvps = equity / shares
            bvps_source = "equity/shares"

    result["bvps"] = bvps
    result["bvps_source"] = bvps_source if bvps else "unavailable"

    # ── ROE ──────────────────────────────────────────────────────────────────
    roe = _f(info.get("returnOnEquity"))
    roe_source = "returnOnEquity"

    if not roe and bvps and bvps > 0:
        eps = _f(info.get("trailingEps"))
        if eps is not None and eps > 0:
            roe = eps / bvps
            roe_source = "trailingEps/bookValue"

    if not roe and bvps and shares and bvps > 0 and shares > 0:
        ni = _f(info.get("netIncomeToCommon"))
        if ni and ni > 0:
            roe = ni / (bvps * shares)
            roe_source = "netIncome/(bvps*shares)"

    if not roe:
        ni = _f(info.get("netIncomeToCommon"))
        equity = _f(info.get("totalStockholderEquity"))
        if ni and equity and equity > 0:
            roe = ni / equity
            roe_source = "netIncome/totalEquity"

    result["roe"] = roe
    result["roe_source"] = roe_source if roe else "unavailable"

    logger.info(
        "[%s] resolve_financial_inputs: BVPS=%.2f (%s) ROE=%.4f (%s) shares=%s",
        ticker,
        bvps or 0, result["bvps_source"],
        roe or 0,  result["roe_source"],
        f"{shares:.0f}" if shares else "N/A",
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Valuation models
# ─────────────────────────────────────────────────────────────────────────────

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
        "low":  {"g": max(0, g - 0.02), "r": max(0.05, r + 0.01), "tg": max(0, tg - 0.005)},
        "base": {"g": g,               "r": r,                    "tg": tg},
        "high": {"g": g + 0.02,        "r": max(0.05, r - 0.01),  "tg": tg + 0.005},
    }
    caps   = {k: _pv(**v) for k, v in scenarios.items()}
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
            "optimistic":   _dcf_band(fcf0, shares, mkt_cap, min(0.12, g + 0.03), max(0.08, r - 0.01), min(0.04, tg + 0.005)),
            "recession":    _dcf_band(fcf0, shares, mkt_cap, max(0, g - 0.05),    r + 0.02, max(0.015, tg - 0.01)),
        },
        "methodology": "5-year DCF with terminal value"
    }


def _excess_returns_valuation(info: Dict[str, Any], ticker: str, r: float, tg: float) -> Dict[str, Any]:
    """
    Residual Income / Excess Returns model for banks and financial services.
    Intrinsic Value = BVPS + PV of Excess Returns
    where Excess Return = BVPS * (ROE - Cost of Equity) perpetuity / (r - tg)

    Uses resolve_financial_inputs() for all data extraction so that BVPS and ROE
    have the same multi-fallback derivation chain as comprehensive_scoring.py —
    no more silent failures when yfinance omits returnOnEquity (e.g. Bajaj Finance).
    """
    try:
        logger.info(f"Running Excess Returns valuation for {ticker} with r={r:.4f}, tg={tg:.4f}")
        price = _f(info.get("currentPrice") or info.get("regularMarketPrice"))

        fi = resolve_financial_inputs(info, ticker, price)
        bvps = fi["bvps"]
        roe  = fi["roe"]

        if not bvps or not roe:
            return {
                "applicable": False,
                "reason": (
                    f"Missing key banking metrics — "
                    f"BVPS source: {fi['bvps_source']}, ROE source: {fi['roe_source']}"
                )
            }
        if bvps <= 0:
            return {"applicable": False, "reason": "Negative book value — model not applicable"}
        if r <= tg:
            return {"applicable": False, "reason": "Discount rate must exceed terminal growth rate"}

        excess_return_rate    = roe - r
        terminal_value_excess = (bvps * excess_return_rate) / (r - tg)
        intrinsic_value       = bvps + terminal_value_excess
        upside                = ((intrinsic_value / price) - 1) if price and price > 0 else None

        # Scenarios: vary COE ±1%
        scenarios = {}
        for label, r_adj in [("conservative", r + 0.01), ("base", r), ("optimistic", max(0.08, r - 0.01))]:
            er   = roe - r_adj
            tv   = (bvps * er) / (r_adj - tg) if r_adj > tg else 0
            iv   = bvps + tv
            up   = ((iv / price) - 1) if price and price > 0 else None
            scenarios[label] = {"cost_of_equity": r_adj, "intrinsic_value": round(iv, 2),
                                 "upside_pct": round(up * 100, 2) if up is not None else None}

        return {
            "applicable":        True,
            "method":            "Excess Returns (Residual Income)",
            "intrinsic_value":   round(intrinsic_value, 2),
            "upside_pct":        round(upside * 100, 2) if upside is not None else None,
            "scenarios":         scenarios,
            "inputs":            {
                "ROE":             round(roe, 4),
                "BVPS":            round(bvps, 2),
                "cost_of_equity":  round(r, 4),
                "terminal_growth": round(tg, 4),
                "excess_return":   round(excess_return_rate, 4),
                "bvps_source":     fi["bvps_source"],
                "roe_source":      fi["roe_source"],
            },
            "methodology": "Intrinsic Value = BVPS + (BVPS × (ROE − Ke)) / (Ke − g)"
        }
    except Exception as e:
        return {"applicable": False, "error": str(e)}


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
    """
    Comparables analysis.
    For Indian tickers: use domestic peer benchmarks (NSE peers, same regulatory environment).
    For others: use global sector averages.
    Cross-border comparisons (e.g. Indian bank vs US banks) produce incorrect conclusions
    due to different risk-free rates, regulatory capital requirements, and growth profiles.
    """
    # Resolve benchmarks
    indian_peers = _resolve_indian_peer_benchmarks(info, ticker)
    if indian_peers:
        mults       = indian_peers
        peer_label  = f"Indian domestic peers ({', '.join(indian_peers['tickers'][:3])}...)"
    else:
        mults      = _INDUSTRY_PE.get(info.get("sector", ""), _DEFAULT_MULTIPLES)
        peer_label = "Global sector averages"

    analysis: Dict[str, Any] = {}
    pe, pb, ev_eb = (_f(info.get(k)) for k in ["trailingPE", "priceToBook", "enterpriseToEbitda"])

    if pe and price and mults.get("pe"):
        analysis["pe_based"] = {
            "current_multiple":  pe,
            "peer_average":      mults["pe"],
            "implied_price":     round(price / pe * mults["pe"], 2),
            "premium_discount":  f"{((pe / mults['pe']) - 1) * 100:+.1f}%",
        }
    if pb and price and mults.get("pb"):
        analysis["pb_based"] = {
            "current_multiple":  pb,
            "peer_average":      mults["pb"],
            "implied_price":     round(price / pb * mults["pb"], 2),
            "premium_discount":  f"{((pb / mults['pb']) - 1) * 100:+.1f}%",
        }
    if ev_eb and mults.get("ev_ebitda"):
        analysis["ev_ebitda"] = {
            "current_multiple":  ev_eb,
            "peer_average":      mults["ev_ebitda"],
            "premium_discount":  f"{((ev_eb / mults['ev_ebitda']) - 1) * 100:+.1f}%",
        }

    return {
        "applicable":       bool(analysis),
        "peer_group":       peer_label,
        "multiples_analysis": analysis,
        "methodology":      "Domestic peer comparison" if indian_peers else "Industry peer comparison",
    }


def _comps_banking_india(ticker: str, info: Dict[str, Any], price: Optional[float],
                          sub_sector: str) -> Dict[str, Any]:
    """
    P/B based comparables specifically for Indian banks.
    Uses Indian domestic peers, not US money-center banks.
    """
    peers = _INDIAN_PEER_GROUPS.get(sub_sector, _INDIAN_PEER_GROUPS["Private Banks"])
    current_pb  = _f(info.get("priceToBook"))
    current_pe  = _f(info.get("trailingPE"))
    peer_pb     = peers["pb"]
    peer_pe     = peers["pe"]
    peer_roe    = peers["roe"]

    analysis: Dict[str, Any] = {}
    if current_pb and price:
        analysis["pb_based"] = {
            "current_pb":    round(current_pb, 2),
            "peer_avg_pb":   peer_pb,
            "implied_price": round((peer_pb / current_pb) * price, 2),
            "premium_discount": f"{((current_pb / peer_pb) - 1) * 100:+.1f}%",
        }
    if current_pe and price:
        analysis["pe_based"] = {
            "current_pe":    round(current_pe, 2),
            "peer_avg_pe":   peer_pe,
            "implied_price": round((peer_pe / current_pe) * price, 2),
            "premium_discount": f"{((current_pe / peer_pe) - 1) * 100:+.1f}%",
        }

    # Add RoE context — key quality signal for banks
    roe = _f(info.get("returnOnEquity"))
    if roe:
        analysis["roe_context"] = {
            "current_roe": f"{roe * 100:.1f}%",
            "peer_avg_roe": f"{peer_roe * 100:.1f}%",
            "assessment": "Above peer average" if roe > peer_roe else "Below peer average",
        }

    return {
        "applicable":         bool(analysis),
        "peer_group":         f"Indian {sub_sector} ({', '.join(peers['tickers'][:3])}...)",
        "multiples_analysis": analysis,
        "methodology":        "P/B and P/E comparison against Indian domestic banking peers",
    }


def _banking_npa_metrics(info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract credit quality / NPA proxies for banks.
    yfinance doesn't expose NPA directly; we use available proxies.
    """
    metrics: Dict[str, Any] = {}
    # Provision coverage / loan loss reserves (proxy)
    for key in ("allowanceForDoubtfulAccountsReceivableCurrent",
                "allowanceForDoubtfulAccountsReceivableNoncurrent"):
        v = _f(info.get(key))
        if v:
            metrics["provision_for_losses"] = v
            break
    roe   = _f(info.get("returnOnEquity"))
    roa   = _f(info.get("returnOnAssets"))
    de    = _f(info.get("debtToEquity"))
    nim   = _f(info.get("netInterestMargin"))   # not always available
    if roe:  metrics["return_on_equity"]  = f"{roe * 100:.1f}%"
    if roa:  metrics["return_on_assets"]  = f"{roa * 100:.2f}%"
    if de:   metrics["leverage_ratio"]    = round(de, 2)
    if nim:  metrics["net_interest_margin"] = f"{nim * 100:.2f}%"

    # Capital adequacy proxy: equity / assets
    equity = _f(info.get("totalStockholderEquity"))
    assets = _f(info.get("totalAssets"))
    if equity and assets and assets > 0:
        metrics["equity_to_assets_pct"] = f"{equity / assets * 100:.2f}%"

    metrics["note"] = ("Detailed NPA / GNPA / NNPA data is not available via yfinance. "
                       "Refer to latest quarterly results filed with BSE/NSE for NPA disclosures.")
    return metrics


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
    gr  = [g - 0.02, g, g + 0.02]
    dr  = [r - 0.01, r, r + 0.01]
    tr  = [max(0.015, tg - 0.005), tg, tg + 0.005]
    matrix = [[_dcf_band(fcf0, shares, None, gg, dd, tg).get("intrinsic_price", {}).get("base")
               if gg < dd else None for dd in dr] for gg in gr]
    term_sens = [_dcf_band(fcf0, shares, None, g, r, t).get("intrinsic_price", {}).get("base")
                 if g < r else None for t in tr]
    return {
        "applicable": True,
        "sensitivity_matrix": {
            "growth_vs_discount": {"growth_rates": gr, "discount_rates": dr, "price_matrix": matrix},
            "terminal_growth":    {"terminal_rates": tr, "prices": term_sens},
        },
        "methodology": "Sensitivity analysis across growth / discount / terminal rate axes",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Consolidation + data integrity
# ─────────────────────────────────────────────────────────────────────────────

def _validate_target(target: Optional[float], price: Optional[float],
                     analyst_target: Optional[float],
                     ticker: str = "") -> Dict[str, Any]:
    """
    Sanity-check the model-derived target against analyst consensus.
    If our target diverges >50% from consensus, flag it as unreliable rather
    than silently issuing a buy/sell recommendation on corrupted data.

    Also detects stale/adjusted analyst targets for Indian stocks: if
    targetMeanPrice is >40% below current price for a .NS/.BO ticker, it is
    almost certainly a pre-merger or currency-adjusted stale value from yfinance
    (reproducible with HDFCBANK.NS after the 2023 HDFC Ltd merger).
    """
    if not target or not price:
        return {"status": "INSUFFICIENT_DATA", "message": "Cannot validate — missing price or target"}

    flags: List[str] = []
    is_indian = ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO")

    # Flag 0 (Indian stocks only): analyst target looks stale / pre-merger / currency-wrong
    # If analyst_target is >40% below current price, it is likely stale data from yfinance.
    # Real analyst targets for Indian large-caps rarely sit 40%+ below the current price.
    if is_indian and analyst_target and analyst_target > 0 and price > 0:
        analyst_vs_price = (analyst_target - price) / price
        if analyst_vs_price < -0.40:
            flags.append(
                f"DATA QUALITY WARNING: analyst consensus target ₹{analyst_target:.0f} is "
                f"{-analyst_vs_price*100:.0f}% below current price ₹{price:.0f}. "
                f"This likely reflects stale, pre-merger, or unadjusted data from yfinance "
                f"(common after corporate actions like the HDFC Bank / HDFC Ltd merger). "
                f"Do not use this target for investment decisions without manual verification."
            )

    # Flag 1: extreme implied move (>80% up or >60% down vs current price)
    upside = (target - price) / price
    if upside > 0.80:
        flags.append(f"Target implies +{upside*100:.0f}% — unusually high; verify inputs")
    if upside < -0.60:
        flags.append(f"Target implies {upside*100:.0f}% — potential model error (negative FCF / data issue)")

    # Flag 2: divergence from analyst consensus (only if analyst target is itself credible)
    if analyst_target and analyst_target > 0:
        analyst_credible = not (is_indian and analyst_target < price * 0.60)
        if analyst_credible:
            divergence = abs(target - analyst_target) / analyst_target
            if divergence > 0.50:
                flags.append(
                    f"Model target ₹{target:.0f} diverges {divergence*100:.0f}% from analyst consensus "
                    f"₹{analyst_target:.0f} — LOW CONFIDENCE"
                )

    if flags:
        return {"status": "LOW_CONFIDENCE", "flags": flags,
                "recommendation": "Do not use this price target for investment decisions without manual review"}
    return {"status": "PASS", "flags": []}


def _consolidate(valuations: Dict[str, Any], price: Optional[float],
                 analyst_target: Optional[float] = None,
                 ticker: str = "") -> Dict[str, Any]:
    """
    Weighted consolidation with data integrity check.

    Model weights (base):
      - DCF / Excess Returns: 0.50  (primary intrinsic value model)
      - DDM:                  0.20  (income model — only when dividend is meaningful)
      - Comparables:          0.30  (market-relative — only when not an extreme outlier)

    Outlier guard for Comparables:
      High-growth / quality-premium stocks (e.g. Polycab PE 47x vs sector 16x) routinely
      trade at multiples far above industry averages.  Using a peer-average multiple to back
      into an implied price produces a number well below the current price, which then drags
      the consolidated target below fair value and below current price.  We detect this:
      if the comparables implied price is >35% below the primary model target AND <80% of
      the current price, the stock is clearly trading at a justified growth premium and
      peer-multiple reversal is not a near-term thesis.  In that case the comparables are
      excluded from the weighted average (weight → 0) and the primary model gets 0.70.

    Analyst anchor:
      If a credible analyst consensus target exists (not stale — within ±60% of current
      price for Indian tickers) and our consolidated model target diverges from it by >30%,
      we blend in the analyst target at 20% weight.  This prevents extreme DCF/model outliers
      from dominating when the analyst community has a different consensus.
    """
    primary_prices: List[float] = []
    prices: List[float] = []
    weights: Dict[str, float] = {}

    def _guard(p: Optional[float]) -> Optional[float]:
        """Reject clearly bogus prices."""
        if p is None or p <= 0:
            return None
        if price and price > 0 and p > price * 10:
            return None  # Implausibly high — likely a model error
        return p

    # ── Primary model (DCF or Excess Returns) ─────────────────────────────
    primary_iv: Optional[float] = None

    if valuations.get("dcf", {}).get("applicable"):
        p = _guard(valuations["dcf"].get("base_case", {}).get("intrinsic_price", {}).get("base"))
        if p:
            primary_iv = p
            prices.append(p)
            weights["dcf"] = 0.50

    if valuations.get("excess_returns", {}).get("applicable"):
        p = _guard(_f(valuations["excess_returns"].get("intrinsic_value")))
        if p:
            primary_iv = p
            prices.append(p)
            weights["excess_returns"] = 0.50

    # ── DDM ───────────────────────────────────────────────────────────────
    if valuations.get("ddm", {}).get("applicable"):
        p = _guard(_f(valuations["ddm"].get("ddm_value_per_share")))
        if p:
            prices.append(p)
            weights["ddm"] = 0.20

    # ── Comparables — outlier guard ───────────────────────────────────────
    # If comp implied price is far below both current price AND primary model,
    # the stock is at a justified growth premium and comparables are not a useful
    # anchor for a near-term price target.  Exclude them from the weighted average.
    comp_iv: Optional[float] = None
    if valuations.get("comparables", {}).get("applicable"):
        comp_vals = [
            valuations["comparables"]["multiples_analysis"].get(k, {}).get("implied_price")
            for k in ("pe_based", "pb_based")
        ]
        comp_vals = [_guard(_f(cv)) for cv in comp_vals if cv is not None]
        comp_vals = [cv for cv in comp_vals if cv is not None]
        if comp_vals:
            comp_iv = sum(comp_vals) / len(comp_vals)

    if comp_iv is not None:
        is_outlier = False
        if price and price > 0 and comp_iv < price * 0.80:
            # Comparables below 80% of current price — likely a premium-multiple stock
            if primary_iv and primary_iv > 0 and comp_iv < primary_iv * 0.65:
                # Also >35% below primary model — confirmed growth premium situation
                is_outlier = True

        if not is_outlier:
            prices.append(comp_iv)
            weights["comparables"] = 0.30
        else:
            # Rebalance: primary model takes the weight comparables would have had
            for k in ("dcf", "excess_returns"):
                if k in weights:
                    weights[k] = 0.70  # bump primary model to 70%
            # Still record comp_iv for transparency but don't use it in the weighted average
            valuations.setdefault("comparables_excluded", {})["reason"] = (
                f"Excluded: stock trades at growth premium "
                f"(comp implied Rs.{comp_iv:.0f} is >35% below primary model and <80% of current price). "
                f"Peer-multiple reversion is not a near-term thesis for premium-growth stocks."
            )

    if not prices:
        return {
            "target_price": None, "valuation_range": {},
            "confidence": "Low", "data_integrity": {"status": "INSUFFICIENT_DATA"},
            "summary": "Insufficient data for consolidated valuation",
        }

    tw     = sum(weights.values())
    target = (sum(p * w for p, w in zip(prices, weights.values())) / tw
              if tw > 0 else sum(prices) / len(prices))

    # ── Analyst anchor blend ───────────────────────────────────────────────
    # If we have a credible analyst target and it differs meaningfully from our
    # model target, blend it in at 20% to keep the output grounded in market reality.
    is_indian = ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO")
    analyst_credible = (
        analyst_target and analyst_target > 0 and
        not (is_indian and price and analyst_target < price * 0.60)
    )
    if analyst_credible and target > 0:
        divergence = abs(target - analyst_target) / analyst_target
        if divergence > 0.30:
            # Blend: 80% model, 20% analyst consensus
            target = target * 0.80 + analyst_target * 0.20

    spread     = (max(prices) - min(prices)) / target if target and len(prices) > 1 else 0
    confidence = "High" if spread < 0.15 else "Medium" if spread < 0.30 else "Low"
    upside     = ((target - price) / price * 100) if price and target else None

    integrity = _validate_target(target, price, analyst_target, ticker)
    if integrity.get("status") == "LOW_CONFIDENCE":
        confidence = "Low"

    currency = "Rs." if (is_indian) else "$"
    return {
        "target_price":        round(target, 2),
        "valuation_range":     {"low": round(min(prices), 2), "high": round(max(prices), 2)},
        "upside_downside_pct": round(upside, 2) if upside is not None else None,
        "models_used":         list(weights),
        "confidence":          confidence,
        "data_integrity":      integrity,
        "summary": (
            f"Consolidated target: {currency}{target:.2f} ({upside:+.1f}% vs current) — {confidence} confidence"
            if target and upside is not None else "Valuation analysis completed"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

async def compute_valuation(ticker: str, current_price: Optional[float] = None) -> Dict[str, Any]:
    """
    Multi-model valuation with sector-aware model selection.

    Non-financial companies → DCF + DDM + Comparables
    Financial Services / Banks → Excess Returns + P/B Comparables (domestic peers)
                                  + NPA credit quality metrics

    current_price: canonical price fetched upstream (e.g. from analyst_recommendations).
    If provided it is used directly, skipping the internal yfinance fetch for price.
    This eliminates the dual-fetch price split bug where two different yfinance code
    paths return different values (reproducible with HDFCBANK.NS post-merger prices).
    """
    def _run() -> Dict[str, Any]:
        try:
            info   = yf.Ticker(ticker).info or {}
            # Use caller-supplied price if available; only fall back to yfinance if not.
            # This ensures the price in all valuation calculations matches the report header.
            price_from_info = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
            price = current_price if (current_price and current_price > 0) else price_from_info
            shares = _f(info.get("sharesOutstanding"))
            mkt_cap = _f(info.get("marketCap"))
            beta   = _f(info.get("beta")) or 1.0
            sector = info.get("sector", "")
            industry = info.get("industry", "")

            # ── Correct cost of capital (Indian vs global risk-free rate) ──────
            r  = _cost_of_equity(ticker, beta)
            tg = 0.025
            # Growth: use earnings growth for financials, revenue growth for others
            raw_g = (_f(info.get("earningsGrowth")) if sector == "Financial Services"
                     else _f(info.get("revenueGrowth")))
            g = max(0.0, min(0.15, raw_g or 0.05))

            analyst_target = _f(info.get("targetMeanPrice"))
            is_financial   = (sector == "Financial Services" or "Bank" in industry
                               or "Insurance" in industry or "NBFC" in industry.upper())
            valuations: Dict[str, Any] = {}

            if is_financial:
                # ── Financial Services path ───────────────────────────────────
                #
                # 1. Excess Returns (Residual Income) — primary model
                valuations["excess_returns"] = _excess_returns_valuation(info, ticker, r, tg)

                # 2. DCF explicitly marked inapplicable with correct reason
                fcf0 = None  # deliberately not computed for financials
                valuations["dcf"] = {
                    "applicable": False,
                    "reason": (
                        "DCF is not applicable for Financial Services companies. "
                        "Operating cash flows for banks include deposit/loan flows "
                        "(their inventory), making FCF meaningless. "
                        "Using Excess Returns (Residual Income) model instead."
                    )
                }

                # 3. Domestic peer comparables (P/B + P/E vs Indian peers only)
                sub_sector = _detect_financial_sub_sector(info) or "Private Banks"
                valuations["comparables"] = _comps_banking_india(ticker, info, price, sub_sector)

                # 4. DDM if meaningful dividend
                ddm = _ddm(info, r)
                if ddm.get("applicable"):
                    valuations["ddm"] = ddm

                # 5. Credit quality / NPA proxy metrics
                credit_metrics = _banking_npa_metrics(info)

                consolidated = _consolidate(valuations, price, analyst_target, ticker)
                return {
                    "primary_model": "excess_returns",   # consumed by frontend — never show DCF card for this
                    "inputs": {
                        "current_price":   price,
                        "book_value_ps":   _f(info.get("bookValue")),
                        "return_on_equity": _f(info.get("returnOnEquity")),
                        "cost_of_equity":  round(r, 4),
                        "terminal_growth": tg,
                        "beta":            beta,
                        "risk_free_rate":  _risk_free_rate(ticker),
                        "analyst_target":  analyst_target,
                        "sub_sector":      sub_sector,
                    },
                    "models":                valuations,
                    "credit_quality":        credit_metrics,
                    "sensitivity_analysis":  {"applicable": False,
                                              "reason": "Sensitivity analysis uses FCF — not applicable for banks"},
                    "consolidated_valuation": consolidated,
                    "valuation_summary":      consolidated.get("summary", "Multi-model valuation completed"),
                }

            else:
                # ── Non-financial path (original logic, improved) ─────────────
                fcf0 = _get_fcf(ticker, info)

                # Try enhanced DCF tool first, fall back to internal model
                try:
                    from app.tools.dcf_valuation import perform_dcf_valuation
                    dcf_result = asyncio.run(perform_dcf_valuation(ticker))
                    if dcf_result:
                        valuations["dcf"] = {
                            "applicable": True,
                            "base_case":  {"intrinsic_price": {"base": dcf_result.get("intrinsic_value")}},
                            "methodology": "Enhanced DCF",
                        }
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

                consolidated = _consolidate(valuations, price, analyst_target, ticker)
                return {
                    "primary_model": "dcf",              # consumed by frontend
                    "inputs": {
                        "fcf0":            fcf0,
                        "revenue_growth":  g,
                        "discount_rate":   r,
                        "risk_free_rate":  _risk_free_rate(ticker),
                        "terminal_growth": tg,
                        "shares_outstanding": shares,
                        "market_cap":      mkt_cap,
                        "current_price":   price,
                        "dividend_yield":  _f(info.get("dividendYield")),
                        "beta":            beta,
                        "analyst_target":  analyst_target,
                    },
                    "models":                valuations,
                    "sensitivity_analysis":  _sensitivity(fcf0, g, r, tg, shares),
                    "consolidated_valuation": consolidated,
                    "valuation_summary":      consolidated.get("summary", "Multi-model valuation completed"),
                }

        except Exception as e:
            return {
                "inputs": {}, "models": {}, "sensitivity_analysis": {},
                "consolidated_valuation": {},
                "valuation_summary": f"Valuation analysis failed: {e}",
            }

    return await asyncio.to_thread(_run)