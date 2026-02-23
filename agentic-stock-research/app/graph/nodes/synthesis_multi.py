from __future__ import annotations

import asyncio
import json
import logging
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.nlp import _ollama
from app.graph.nodes.synthesis_common import (
    convert_numpy_types, score_to_action, score_to_letter_grade, score_to_stars,
    format_currency, format_percentage, safe_get,
)

logger = logging.getLogger(__name__)

# ── Sector/regime adaptive weights ──────────────────────────────────────────

_SECTOR_WEIGHTS = {
    "Technology":         {"technicals": 0.25, "fundamentals": 0.20, "growth": 0.25, "sentiment": 0.15, "valuation": 0.15},
    "Financial Services": {"technicals": 0.20, "fundamentals": 0.30, "growth": 0.15, "sentiment": 0.15, "valuation": 0.20},
    "Healthcare":         {"technicals": 0.15, "fundamentals": 0.25, "growth": 0.30, "sentiment": 0.10, "valuation": 0.20},
    "Energy":             {"technicals": 0.30, "fundamentals": 0.20, "growth": 0.10, "sentiment": 0.20, "valuation": 0.20},
    "Consumer":           {"technicals": 0.20, "fundamentals": 0.25, "growth": 0.20, "sentiment": 0.20, "valuation": 0.15},
    "default":            {"technicals": 0.25, "fundamentals": 0.25, "growth": 0.20, "sentiment": 0.15, "valuation": 0.15},
}
_REGIME_ADJUSTMENTS = {
    "bull":    {"growth": 1.2, "sentiment": 1.1, "valuation": 0.9},
    "bear":    {"fundamentals": 1.3, "valuation": 1.2, "growth": 0.8},
    "sideways": {"technicals": 1.2, "fundamentals": 1.1, "growth": 0.95},
}


def _adaptive_weights(sector: str, regime: str = "sideways") -> Dict[str, float]:
    weights = (_SECTOR_WEIGHTS.get(sector) or _SECTOR_WEIGHTS["default"]).copy()
    for k, adj in _REGIME_ADJUSTMENTS.get(regime, {}).items():
        if k in weights:
            weights[k] *= adj
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def _identify_regime(market_context: Dict) -> str:
    vix = market_context.get("vix", 20)
    trend = market_context.get("trend", "neutral")
    if vix < 20 and trend == "up": return "bull"
    if vix > 30 or trend == "down": return "bear"
    return "sideways"


# ── Score components ─────────────────────────────────────────────────────────

def _pe_score(pe):
    if not pe or pe <= 0: return None
    if 10 <= pe <= 20: return 0.8
    if 20 < pe <= 30: return 0.6
    if pe < 10: return 0.5
    if pe > 50: return 0.3
    return 0.4


def _roe_score(roe):
    if roe is None: return None
    if roe >= 0.20: return 0.9
    if roe >= 0.15: return 0.7
    if roe >= 0.10: return 0.5
    if roe >= 0: return 0.4
    return 0.2


def _growth_rate_score(g):
    if g is None: return None
    if g >= 0.25: return 0.9
    if g >= 0.15: return 0.7
    if g >= 0.05: return 0.5
    if g >= 0: return 0.4
    return 0.2


def _de_score(de):
    if de is None: return None
    if de < 0.5: return 0.8
    if de < 1.0: return 0.6
    if de < 2.0: return 0.4
    return 0.2


def _upside_score(upside):
    if upside is None: return 0.5
    if upside > 30: return 0.9
    if upside > 15: return 0.7
    if upside > 0:  return 0.55
    if upside > -15: return 0.4
    return 0.2


class ExplainableScore:
    def __init__(self):
        self.components: Dict[str, float] = {}
        self.weights: Dict[str, float] = {}
        self.raw_scores: Dict[str, float] = {}
        self.confidence_factors: Dict[str, float] = {}

    def add(self, name: str, raw: float, weight: float, conf: float = 1.0):
        self.raw_scores[name] = raw
        self.weights[name] = weight
        self.confidence_factors[name] = conf
        self.components[name] = raw * weight * conf

    def total(self) -> float:
        return sum(self.components.values())

    def explanation(self) -> Dict[str, Any]:
        t = self.total()
        return {
            "total_score": t, "components": self.components, "raw_scores": self.raw_scores,
            "weights": self.weights, "confidence_factors": self.confidence_factors,
            "contributions": {n: (s / t * 100 if t else 0) for n, s in self.components.items()},
        }


