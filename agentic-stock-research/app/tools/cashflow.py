from __future__ import annotations

from typing import Any, Dict, Optional, List, Tuple

import pandas as pd
import yfinance as yf


async def analyze_cashflows(ticker: str) -> Dict[str, Any]:
    import asyncio

    def _to_float(x: Any) -> Optional[float]:
        try:
            return float(x)
        except Exception:
            return None

    def _cash() -> Dict[str, Any]:
        try:
            t = yf.Ticker(ticker)
            cf: pd.DataFrame = t.cashflow  # type: ignore[attr-defined]
            is_df: pd.DataFrame = getattr(t, "financials", None)  # income statement for revenue
        except Exception:
            return {"trend": None}
        if cf is None or getattr(cf, "empty", True):
            return {"trend": None}
        
        # Find operating cash flow with multiple possible key names
        ocf_series = None
        ocf_keys = [
            "Total Cash From Operating Activities",
            "Cash Flow From Continuing Operating Activities", 
            "Operating Cash Flow",
            "Net Cash From Operating Activities"
        ]
        for key in ocf_keys:
            if key in cf.index:
                ocf_series = cf.loc[key].dropna()
                break
        
        # Find capital expenditures with multiple possible key names
        capex_series = None
        capex_keys = [
            "Capital Expenditures",
            "Capital Expenditure", 
            "Capex",
            "Purchase Of Property Plant Equipment"
        ]
        for key in capex_keys:
            if key in cf.index:
                capex_series = cf.loc[key].dropna()
                break

        # Attempt to get revenue series for margin calculations
        revenue_series = None
        if isinstance(is_df, pd.DataFrame) and not is_df.empty:
            rev_keys = [
                "Total Revenue",
                "Revenue",
                "TotalRevenue",
            ]
            for key in rev_keys:
                if key in is_df.index:
                    revenue_series = is_df.loc[key].dropna()
                    break
        trend = None
        if isinstance(ocf_series, pd.Series) and len(ocf_series) >= 2:
            trend = "improving" if ocf_series.diff().mean() > 0 else "deteriorating"
        # Calculate additional metrics
        ocf_latest = _to_float(ocf_series.iloc[-1]) if isinstance(ocf_series, pd.Series) and len(ocf_series) else None
        capex_latest = _to_float(capex_series.iloc[-1]) if isinstance(capex_series, pd.Series) and len(capex_series) else None
        
        # Calculate free cash flow if possible
        free_cash_flow = None
        if isinstance(ocf_latest, (int, float)) and isinstance(capex_latest, (int, float)):
            # CapEx is usually negative, so we add it (which subtracts the absolute value)
            free_cash_flow = ocf_latest + capex_latest
        
        # Build historical series
        def _series_to_list(s: Optional[pd.Series]) -> List[Tuple[str, float]]:
            if not isinstance(s, pd.Series) or len(s) == 0:
                return []
            out: List[Tuple[str, float]] = []
            for col, val in s.items():
                try:
                    # Columns are often Timestamps; fallback to str
                    label = str(getattr(col, "date", col))
                except Exception:
                    label = str(col)
                fv = _to_float(val)
                if fv is not None:
                    out.append((label, fv))
            # ensure chronological order oldest -> newest for CAGR calc
            return sorted(out, key=lambda x: x[0])

        ocf_hist_pairs = _series_to_list(ocf_series)
        capex_hist_pairs = _series_to_list(capex_series)
        fcf_hist_pairs: List[Tuple[str, float]] = []
        if ocf_hist_pairs and capex_hist_pairs:
            # Align by period label
            capex_map = {p: v for p, v in capex_hist_pairs}
            for p, ocf_v in ocf_hist_pairs:
                if p in capex_map:
                    fcf_v = ocf_v + capex_map[p]
                    fcf_hist_pairs.append((p, fcf_v))

        ocf_history = [v for _, v in ocf_hist_pairs]

        # FCF margin (latest)
        fcf_margin = None
        if fcf_hist_pairs:
            fcf_last = fcf_hist_pairs[-1][1]
            rev_last = None
            if isinstance(revenue_series, pd.Series) and len(revenue_series) > 0:
                # Align by latest column name token if possible, else just take latest
                try:
                    rev_last = _to_float(revenue_series.iloc[-1])
                except Exception:
                    rev_last = None
            if isinstance(fcf_last, (int, float)) and isinstance(rev_last, (int, float)) and rev_last:
                fcf_margin = fcf_last / rev_last

        # FCF CAGR
        fcf_cagr = None
        fcf_cagr_years = None
        if len(fcf_hist_pairs) >= 2:
            first_val = fcf_hist_pairs[0][1]
            last_val = fcf_hist_pairs[-1][1]
            # years approximated by number of periods - 1 (annual)
            years = max(1, len(fcf_hist_pairs) - 1)
            fcf_cagr_years = years
            try:
                if first_val and last_val and first_val > 0 and last_val > 0:
                    fcf_cagr = (last_val / first_val) ** (1.0 / years) - 1.0
            except Exception:
                fcf_cagr = None

        # Flags
        positive_fcf_latest = isinstance(free_cash_flow, (int, float)) and free_cash_flow > 0
        improving_ocf = trend == "improving"
        capex_to_ocf_ratio = None
        capex_discipline = None
        if isinstance(ocf_latest, (int, float)) and ocf_latest != 0 and isinstance(capex_latest, (int, float)):
            capex_to_ocf_ratio = abs(capex_latest) / abs(ocf_latest)
            capex_discipline = capex_to_ocf_ratio <= 0.7  # heuristic
        
        return {
            "ocf_latest": ocf_latest,
            "ocf_trend": trend,
            "ocf_history": ocf_history,
            "capex_latest": capex_latest,
            "free_cash_flow": free_cash_flow,
            "summary": f"OCF: ${ocf_latest/1e9:.1f}B, CapEx: ${capex_latest/1e9:.1f}B, FCF: ${free_cash_flow/1e9:.1f}B" if ocf_latest and capex_latest and free_cash_flow is not None else "Limited cash flow data",
            # Extended series
            "series": {
                "ocf": ocf_hist_pairs,
                "capex": capex_hist_pairs,
                "fcf": fcf_hist_pairs,
            },
            # Ratios & growth
            "fcf_margin": fcf_margin,
            "fcf_cagr": fcf_cagr,
            "fcf_cagr_years": fcf_cagr_years,
            # Flags
            "flags": {
                "positive_fcf_latest": positive_fcf_latest,
                "improving_ocf": improving_ocf,
                "capex_discipline": capex_discipline,
                "capex_to_ocf_ratio": capex_to_ocf_ratio,
            },
        }

    return await asyncio.to_thread(_cash)
