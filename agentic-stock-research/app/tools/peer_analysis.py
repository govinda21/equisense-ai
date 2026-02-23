"""
Peer Comparison Analysis
Identifies comparable companies, fetches valuation metrics,
and scores the target stock relative to its peers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from app.tools.finance import fetch_info

logger = logging.getLogger(__name__)


# ---------- data models ----------

@dataclass
class ValuationMetrics:
    ticker: str
    market_cap:           Optional[float] = None
    enterprise_value:     Optional[float] = None
    trailing_pe:          Optional[float] = None
    forward_pe:           Optional[float] = None
    price_to_book:        Optional[float] = None
    price_to_sales:       Optional[float] = None
    ev_to_ebitda:         Optional[float] = None
    ev_to_revenue:        Optional[float] = None
    ev_to_ebit:           Optional[float] = None
    peg_ratio:            Optional[float] = None
    price_to_cash_flow:   Optional[float] = None
    dividend_yield:       Optional[float] = None
    beta:                 Optional[float] = None


@dataclass
class PeerComparison:
    metric:            str
    target_value:      Optional[float]
    peer_average:      Optional[float]
    peer_median:       Optional[float]
    peer_min:          Optional[float]
    peer_max:          Optional[float]
    percentile_rank:   Optional[int]
    z_score:           Optional[float]
    relative_position: str   # "Cheap" | "Fair" | "Expensive" | "Low/Moderate/High Risk"


# ---------- constants ----------

# Metrics where lower value = cheaper (better)
_CHEAP_METRICS = {"trailing_pe", "forward_pe", "price_to_book", "price_to_sales",
                  "ev_to_ebitda", "ev_to_revenue", "ev_to_ebit", "peg_ratio", "price_to_cash_flow"}

_METRIC_LABELS = {
    "trailing_pe": "Trailing P/E", "forward_pe": "Forward P/E",
    "price_to_book": "Price-to-Book", "price_to_sales": "Price-to-Sales",
    "ev_to_ebitda": "EV/EBITDA", "ev_to_revenue": "EV/Revenue",
    "ev_to_ebit": "EV/EBIT", "peg_ratio": "PEG Ratio",
    "price_to_cash_flow": "Price-to-Cash Flow",
    "dividend_yield": "Dividend Yield", "beta": "Beta",
}

_METRIC_WEIGHTS = {
    "trailing_pe": 0.15, "forward_pe": 0.15, "price_to_book": 0.10,
    "price_to_sales": 0.10, "ev_to_ebitda": 0.15, "ev_to_revenue": 0.10,
    "peg_ratio": 0.10, "price_to_cash_flow": 0.10, "dividend_yield": 0.05,
}

# Predefined peer groups
_PEER_MAP: Dict[str, List[str]] = {
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "META", "ORCL"],
    "GOOGL": ["AAPL", "MSFT", "AMZN", "META", "NFLX"],
    "AMZN": ["AAPL", "MSFT", "GOOGL", "META", "WMT"],
    "META": ["AAPL", "MSFT", "GOOGL", "SNAP"],
    "NVDA": ["AMD", "INTC", "QCOM", "AAPL", "MSFT"],
    "TSLA": ["GM", "F", "NIO", "RIVN", "LCID"],
    "JPM": ["BAC", "WFC", "C", "GS", "MS"],
    "BAC": ["JPM", "WFC", "C", "USB", "PNC"],
    "JNJ": ["PFE", "MRK", "ABT", "TMO", "UNH"],
    "PFE": ["JNJ", "MRK", "ABT", "BMY", "LLY"],
    "KO":  ["PEP", "MNST", "KDP", "CCEP"],
    "PEP": ["KO", "MNST", "KDP", "CCEP"],
    "WMT": ["TGT", "COST", "AMZN", "HD", "LOW"],
    # Indian stocks
    "RELIANCE.NS":  ["TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"],
    "TCS.NS":       ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "HDFCBANK.NS":  ["ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
    "BAJFINANCE.NS":["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS"],
    "JIOFIN.NS":    ["HDFCBANK.NS", "ICICIBANK.NS", "BAJFINANCE.NS", "AXISBANK.NS"],
}

_SECTOR_FALLBACK: Dict[str, List[str]] = {
    "Technology":          ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
    "Financial Services":  ["JPM", "BAC", "WFC", "C", "GS"],
    "Healthcare":          ["JNJ", "PFE", "MRK", "ABT", "UNH"],
    "Consumer":            ["KO", "PEP", "WMT", "TGT", "COST"],
}


def _safe(x: Any) -> Optional[float]:
    try:
        f = float(x)
        return None if f != f else f
    except Exception:
        return None


# ---------- metric extraction ----------

def _extract(info: Dict[str, Any]) -> ValuationMetrics:
    return ValuationMetrics(
        ticker=info.get("symbol", ""),
        market_cap=_safe(info.get("marketCap")),
        enterprise_value=_safe(info.get("enterpriseValue")),
        trailing_pe=_safe(info.get("trailingPE")),
        forward_pe=_safe(info.get("forwardPE")),
        price_to_book=_safe(info.get("priceToBook")),
        price_to_sales=_safe(info.get("priceToSalesTrailing12Months")),
        ev_to_ebitda=_safe(info.get("enterpriseToEbitda")),
        ev_to_revenue=_safe(info.get("enterpriseToRevenue")),
        ev_to_ebit=_safe(info.get("enterpriseToEbit")),
        peg_ratio=_safe(info.get("pegRatio")),
        price_to_cash_flow=_safe(info.get("priceToCashflowTrailing12Months")),
        dividend_yield=_safe(info.get("dividendYield")),
        beta=_safe(info.get("beta")),
    )


# ---------- comparison logic ----------

def _percentile(val: float, peers: List[float]) -> int:
    if not peers:
        return 50
    all_vals = sorted(peers + [val])
    return int(all_vals.index(val) / (len(all_vals) - 1) * 100) if len(all_vals) > 1 else 50


def _relative_position(metric: str, pct: int) -> str:
    if metric in _CHEAP_METRICS:
        return "Cheap" if pct <= 25 else "Expensive" if pct >= 75 else "Fair"
    if metric == "dividend_yield":
        return "Cheap" if pct >= 75 else "Expensive" if pct <= 25 else "Fair"
    return "Low Risk" if pct <= 25 else "High Risk" if pct >= 75 else "Moderate Risk"


def _compare(target: ValuationMetrics, peers: Dict[str, ValuationMetrics]
             ) -> Dict[str, Any]:
    results: Dict[str, PeerComparison] = {}
    strengths, weaknesses, val_summary = [], [], []

    for metric in _METRIC_LABELS:
        tval = getattr(target, metric)
        pvals = [getattr(p, metric) for p in peers.values()
                 if getattr(p, metric) is not None]
        if tval is None or not pvals:
            continue

        avg    = float(np.mean(pvals))
        median = float(np.median(pvals))
        std    = float(np.std(pvals)) if len(pvals) > 1 else 0
        pct    = _percentile(tval, pvals)
        z      = (tval - avg) / std if std else 0
        pos    = _relative_position(metric, pct)

        results[metric] = PeerComparison(
            metric=metric, target_value=tval,
            peer_average=avg, peer_median=median,
            peer_min=min(pvals), peer_max=max(pvals),
            percentile_rank=pct, z_score=z, relative_position=pos,
        )

        label = _METRIC_LABELS[metric]
        if pct <= 25:
            if metric in _CHEAP_METRICS:
                strengths.append(f"Attractive {label} ({pct}th percentile)")
                val_summary.append(f"{label}: Undervalued vs peers")
            elif metric == "dividend_yield":
                strengths.append(f"High {label}")
                val_summary.append(f"{label}: Above-average yield")
            else:
                strengths.append(f"Low volatility (beta {pct}th pct)")
        elif pct >= 75:
            if metric in _CHEAP_METRICS:
                weaknesses.append(f"Premium {label} ({pct}th percentile)")
                val_summary.append(f"{label}: Overvalued vs peers")
            elif metric == "dividend_yield":
                weaknesses.append(f"Low {label}")
                val_summary.append(f"{label}: Below-average yield")
            else:
                weaknesses.append(f"High volatility (beta {pct}th pct)")
        else:
            val_summary.append(f"{label}: In-line with peers")

    # Overall valuation score (0–100, higher = more attractive)
    score = sum(
        ((100 - r.percentile_rank) if metric in _CHEAP_METRICS
         else r.percentile_rank if metric == "dividend_yield"
         else 50) * _METRIC_WEIGHTS.get(metric, 0.05)
        for metric, r in results.items()
        if r.percentile_rank is not None
    )

    position = ("Significantly Undervalued" if score >= 70 else
                "Moderately Undervalued"    if score >= 60 else
                "Fairly Valued"             if score >= 40 else
                "Moderately Overvalued"     if score >= 30 else "Significantly Overvalued")

    peer_names = list(peers.keys())
    attract    = "attractive" if score >= 60 else "fair" if score >= 40 else "expensive"
    summary = (
        f"{target.ticker} shows {attract} valuation vs {len(peer_names)} peers "
        f"({', '.join(peer_names[:3])}{'...' if len(peer_names) > 3 else ''}). "
        + (f"Strengths: {', '.join(strengths[:3])}. " if strengths else "")
        + (f"Concerns: {', '.join(weaknesses[:3])}." if weaknesses else "")
    )

    return {
        "valuation_metrics":  {k: v.__dict__ for k, v in results.items()},
        "valuation_score":    score,
        "relative_position":  position,
        "strengths":          strengths,
        "weaknesses":         weaknesses,
        "valuation_summary":  val_summary,
        "summary":            summary,
        "peer_count":         len(peers),
    }


# ---------- public API ----------

async def analyze_peers(ticker: str) -> Dict[str, Any]:
    """
    Identify comparable peers, compare valuation metrics,
    and return a relative positioning assessment.
    """
    try:
        company_info = await fetch_info(ticker)
        sector   = company_info.get("sector", "")
        industry = company_info.get("industry", "")
        mktcap   = _safe(company_info.get("marketCap"))

        # Identify peers
        peers = _PEER_MAP.get(ticker.upper(), [])
        if not peers:
            for kw, defaults in _SECTOR_FALLBACK.items():
                if kw in sector:
                    peers = defaults[:3]
                    break
            if not peers:
                peers = ["SPY"]  # market-benchmark fallback

        peers = [p for p in peers if p.upper() != ticker.upper()][:5]
        if not peers:
            return {"sector": sector, "industry": industry, "peers_identified": [],
                    "relative_position": "Unable to identify comparable peers",
                    "summary": "Insufficient peer data"}

        # Fetch target + peer metrics
        target_metrics = _extract(company_info)
        peer_metrics: Dict[str, ValuationMetrics] = {}
        for p in peers:
            try:
                peer_metrics[p] = _extract(await fetch_info(p))
            except Exception:
                continue

        if not peer_metrics:
            return {"sector": sector, "industry": industry, "peers_identified": peers,
                    "relative_position": "Unable to fetch peer data",
                    "summary": "Peer data retrieval failed"}

        comparison = _compare(target_metrics, peer_metrics)
        return {
            "sector": sector, "industry": industry,
            "peers_identified": list(peer_metrics.keys()),
            "target_metrics":   target_metrics.__dict__,
            "peer_metrics":     {k: v.__dict__ for k, v in peer_metrics.items()},
            **comparison,
        }

    except Exception as e:
        logger.error(f"Peer analysis failed for {ticker}: {e}")
        return {"sector": "Unknown", "industry": "Unknown", "peers_identified": [],
                "relative_position": f"Analysis failed: {e}",
                "summary": "Peer analysis could not be completed"}
