"""
Leadership & governance signal extraction using yfinance.
Produces governance score, insider trend, and board independence rating.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

import yfinance as yf


async def analyze_leadership(ticker: str) -> Dict[str, Any]:
    """
    Approximate leadership/governance signals from yfinance info fields.
    Returns conservative defaults when data is unavailable.

    Fields used:
      auditRisk, boardRisk, compensationRisk, shareHolderRightsRisk  (1-10, lower = better)
      heldPercentInsiders  (fraction 0-1)
    """
    def _fetch() -> Dict[str, Any]:
        try:
            info = yf.Ticker(ticker).info or {}

            risk_vals = [
                info.get(k) for k in
                ("auditRisk", "boardRisk", "compensationRisk", "shareHolderRightsRisk")
                if isinstance(info.get(k), (int, float))
            ]
            governance_score = (
                round(max(0.0, 1.0 - sum(risk_vals) / (len(risk_vals) * 10)), 3)
                if risk_vals else 0.6
            )

            insider_pct = info.get("heldPercentInsiders")
            if isinstance(insider_pct, (int, float)):
                insider_trend = "accumulating" if insider_pct > 0.15 else "light" if insider_pct < 0.02 else "neutral"
            else:
                insider_trend = "neutral"

            board_risk = info.get("boardRisk")
            board_independence = (
                "strong" if isinstance(board_risk, (int, float)) and board_risk <= 5
                else "moderate" if isinstance(board_risk, (int, float)) and board_risk <= 7
                else "weak" if isinstance(board_risk, (int, float))
                else "unknown"
            )

            return {
                "governance_score": governance_score,
                "insider_trend": insider_trend,
                "board_independence": board_independence,
                "details": {
                    "auditRisk": info.get("auditRisk"),
                    "boardRisk": board_risk,
                    "compensationRisk": info.get("compensationRisk"),
                    "shareHolderRightsRisk": info.get("shareHolderRightsRisk"),
                    "heldPercentInsiders": insider_pct,
                },
            }
        except Exception:
            return {"governance_score": 0.6, "insider_trend": "neutral", "board_independence": "moderate"}

    return await asyncio.to_thread(_fetch)
