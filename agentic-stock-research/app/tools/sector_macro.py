from __future__ import annotations

import asyncio
from typing import Any, Dict

import yfinance as yf


async def analyze_sector_macro(ticker: str) -> Dict[str, Any]:
    """Lightweight sector/macro view using yfinance metadata."""
    def _fetch() -> Dict[str, Any]:
        try:
            info = yf.Ticker(ticker).info or {}
            sector = info.get("sector") or "Unknown"
            industry = info.get("industry") or "Unknown"
            country = info.get("country") or info.get("exchangeTimezoneName") or "Unknown"
            is_india = isinstance(country, str) and ("India" in country or ticker.upper().endswith((".NS", ".BO")))
            risks = ["rupee volatility", "domestic rates", "regulatory"] if is_india else ["rates", "fx", "growth"]
            sector_l = sector.lower()
            outlook = ("positive" if any(k in sector_l for k in ["tech", "technology"])
                       else "mixed" if any(k in sector_l for k in ["retail", "discretionary"])
                       else "stable")
            return {"sector": sector, "industry": industry, "country": country,
                    "sector_outlook": outlook, "macro_risks": risks}
        except Exception:
            return {"sector_outlook": "stable", "macro_risks": ["rates", "fx"]}

    return await asyncio.to_thread(_fetch)
