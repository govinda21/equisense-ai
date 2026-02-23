"""
Horizon Filtering Engine
Adjusts analysis weights, confidence scores, and recommendations
based on the user's investment time horizon (short / medium / long-term).
"""
from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AnalysisHorizon(str, Enum):
    SHORT_TERM  = "short_term"   # 0–6 months
    MEDIUM_TERM = "medium_term"  # 6–18 months
    LONG_TERM   = "long_term"    # 18+ months


# Weight and adjustment config per horizon
_CONFIG: Dict[AnalysisHorizon, Dict] = {
    AnalysisHorizon.SHORT_TERM: {
        "days_range": (0, 180),
        "weights": {"technicals": 0.40, "news_sentiment": 0.30, "fundamentals": 0.20, "growth_prospects": 0.10},
        "volatility_adjustment": 1.2, "confidence_discount": 0.9,
    },
    AnalysisHorizon.MEDIUM_TERM: {
        "days_range": (180, 540),
        "weights": {"technicals": 0.25, "news_sentiment": 0.20, "fundamentals": 0.35, "growth_prospects": 0.20},
        "volatility_adjustment": 1.0, "confidence_discount": 1.0,
    },
    AnalysisHorizon.LONG_TERM: {
        "days_range": (540, 1095),
        "weights": {"technicals": 0.10, "news_sentiment": 0.10, "fundamentals": 0.40, "growth_prospects": 0.40},
        "volatility_adjustment": 0.8, "confidence_discount": 1.1,
    },
}

# Always-on static weights for sections not in the horizon config
_STATIC_WEIGHTS = {"valuation": 0.15, "peer_analysis": 0.10,
                   "sector_macro": 0.10, "leadership": 0.05,
                   "cashflow": 0.05, "analyst_recommendations": 0.05}

_HORIZON_FACTORS = {
    AnalysisHorizon.SHORT_TERM:  ["Technical momentum", "Earnings expectations", "Market sentiment", "Volatility"],
    AnalysisHorizon.MEDIUM_TERM: ["Catalyst timing", "Valuation", "Sector trends", "Risk management"],
    AnalysisHorizon.LONG_TERM:   ["Business fundamentals", "Competitive moats", "Growth prospects", "Management quality"],
}

_HORIZON_CONSIDERATIONS = {
    AnalysisHorizon.SHORT_TERM:  ["Higher volatility expected", "Technical indicators more relevant",
                                   "Earnings and guidance critical", "Market sentiment impact significant"],
    AnalysisHorizon.MEDIUM_TERM: ["Balanced approach required", "Both technical and fundamental factors",
                                   "Catalyst timing important", "Risk management essential"],
    AnalysisHorizon.LONG_TERM:   ["Fundamental business quality paramount", "Competitive positioning crucial",
                                   "Management execution important", "Industry trends and disruption risks"],
}