def _calculate_enhanced_score(ticker: str, analysis: Dict, confidences: Dict,
                               sector: str = "default", regime: str = "sideways") -> Tuple[float, Dict]:
    exp = ExplainableScore()
    w = _adaptive_weights(sector, regime)

    tech = analysis.get("technicals", {})
    ts = tech.get("signals", {}).get("score", 0.5)
    if ts is not None:
        exp.add("technicals", ts, w.get("technicals", 0.25), confidences.get("technicals", 0.5))

    fund = analysis.get("fundamentals", {})
    factors = [s for s in [_pe_score(fund.get("pe")), _roe_score(fund.get("roe")),
                           _growth_rate_score(fund.get("revenueGrowth")),
                           _de_score(fund.get("debtToEquity"))] if s is not None]
    fund_score = statistics.mean(factors) if factors else 0.5
    exp.add("fundamentals", fund_score, w.get("fundamentals", 0.25), confidences.get("fundamentals", 0.5))

    growth_outlook = analysis.get("growth_prospects", {}).get("growth_outlook", {}).get("overall_outlook", "")
    gs = 0.8 if "strong" in growth_outlook.lower() else 0.6 if "moderate" in growth_outlook.lower() else 0.4 if "slow" in growth_outlook.lower() else 0.3
    exp.add("growth_prospects", gs, w.get("growth", 0.20), confidences.get("growth_prospects", 0.5))

    news_s = analysis.get("news_sentiment", {}).get("score", 0.5)
    yt_s = analysis.get("youtube", {}).get("score", 0.5)
    sent = (news_s * 0.7 + yt_s * 0.3) if news_s and yt_s else (news_s or yt_s or 0.5)
    sent_conf = confidences.get("news_sentiment", 0.5) * 0.7 + confidences.get("youtube", 0.5) * 0.3
    exp.add("sentiment", sent, w.get("sentiment", 0.15), sent_conf)

    upside = (analysis.get("valuation") or {}).get("consolidated_valuation", {}).get("upside_downside_pct")
    exp.add("valuation", _upside_score(upside), w.get("valuation", 0.15), confidences.get("valuation", 0.5))

    total = exp.total()
    peer = analysis.get("peer_analysis", {})
    if peer.get("relative_position"):
        pos = peer["relative_position"].lower()
        total += 0.05 if ("above-average" in pos or "outperform" in pos) else -0.05 if "below-average" in pos else 0

    analyst = analysis.get("analyst_recommendations", {})
    implied = analyst.get("consensus_analysis", {}).get("implied_return")
    if implied:
        total = min(1.0, total * 1.1) if implied > 20 else max(0.0, total * 0.9) if implied < -10 else total

    return max(0.0, min(1.0, total)), exp.explanation()


def _score_to_action(score: float) -> str:
    if score >= 0.75: return "Strong Buy"
    if score >= 0.65: return "Buy"
    if score >= 0.55: return "Hold"
    if score >= 0.45: return "Weak Hold"
    if score >= 0.35: return "Sell"
    return "Strong Sell"


def calculate_expected_return(analysis: Dict, score: float) -> float:
    base = (score - 0.5) * 40
    upside = (analysis.get("valuation") or {}).get("consolidated_valuation", {}).get("upside_downside_pct")
    if upside is not None:
        base = base * 0.6 + upside * 0.4
    implied = (analysis.get("analyst_recommendations") or {}).get("consensus_analysis", {}).get("implied_return")
    if implied is not None:
        base = base * 0.7 + implied * 0.3
    tpe = (analysis.get("fundamentals") or {}).get("trailingPE")
    fpe = (analysis.get("fundamentals") or {}).get("forwardPE")
    if tpe and fpe and tpe > 0 and fpe > 0:
        pe_ret = ((tpe - fpe) / tpe) * 100 * (0.4 if tpe > fpe else 0.2)
        base = base * 0.8 + pe_ret * 0.2
    return round(base, 1)


