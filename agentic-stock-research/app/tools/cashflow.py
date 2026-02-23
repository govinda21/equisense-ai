from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import asyncio

import pandas as pd
import yfinance as yf


def _to_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _find_series(df: pd.DataFrame, keys: List[str]) -> Optional[pd.Series]:
    for key in keys:
        if key in df.index:
            return df.loc[key].dropna()
    return None


def _series_to_pairs(s: Optional[pd.Series]) -> List[Tuple[str, float]]:
    if not isinstance(s, pd.Series) or s.empty:
        return []
    pairs = []
    for col, val in s.items():
        label = str(getattr(col, "date", col))
        fv = _to_float(val)
        if fv is not None:
            pairs.append((label, fv))
    return sorted(pairs, key=lambda x: x[0])


def _cash() -> Dict[str, Any]:
    # NOTE: ticker is captured from outer scope via closure in analyze_cashflows
    raise NotImplementedError("Use analyze_cashflows(ticker)")


async def analyze_cashflows(ticker: str) -> Dict[str, Any]:
    def _run() -> Dict[str, Any]:
        try:
            t = yf.Ticker(ticker)
            cf: pd.DataFrame = t.cashflow
            is_df: pd.DataFrame = getattr(t, "financials", None)
        except Exception:
            return {"trend": None}

        if cf is None or getattr(cf, "empty", True):
            return {"trend": None}

        ocf_series = _find_series(cf, [
            "Total Cash From Operating Activities",
            "Cash Flow From Continuing Operating Activities",
            "Operating Cash Flow",
            "Net Cash From Operating Activities",
        ])
        capex_series = _find_series(cf, [
            "Capital Expenditures", "Capital Expenditure",
            "Capex", "Purchase Of Property Plant Equipment",
        ])
        revenue_series = None
        if isinstance(is_df, pd.DataFrame) and not is_df.empty:
            revenue_series = _find_series(is_df, ["Total Revenue", "Revenue", "TotalRevenue"])

        ocf_latest = _to_float(ocf_series.iloc[-1]) if isinstance(ocf_series, pd.Series) and len(ocf_series) else None
        capex_latest = _to_float(capex_series.iloc[-1]) if isinstance(capex_series, pd.Series) and len(capex_series) else None
        trend = None
        if isinstance(ocf_series, pd.Series) and len(ocf_series) >= 2:
            trend = "improving" if ocf_series.diff().mean() > 0 else "deteriorating"

        free_cash_flow = (
            ocf_latest + capex_latest
            if isinstance(ocf_latest, (int, float)) and isinstance(capex_latest, (int, float))
            else None
        )

        ocf_pairs = _series_to_pairs(ocf_series)
        capex_pairs = _series_to_pairs(capex_series)
        capex_map = {p: v for p, v in capex_pairs}
        fcf_pairs = [(p, v + capex_map[p]) for p, v in ocf_pairs if p in capex_map]

        # FCF margin
        fcf_margin = None
        if fcf_pairs and isinstance(revenue_series, pd.Series) and len(revenue_series) > 0:
            fcf_last = fcf_pairs[-1][1]
            rev_last = _to_float(revenue_series.iloc[-1])
            if isinstance(fcf_last, (int, float)) and isinstance(rev_last, (int, float)) and rev_last:
                fcf_margin = fcf_last / rev_last

        # FCF CAGR
        fcf_cagr, fcf_cagr_years = None, None
        if len(fcf_pairs) >= 2:
            first_val, last_val = fcf_pairs[0][1], fcf_pairs[-1][1]
            years = max(1, len(fcf_pairs) - 1)
            fcf_cagr_years = years
            try:
                if first_val > 0 and last_val > 0:
                    fcf_cagr = (last_val / first_val) ** (1.0 / years) - 1.0
            except Exception:
                pass

        # Flags
        capex_to_ocf_ratio = None
        capex_discipline = None
        if isinstance(ocf_latest, (int, float)) and ocf_latest != 0 and isinstance(capex_latest, (int, float)):
            capex_to_ocf_ratio = abs(capex_latest) / abs(ocf_latest)
            capex_discipline = capex_to_ocf_ratio <= 0.7

        summary = (
            f"OCF: ${ocf_latest/1e9:.1f}B, CapEx: ${capex_latest/1e9:.1f}B, FCF: ${free_cash_flow/1e9:.1f}B"
            if ocf_latest and capex_latest and free_cash_flow is not None
            else "Limited cash flow data"
        )

        return {
            "ocf_latest": ocf_latest,
            "ocf_trend": trend,
            "ocf_history": [v for _, v in ocf_pairs],
            "capex_latest": capex_latest,
            "free_cash_flow": free_cash_flow,
            "summary": summary,
            "series": {"ocf": ocf_pairs, "capex": capex_pairs, "fcf": fcf_pairs},
            "fcf_margin": fcf_margin,
            "fcf_cagr": fcf_cagr,
            "fcf_cagr_years": fcf_cagr_years,
            "flags": {
                "positive_fcf_latest": isinstance(free_cash_flow, (int, float)) and free_cash_flow > 0,
                "improving_ocf": trend == "improving",
                "capex_discipline": capex_discipline,
                "capex_to_ocf_ratio": capex_to_ocf_ratio,
            },
        }

    return await asyncio.to_thread(_run)