class HorizonFilteringEngine:
    """Filter and weight analysis data based on the investor's time horizon."""

    # ------------------------------------------------------------------
    # Horizon classification
    # ------------------------------------------------------------------

    def determine_horizons(self, short_days: int, long_days: int
                           ) -> Tuple[AnalysisHorizon, AnalysisHorizon]:
        short = self._classify(short_days)
        long  = self._classify(long_days)
        logger.info(f"Horizons → short={short.value}, long={long.value}")
        return short, long

    def _classify(self, days: int) -> AnalysisHorizon:
        if days <= 180:
            return AnalysisHorizon.SHORT_TERM
        elif days <= 540:
            return AnalysisHorizon.MEDIUM_TERM
        return AnalysisHorizon.LONG_TERM

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def apply_horizon_filtering(
        self,
        analysis_data: Dict[str, Any],
        horizon: AnalysisHorizon,
        confidences: Dict[str, float],
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        cfg = _CONFIG[horizon]
        filtered = dict(analysis_data)  # shallow copy

        # Embed horizon weights
        filtered["horizon_weights"] = cfg["weights"]

        # RSI thresholds – tighter for short-term
        rsi_thresh = {"overbought": 70, "oversold": 30} if horizon == AnalysisHorizon.SHORT_TERM \
                     else {"overbought": 75, "oversold": 25}
        tech = filtered.get("technicals", {}).get("details", {})
        if tech:
            tech["rsi_adjusted_thresholds"] = rsi_thresh

        # Sentiment volatility note
        vol = cfg["volatility_adjustment"]
        for sec in ("news_sentiment", "youtube_sentiment"):
            sent = filtered.get(sec, {}).get("details", {})
            if sent:
                sent["volatility_factor"] = vol
                sent["horizon_note"] = (
                    "Short-term: higher volatility" if horizon == AnalysisHorizon.SHORT_TERM
                    else "Long-term: trend focus"
                )

        # Growth focus
        growth = filtered.get("growth_prospects", {}).get("details", {})
        if growth:
            growth["focus"]     = "near_term_catalysts" if horizon == AnalysisHorizon.SHORT_TERM else "sustainable_growth"
            growth["timeframe"] = "0-6 months"           if horizon == AnalysisHorizon.SHORT_TERM else "18+ months"

        # Valuation method priority
        val = filtered.get("valuation", {}).get("details", {})
        if val:
            val["focus"]           = "relative_valuation" if horizon == AnalysisHorizon.SHORT_TERM else "intrinsic_valuation"
            val["priority_methods"] = ["P/E","P/B","EV/EBITDA"] if horizon == AnalysisHorizon.SHORT_TERM \
                                      else ["DCF","DDM","Sum_of_Parts"]

        # Confidence adjustment
        disc = cfg["confidence_discount"]
        adjusted_conf = {k: min(1.0, v * disc) for k, v in confidences.items()}

        filtered["horizon_metadata"] = {
            "horizon": horizon.value, "config": cfg, "applied_at": datetime.now().isoformat()
        }
        logger.info(f"Applied {horizon.value} filtering")
        return filtered, adjusted_conf

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def calculate_horizon_weighted_score(
        self,
        section_scores: Dict[str, float],
        confidences: Dict[str, float],
        horizon: AnalysisHorizon,
    ) -> float:
        weights = {**_CONFIG[horizon]["weights"], **_STATIC_WEIGHTS}
        num, denom = 0.0, 0.0
        for sec, score in section_scores.items():
            w = weights.get(sec, 0.05)
            conf = confidences.get(sec, 0.5)
            eff = w * conf
            num   += score * eff
            denom += eff
        return num / denom if denom else 0.5

    # ------------------------------------------------------------------
    # Summaries & recommendations
    # ------------------------------------------------------------------

    def generate_horizon_summary(
        self,
        horizon: AnalysisHorizon,
        analysis_data: Dict[str, Any],
        composite_score: float,
    ) -> Dict[str, Any]:
        cfg = _CONFIG[horizon]
        focus_areas = []
        w = cfg["weights"]
        if w["technicals"]     > 0.30: focus_areas.append("Technical momentum and chart patterns")
        if w["news_sentiment"]  > 0.20: focus_areas.append("Market sentiment and news flow")
        if w["fundamentals"]    > 0.35: focus_areas.append("Fundamental business metrics")
        if w["growth_prospects"] > 0.30: focus_areas.append("Growth prospects and catalysts")

        return {
            "horizon": horizon.value,
            "days_range": cfg["days_range"],
            "focus_areas": focus_areas,
            "key_considerations": _HORIZON_CONSIDERATIONS[horizon],
            "confidence_level": "high" if composite_score >= 0.7 else "moderate" if composite_score >= 0.5 else "low",
        }

    def get_horizon_recommendations(
        self,
        short_score: float, long_score: float,
        short_horizon: AnalysisHorizon, long_horizon: AnalysisHorizon,
    ) -> Dict[str, Any]:
        diff = long_score - short_score
        comparative = (
            "Long-term outlook more favorable" if diff >  0.10 else
            "Short-term outlook more favorable" if diff < -0.10 else
            "Consistent outlook across horizons"
        )
        return {
            "short_term": {
                "score": short_score, "horizon": short_horizon.value,
                "recommendation": self._recommend(short_score),
                "confidence":     self._confidence(short_score),
                "key_factors":    _HORIZON_FACTORS[short_horizon],
            },
            "long_term": {
                "score": long_score, "horizon": long_horizon.value,
                "recommendation": self._recommend(long_score),
                "confidence":     self._confidence(long_score),
                "key_factors":    _HORIZON_FACTORS[long_horizon],
            },
            "comparative_analysis": comparative,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _recommend(self, score: float) -> str:
        if score >= 0.8: return "Strong Buy"
        if score >= 0.6: return "Buy"
        if score >= 0.4: return "Hold"
        if score >= 0.2: return "Sell"
        return "Strong Sell"

    def _confidence(self, score: float) -> str:
        return "High" if score >= 0.7 else "Moderate" if score >= 0.5 else "Low"


# Singleton
horizon_engine = HorizonFilteringEngine()
