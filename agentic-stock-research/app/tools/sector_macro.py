from __future__ import annotations

from typing import Any, Dict

import yfinance as yf


async def analyze_sector_macro(ticker: str) -> Dict[str, Any]:
    """
    Provide a lightweight sector/macro view using available metadata:
    - sector, industry from yf.Ticker.info
    - country inferred from exchange or symbol suffix
    """
    import asyncio

    def _fetch() -> Dict[str, Any]:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            sector = info.get("sector") or "Unknown"
            industry = info.get("industry") or "Unknown"
            country = info.get("country") or info.get("exchangeTimezoneName") or "Unknown"

            # Simple heuristics for risks
            risks: list[str] = []
            if isinstance(country, str) and ("India" in country or ticker.upper().endswith((".NS", ".BO"))):
                risks.extend(["rupee volatility", "domestic rates", "regulatory"])
            else:
                risks.extend(["rates", "fx", "growth"])

            outlook = "stable"
            if sector and any(k in sector.lower() for k in ["tech", "technology"]):
                outlook = "positive"
            elif sector and any(k in sector.lower() for k in ["retail", "discretionary"]):
                outlook = "mixed"

            return {
                "sector": sector,
                "industry": industry,
                "country": country,
                "sector_outlook": outlook,
                "macro_risks": risks,
            }
        except Exception:
            return {"sector_outlook": "stable", "macro_risks": ["rates", "fx"]}

    return await asyncio.to_thread(_fetch)
