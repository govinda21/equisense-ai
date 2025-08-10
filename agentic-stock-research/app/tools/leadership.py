from __future__ import annotations

from typing import Any, Dict

import yfinance as yf


async def analyze_leadership(ticker: str) -> Dict[str, Any]:
    """
    Approximate leadership/governance signals using available yfinance fields.
    If data is missing, return a conservative default.
    """
    import asyncio

    def _fetch() -> Dict[str, Any]:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            # Heuristics: use available fields to infer governance/insider sentiment
            audit_risk = info.get("auditRisk")  # lower is better
            board_risk = info.get("boardRisk")
            compensation_risk = info.get("compensationRisk")
            share_holder_rights_risk = info.get("shareHolderRightsRisk")
            overall_risk_values = [
                v for v in [audit_risk, board_risk, compensation_risk, share_holder_rights_risk] if isinstance(v, (int, float))
            ]

            governance_score = None
            if overall_risk_values:
                # Normalize inverse: lower risk → higher score
                avg_risk = sum(overall_risk_values) / len(overall_risk_values)
                governance_score = max(0.0, min(1.0, 1.0 - (avg_risk / 10.0)))

            insider_hold_pct = info.get("heldPercentInsiders")  # fraction 0..1
            insider_trend = "neutral"
            if isinstance(insider_hold_pct, (int, float)):
                if insider_hold_pct > 0.15:
                    insider_trend = "accumulating"
                elif insider_hold_pct < 0.02:
                    insider_trend = "light"

            board_independence = "unknown"
            if isinstance(board_risk, (int, float)):
                board_independence = "strong" if board_risk <= 5 else "moderate" if board_risk <= 7 else "weak"

            return {
                "governance_score": governance_score if governance_score is not None else 0.6,
                "insider_trend": insider_trend,
                "board_independence": board_independence,
                "details": {
                    "auditRisk": audit_risk,
                    "boardRisk": board_risk,
                    "compensationRisk": compensation_risk,
                    "shareHolderRightsRisk": share_holder_rights_risk,
                    "heldPercentInsiders": insider_hold_pct,
                },
            }
        except Exception:
            return {"governance_score": 0.6, "insider_trend": "neutral", "board_independence": "moderate"}

    return await asyncio.to_thread(_fetch)