def identify_key_factors(analysis: Dict, explanation: Dict, score: float = 0.5) -> Tuple[List[str], List[str]]:
    positives, negatives = [], []
    is_buy = score >= 0.6
    is_sell = score < 0.4
    _LABELS = {"technicals": ("Strong technical momentum", "Weak technical signals"),
                "fundamentals": ("Solid fundamentals", "Concerning fundamentals"),
                "growth_prospects": ("Attractive growth outlook", "Limited growth potential"),
                "sentiment": ("Positive market sentiment", None),
                "valuation": ("Compelling valuation", None)}
    for name, contrib in explanation.get("contributions", {}).items():
        pos_label, neg_label = _LABELS.get(name, (None, None))
        if contrib > 15 and pos_label and (is_buy or not is_sell):
            positives.append(pos_label)
        elif contrib < 10 and neg_label:
            negatives.append(neg_label)
    fund = analysis.get("fundamentals", {})
    if fund.get("pe") and fund["pe"] > 30: negatives.append("High P/E ratio")
    if fund.get("roe") and fund["roe"] > 0.20 and (is_buy or not is_sell):
        positives.append(f"Strong ROE of {fund['roe']:.1f}%")
    if fund.get("debtToEquity") and fund["debtToEquity"] > 2: negatives.append("High leverage")
    peer = analysis.get("peer_analysis", {})
    pos_val = peer.get("relative_position", "").lower()
    if "above-average" in pos_val and (is_buy or not is_sell): positives.append("Outperforming peers")
    elif "below-average" in pos_val: negatives.append("Underperforming peers")
    if is_sell:
        if fund.get("pe") and fund["pe"] > 25: negatives.append("Elevated valuation")
        if len(positives) > len(negatives): negatives.extend(["Market headwinds", "Risk factors present"])
        positives = positives[:1] or ["Limited defensive qualities"]
    elif is_buy:
        if len(negatives) > len(positives): positives.extend(["Strong fundamentals", "Growth potential"])
        negatives = negatives[:2] or ["Market volatility risk"]
    positives = positives or (["Some defensive qualities"] if is_sell else ["Stable market position"])
    negatives = negatives or (["Market volatility risk"] if is_buy else ["Uncertain outlook"])
    return positives[:3], negatives[:3]


def format_section(data: Any, confidence: float) -> Dict[str, Any]:
    if not data:
        return {"summary": "No data available", "confidence": 0.0, "details": {}}
    summary = data.get("summary", "Analysis completed") if isinstance(data, dict) else str(data)[:200]
    return {"summary": summary, "confidence": confidence, "details": data if isinstance(data, dict) else {"raw": data}}


async def get_llm_insights(ticker: str, analysis: Dict, base_score: float, settings: AppSettings) -> Optional[Dict]:
    if settings.llm_provider != "ollama":
        return None
    prompt = (f"Analyze {ticker} investment (score {base_score:.2f}, "
              f"PE={analysis.get('fundamentals',{}).get('pe')}, "
              f"ROE={analysis.get('fundamentals',{}).get('roe')}). "
              "Provide insights (max 50 words) and adjustment (-0.1 to +0.1).\n"
              "Format: INSIGHTS: [text] | ADJUSTMENT: [±0.XX]")
    try:
        resp = await asyncio.to_thread(_ollama, prompt)
        if resp and "INSIGHTS:" in resp:
            parts = resp.split("|")
            insights = parts[0].replace("INSIGHTS:", "").strip()
            adj = 0.0
            if len(parts) >= 2 and "ADJUSTMENT:" in parts[1]:
                try: adj = max(-0.1, min(0.1, float(parts[1].replace("ADJUSTMENT:", "").strip())))
                except: pass
            return {"insights": insights, "adjustment": adj}
    except Exception as e:
        logger.warning(f"LLM insights failed for {ticker}: {e}")
    return None


async def process_ticker_analysis(ticker: str, analysis: Dict, confidences: Dict,
                                   market_context: Dict, settings: AppSettings) -> Dict:
    sector = (analysis.get("info") or {}).get("sector", "default")
    regime = _identify_regime(market_context)
    score, explanation = _calculate_enhanced_score(ticker, analysis, confidences, sector, regime)
    await get_llm_insights(ticker, analysis, score, settings)  # fire & forget insight (used internally)
    action = _score_to_action(score)
    confidence = statistics.mean(confidences.values()) if confidences else 0.5
    expected_return = calculate_expected_return(analysis, score)
    positives, negatives = identify_key_factors(analysis, explanation, score)
    sections = ["news_sentiment", "youtube", "technicals", "fundamentals", "peer_analysis",
                "analyst_recommendations", "cashflow", "leadership", "sector_macro",
                "growth_prospects", "valuation"]
    result: Dict[str, Any] = {"ticker": ticker}
    result["youtube_sentiment"] = format_section(analysis.get("youtube"), confidences.get("youtube", 0.5))
    for s in sections:
        key = "youtube_sentiment" if s == "youtube" else s
        result[key] = format_section(analysis.get(s), confidences.get(s, 0.5))
    result["decision"] = {
        "action": action, "rating": round(score * 5, 2), "expected_return_pct": expected_return,
        "top_reasons_for": positives, "top_reasons_against": negatives,
        "confidence": confidence, "score_explanation": explanation,
    }
    result["metadata"] = {"sector": sector, "regime": regime,
                          "analysis_timestamp": datetime.now(timezone.utc).isoformat()}
    return result


def create_comparative_analysis(reports: List[Dict]) -> Dict:
    if not reports: return {}
    data = [{
        "ticker": r["ticker"], "action": r["decision"]["action"],
        "rating": r["decision"]["rating"], "expected_return": r["decision"]["expected_return_pct"],
        "confidence": r["decision"]["confidence"], "sector": r["metadata"]["sector"],
        "pe": r["fundamentals"]["details"].get("pe"),
        "growth": (r.get("growth_prospects") or {}).get("growth_outlook", {}).get("overall_outlook"),
        "valuation_upside": (r["valuation"]["details"] if "valuation" in r else {}).get(
            "consolidated_valuation", {}).get("upside_downside_pct"),
    } for r in reports]
    best = max(data, key=lambda x: x["rating"])
    best_value = min((d for d in data if d["pe"]), key=lambda x: x["pe"], default=None)
    high_conf = max(data, key=lambda x: x["confidence"])
    buys = [d for d in data if "Buy" in d["action"]]
    return {
        "summary": f"Analyzed {len(reports)} stocks. Top pick: {best['ticker']} (Rating: {best['rating']:.1f}/5)",
        "rankings": data,
        "recommendations": {
            "best_overall": best["ticker"], "best_value": best_value["ticker"] if best_value else None,
            "highest_confidence": high_conf["ticker"],
        },
        "portfolio_suggestion": {
            "suggested_allocation": {b["ticker"]: f"{100/len(buys):.1f}%" for b in buys} if buys
            else {},
            "risk_level": "Moderate",
            "diversification": f"Across {len({d['sector'] for d in buys})} sectors" if buys else "N/A",
        } if buys else {"message": "No buy recommendations in current analysis"},
    }


async def enhanced_synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    tickers = state.get("tickers", [])
    if not tickers:
        state["final_output"] = {"tickers": [], "reports": [],
                                  "generated_at": datetime.now(timezone.utc).isoformat(), "error": "No tickers"}
        return state

    all_analysis = state.get("analysis", {})
    all_confidences = state.get("confidences", {})
    market_context = state.get("market_context", {"vix": 20, "trend": "neutral", "sp500_pe": 22, "yield_curve": "normal"})

    tasks = []
    for ticker in tickers:
        if len(tickers) == 1 and ticker not in all_analysis and any(k in all_analysis for k in ["technicals", "fundamentals"]):
            ta_, tc_ = all_analysis, all_confidences
        else:
            ta_, tc_ = all_analysis.get(ticker, {}), all_confidences.get(ticker, {})
        tasks.append(process_ticker_analysis(ticker, ta_, tc_, market_context, settings))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid = [r for r in results if not isinstance(r, Exception)]

    # Sort by rating descending
    valid.sort(key=lambda x: x["decision"]["rating"], reverse=True)

    output = {
        "tickers": tickers, "reports": valid,
        "comparative_analysis": create_comparative_analysis(valid) if len(valid) > 1 else None,
        "market_context": market_context,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "scoring": "Adaptive sector/regime-based weighting",
            "explainability": "Component-level contribution tracking",
            "confidence": "Node-level confidence aggregation",
        },
    }

    # Truncate if too large
    try:
        if len(json.dumps(output)) > 10_000_000:
            for report in valid:
                for v in report.values():
                    if isinstance(v, dict) and "details" in v:
                        v["details"] = {"truncated": True}
    except Exception:
        pass

    state["final_output"] = output
    state.setdefault("confidences", {})["synthesis"] = 0.95
    return state


class AdaptiveScoring:
    """
    Adaptive scoring system for sector-specific and market regime adjustments.
    """

    @staticmethod
    def get_adaptive_weights(sector: str, regime: str) -> Dict[str, float]:
        """
        Get adaptive weights based on the sector and market regime.

        :param sector: Sector name (e.g., "Technology", "Financial Services")
        :param regime: Market regime (e.g., "bull", "bear")
        :return: Dictionary of weights for scoring factors.
        """
        base_weights = {
            "technicals": 0.3,
            "fundamentals": 0.4,
            "valuation": 0.3
        }

        if sector == "Technology":
            base_weights["growth"] = 0.4
            base_weights["valuation"] = 0.2
        elif sector == "Financial Services":
            base_weights["fundamentals"] = 0.5
            base_weights["valuation"] = 0.3

        if regime == "bull":
            base_weights["growth"] = base_weights.get("growth", 0) + 0.1
        elif regime == "bear":
            base_weights["valuation"] = base_weights.get("valuation", 0) + 0.1

        # Normalize weights to sum to 1
        total = sum(base_weights.values())
        return {k: v / total for k, v in base_weights.items()}
