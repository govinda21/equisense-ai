from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import statistics

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.nlp import _ollama_chat
from app.graph.nodes.synthesis_common import (
    convert_numpy_types,
    score_to_action,
    score_to_letter_grade,
    score_to_stars,
    format_currency,
    format_percentage,
    safe_get,
)

logger = logging.getLogger(__name__)


class AdaptiveScoring:
    """Sector and regime-adaptive scoring system"""
    
    # Sector-specific weight profiles
    SECTOR_WEIGHTS = {
        "Technology": {
            "technicals": 0.25,
            "fundamentals": 0.20,
            "growth": 0.25,
            "sentiment": 0.15,
            "valuation": 0.15
        },
        "Financial Services": {
            "technicals": 0.20,
            "fundamentals": 0.30,
            "growth": 0.15,
            "sentiment": 0.15,
            "valuation": 0.20
        },
        "Healthcare": {
            "technicals": 0.15,
            "fundamentals": 0.25,
            "growth": 0.30,
            "sentiment": 0.10,
            "valuation": 0.20
        },
        "Energy": {
            "technicals": 0.30,
            "fundamentals": 0.20,
            "growth": 0.10,
            "sentiment": 0.20,
            "valuation": 0.20
        },
        "Consumer": {
            "technicals": 0.20,
            "fundamentals": 0.25,
            "growth": 0.20,
            "sentiment": 0.20,
            "valuation": 0.15
        },
        "default": {
            "technicals": 0.25,
            "fundamentals": 0.25,
            "growth": 0.20,
            "sentiment": 0.15,
            "valuation": 0.15
        }
    }
    
    # Market regime adjustments
    REGIME_ADJUSTMENTS = {
        "bull": {"growth": 1.2, "sentiment": 1.1, "valuation": 0.9},
        "bear": {"fundamentals": 1.3, "valuation": 1.2, "growth": 0.8},
        "sideways": {"technicals": 1.2, "fundamentals": 1.1, "growth": 0.95}
    }
    
    @classmethod
    def get_adaptive_weights(cls, sector: str, regime: str = "sideways") -> Dict[str, float]:
        """Get sector and regime-adjusted weights"""
        base_weights = cls.SECTOR_WEIGHTS.get(sector, cls.SECTOR_WEIGHTS["default"]).copy()
        adjustments = cls.REGIME_ADJUSTMENTS.get(regime, {})
        
        # Apply regime adjustments
        for key, adjustment in adjustments.items():
            if key in base_weights:
                base_weights[key] *= adjustment
        
        # Normalize weights to sum to 1
        total = sum(base_weights.values())
        return {k: v/total for k, v in base_weights.items()}


class ExplainableScore:
    """Track score contributions for explainability"""
    
    def __init__(self):
        self.components = {}
        self.weights = {}
        self.raw_scores = {}
        self.confidence_factors = {}
        
    def add_component(self, name: str, raw_score: float, weight: float, confidence: float = 1.0):
        """Add a scoring component with tracking"""
        self.raw_scores[name] = raw_score
        self.weights[name] = weight
        self.confidence_factors[name] = confidence
        weighted_score = raw_score * weight * confidence
        self.components[name] = weighted_score
        
    def get_total_score(self) -> float:
        """Get total weighted score"""
        return sum(self.components.values())
    
    def get_explanation(self) -> Dict[str, Any]:
        """Get detailed explanation of score"""
        total = self.get_total_score()
        return {
            "total_score": total,
            "components": self.components,
            "raw_scores": self.raw_scores,
            "weights": self.weights,
            "confidence_factors": self.confidence_factors,
            "contributions": {
                name: (score / total * 100) if total > 0 else 0
                for name, score in self.components.items()
            }
        }


def _calculate_enhanced_score(
    ticker: str,
    analysis: Dict[str, Any],
    confidences: Dict[str, float],
    sector: str = "default",
    regime: str = "sideways"
) -> Tuple[float, Dict[str, Any]]:
    """Calculate score with adaptive weights and full explainability"""
    
    explainer = ExplainableScore()
    weights = AdaptiveScoring.get_adaptive_weights(sector, regime)
    
    # Technical Analysis Component
    tech = analysis.get("technicals", {})
    tech_signals = tech.get("signals", {})
    tech_score = tech_signals.get("score", 0.5)
    if tech_score is not None:
        explainer.add_component(
            "technicals",
            tech_score,
            weights.get("technicals", 0.25),
            confidences.get("technicals", 0.5)
        )
    
    # Fundamentals Component (enhanced with multiple metrics)
    fund = analysis.get("fundamentals", {})
    fund_score = 0.5
    fund_factors = []
    
    # P/E scoring
    pe = fund.get("pe")
    if pe and pe > 0:
        pe_score = 0.0
        if 10 <= pe <= 20:
            pe_score = 0.8
        elif 20 < pe <= 30:
            pe_score = 0.6
        elif pe < 10:
            pe_score = 0.5  # Too low might be a value trap
        elif pe > 50:
            pe_score = 0.3
        else:
            pe_score = 0.4
        fund_factors.append(pe_score)
    
    # ROE scoring
    roe = fund.get("roe")
    if roe is not None:
        roe_score = 0.0
        if roe >= 0.20:  # 20%+
            roe_score = 0.9
        elif roe >= 0.15:  # 15-20%
            roe_score = 0.7
        elif roe >= 0.10:  # 10-15%
            roe_score = 0.5
        elif roe >= 0:
            roe_score = 0.4
        else:
            roe_score = 0.2
        fund_factors.append(roe_score)
    
    # Revenue growth scoring
    rev_growth = fund.get("revenueGrowth")
    if rev_growth is not None:
        growth_score = 0.0
        if rev_growth >= 0.25:  # 25%+
            growth_score = 0.9
        elif rev_growth >= 0.15:  # 15-25%
            growth_score = 0.7
        elif rev_growth >= 0.05:  # 5-15%
            growth_score = 0.5
        elif rev_growth >= 0:
            growth_score = 0.4
        else:
            growth_score = 0.2
        fund_factors.append(growth_score)
    
    # Debt/Equity scoring
    debt_equity = fund.get("debtToEquity")
    if debt_equity is not None:
        de_score = 0.0
        if debt_equity < 0.5:
            de_score = 0.8
        elif debt_equity < 1.0:
            de_score = 0.6
        elif debt_equity < 2.0:
            de_score = 0.4
        else:
            de_score = 0.2
        fund_factors.append(de_score)
    
    if fund_factors:
        fund_score = statistics.mean(fund_factors)
    
    explainer.add_component(
        "fundamentals",
        fund_score,
        weights.get("fundamentals", 0.25),
        confidences.get("fundamentals", 0.5)
    )
    
    # Growth Prospects Component
    growth = analysis.get("growth_prospects", {})
    growth_outlook = growth.get("growth_outlook", {})
    growth_score = 0.5
    
    if growth_outlook:
        outlook = growth_outlook.get("overall_outlook", "").lower()
        if "strong" in outlook:
            growth_score = 0.8
        elif "moderate" in outlook:
            growth_score = 0.6
        elif "slow" in outlook:
            growth_score = 0.4
        else:
            growth_score = 0.3
    
    explainer.add_component(
        "growth_prospects",
        growth_score,
        weights.get("growth", 0.20),
        confidences.get("growth_prospects", 0.5)
    )
    
    # Sentiment Component (News + Social)
    news = analysis.get("news_sentiment", {})
    youtube = analysis.get("youtube", {})
    
    news_score = news.get("score", 0.5)
    yt_score = youtube.get("score", 0.5)
    sentiment_score = (news_score * 0.7 + yt_score * 0.3) if news_score and yt_score else news_score or yt_score or 0.5
    
    explainer.add_component(
        "sentiment",
        sentiment_score,
        weights.get("sentiment", 0.15),
        (confidences.get("news_sentiment", 0.5) * 0.7 + confidences.get("youtube", 0.5) * 0.3)
    )
    
    # Valuation Component
    valuation = analysis.get("valuation", {})
    val_score = 0.5
    
    if valuation:
        consolidated = valuation.get("consolidated_valuation", {})
        upside = consolidated.get("upside_downside_pct")
        if upside is not None:
            if upside > 30:
                val_score = 0.9
            elif upside > 15:
                val_score = 0.7
            elif upside > 0:
                val_score = 0.55
            elif upside > -15:
                val_score = 0.4
            else:
                val_score = 0.2
    
    explainer.add_component(
        "valuation",
        val_score,
        weights.get("valuation", 0.15),
        confidences.get("valuation", 0.5)
    )
    
    # Peer Analysis Bonus
    peer = analysis.get("peer_analysis", {})
    if peer.get("relative_position"):
        position = peer["relative_position"].lower()
        peer_bonus = 0.0
        if "above-average" in position or "outperform" in position:
            peer_bonus = 0.05
        elif "below-average" in position:
            peer_bonus = -0.05
        
        total_score = explainer.get_total_score() + peer_bonus
    else:
        total_score = explainer.get_total_score()
    
    # Analyst Recommendations Adjustment
    analyst = analysis.get("analyst_recommendations", {})
    if analyst.get("consensus_analysis", {}).get("implied_return"):
        implied_return = analyst["consensus_analysis"]["implied_return"]
        if implied_return > 20:
            total_score = min(1.0, total_score * 1.1)
        elif implied_return < -10:
            total_score = max(0.0, total_score * 0.9)
    
    return max(0.0, min(1.0, total_score)), explainer.get_explanation()


def _score_to_action(score: float) -> str:
    """Convert score to investment action"""
    if score >= 0.75:
        return "Strong Buy"
    elif score >= 0.65:
        return "Buy"
    elif score >= 0.55:
        return "Hold"
    elif score >= 0.45:
        return "Weak Hold"
    elif score >= 0.35:
        return "Sell"
    else:
        return "Strong Sell"


def _identify_regime(market_context: Dict[str, Any]) -> str:
    """Identify market regime from context"""
    # This would be enhanced with real market indicators
    # For now, use simple heuristics
    vix = market_context.get("vix", 20)
    trend = market_context.get("trend", "neutral")
    
    if vix < 20 and trend == "up":
        return "bull"
    elif vix > 30 or trend == "down":
        return "bear"
    else:
        return "sideways"


async def process_ticker_analysis(
    ticker: str,
    ticker_analysis: Dict[str, Any],
    ticker_confidences: Dict[str, float],
    market_context: Dict[str, Any],
    settings: AppSettings
) -> Dict[str, Any]:
    """Process analysis for a single ticker"""
    
    # Extract sector and regime
    fund = ticker_analysis.get("fundamentals", {})
    info = ticker_analysis.get("info", {})
    sector = info.get("sector", "default")
    regime = _identify_regime(market_context)
    
    # Calculate enhanced score with explainability
    composite_score, score_explanation = _calculate_enhanced_score(
        ticker, ticker_analysis, ticker_confidences, sector, regime
    )
    
    # Get LLM insights if available
    llm_insights = await get_llm_insights(ticker, ticker_analysis, composite_score, settings)
    
    # Determine action and confidence
    action = _score_to_action(composite_score)
    overall_confidence = statistics.mean(ticker_confidences.values()) if ticker_confidences else 0.5
    
    # Calculate expected return based on multiple factors
    expected_return = calculate_expected_return(ticker_analysis, composite_score)
    
    # Identify key factors
    positives, negatives = identify_key_factors(ticker_analysis, score_explanation, composite_score)
    
    return {
        "ticker": ticker,
        "news_sentiment": format_section(ticker_analysis.get("news_sentiment"), ticker_confidences.get("news_sentiment", 0.5)),
        "youtube_sentiment": format_section(ticker_analysis.get("youtube"), ticker_confidences.get("youtube", 0.5)),
        "technicals": format_section(ticker_analysis.get("technicals"), ticker_confidences.get("technicals", 0.5)),
        "fundamentals": format_section(ticker_analysis.get("fundamentals"), ticker_confidences.get("fundamentals", 0.5)),
        "peer_analysis": format_section(ticker_analysis.get("peer_analysis"), ticker_confidences.get("peer_analysis", 0.5)),
        "analyst_recommendations": format_section(ticker_analysis.get("analyst_recommendations"), ticker_confidences.get("analyst_recommendations", 0.5)),
        "cashflow": format_section(ticker_analysis.get("cashflow"), ticker_confidences.get("cashflow", 0.5)),
        "leadership": format_section(ticker_analysis.get("leadership"), ticker_confidences.get("leadership", 0.5)),
        "sector_macro": format_section(ticker_analysis.get("sector_macro"), ticker_confidences.get("sector_macro", 0.5)),
        "growth_prospects": format_section(ticker_analysis.get("growth_prospects"), ticker_confidences.get("growth_prospects", 0.5)),
        "valuation": format_section(ticker_analysis.get("valuation"), ticker_confidences.get("valuation", 0.5)),
        "decision": {
            "action": action,
            "rating": round(composite_score * 5, 2),
            "expected_return_pct": expected_return,
            "top_reasons_for": positives,
            "top_reasons_against": negatives,
            "confidence": overall_confidence,
            "score_explanation": score_explanation
        },
        "metadata": {
            "sector": sector,
            "regime": regime,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }
    }


def format_section(data: Any, confidence: float) -> Dict[str, Any]:
    """Format a section with summary and confidence"""
    if not data:
        return {"summary": "No data available", "confidence": 0.0, "details": {}}
    
    summary = ""
    if isinstance(data, dict):
        summary = data.get("summary", "Analysis completed")
        details = data
    else:
        summary = str(data)[:200]
        details = {"raw": data}
    
    return {
        "summary": summary,
        "confidence": confidence,
        "details": details
    }


async def get_llm_insights(
    ticker: str,
    analysis: Dict[str, Any],
    base_score: float,
    settings: AppSettings
) -> Optional[Dict[str, Any]]:
    """Get LLM insights with structured output"""
    
    if settings.llm_provider != "ollama":
        return None
    
    prompt = f"""Analyze {ticker} investment opportunity:
    
    Base Score: {base_score:.2f}
    Fundamentals: PE={analysis.get('fundamentals', {}).get('pe')}, ROE={analysis.get('fundamentals', {}).get('roe')}
    Growth: {analysis.get('growth_prospects', {}).get('growth_outlook', {}).get('overall_outlook')}
    Valuation: {analysis.get('valuation', {}).get('consolidated_valuation', {}).get('upside_downside_pct')}% upside
    
    Provide brief insights (max 50 words) and any adjustment to the score (-0.1 to +0.1).
    Format: INSIGHTS: [text] | ADJUSTMENT: [±0.XX]"""
    
    try:
        response = await asyncio.to_thread(_ollama_chat, prompt)
        if response:
            # Parse structured response
            insights = ""
            adjustment = 0.0
            
            if "INSIGHTS:" in response:
                parts = response.split("|")
                if len(parts) >= 1:
                    insights = parts[0].replace("INSIGHTS:", "").strip()
                if len(parts) >= 2 and "ADJUSTMENT:" in parts[1]:
                    try:
                        adjustment = float(parts[1].replace("ADJUSTMENT:", "").strip())
                        adjustment = max(-0.1, min(0.1, adjustment))
                    except:
                        pass
            
            return {"insights": insights, "adjustment": adjustment}
    except Exception as e:
        logger.warning(f"LLM insights failed for {ticker}: {e}")
    
    return None


def calculate_expected_return(analysis: Dict[str, Any], score: float) -> float:
    """Calculate expected return based on multiple factors"""
    
    # Base return from score
    base_return = (score - 0.5) * 40  # -20% to +20% base range
    
    # Adjust based on valuation
    valuation = analysis.get("valuation", {})
    upside = valuation.get("consolidated_valuation", {}).get("upside_downside_pct")
    if upside is not None:
        # Blend valuation upside with score-based return
        base_return = base_return * 0.6 + upside * 0.4
    
    # Adjust based on analyst targets
    analyst = analysis.get("analyst_recommendations", {})
    implied_return = analyst.get("consensus_analysis", {}).get("implied_return")
    if implied_return is not None:
        # Further blend with analyst expectations
        base_return = base_return * 0.7 + implied_return * 0.3
    
    return round(base_return, 1)


def identify_key_factors(
    analysis: Dict[str, Any],
    score_explanation: Dict[str, Any],
    composite_score: float = 0.5
) -> Tuple[List[str], List[str]]:
    """Identify key positive and negative factors based on score and analysis"""
    
    positives = []
    negatives = []
    
    # Determine if this is a buy/hold/sell decision
    is_buy_signal = composite_score >= 0.6
    is_sell_signal = composite_score < 0.4
    
    # Analyze score components with bias toward final decision
    contributions = score_explanation.get("contributions", {})
    for component, contribution in contributions.items():
        if contribution > 15:  # Significant positive contribution
            if is_buy_signal or not is_sell_signal:  # Only add positive if not a clear sell
                if component == "technicals":
                    positives.append("Strong technical momentum")
                elif component == "fundamentals":
                    positives.append("Solid fundamentals")
                elif component == "growth_prospects":
                    positives.append("Attractive growth outlook")
                elif component == "sentiment":
                    positives.append("Positive market sentiment")
                elif component == "valuation":
                    positives.append("Compelling valuation")
        elif contribution < 10:  # Weak contribution
            if component == "technicals":
                negatives.append("Weak technical signals")
            elif component == "fundamentals":
                negatives.append("Concerning fundamentals")
            elif component == "growth_prospects":
                negatives.append("Limited growth potential")
    
    # Add specific metric-based factors
    fund = analysis.get("fundamentals", {})
    if fund.get("pe") and fund["pe"] > 30:
        negatives.append("High P/E ratio")
    if fund.get("roe") and fund["roe"] > 0.20:
        if is_buy_signal or not is_sell_signal:
            positives.append(f"Strong ROE of {fund['roe']:.1f}%")
    if fund.get("debtToEquity") and fund["debtToEquity"] > 2:
        negatives.append("High leverage")
    
    # Add peer analysis insights
    peer = analysis.get("peer_analysis", {})
    if peer.get("relative_position"):
        position = peer["relative_position"].lower()
        if "above-average" in position and (is_buy_signal or not is_sell_signal):
            positives.append("Outperforming peers")
        elif "below-average" in position:
            negatives.append("Underperforming peers")
    
    # For sell signals, prioritize negative factors
    if is_sell_signal:
        # Add more negative factors for sell decisions
        if fund.get("pe") and fund["pe"] > 25:
            negatives.append("Elevated valuation")
        if len(positives) > len(negatives):
            # Balance by adding generic negatives
            negatives.extend(["Market headwinds", "Risk factors present"])
        # Limit positives for sell signals
        positives = positives[:1] if positives else ["Limited defensive qualities"]
    
    # For buy signals, prioritize positive factors
    elif is_buy_signal:
        if len(negatives) > len(positives):
            # Balance by adding generic positives
            positives.extend(["Strong fundamentals", "Growth potential"])
        # Limit negatives for buy signals
        negatives = negatives[:2] if negatives else ["Market volatility risk"]
    
    # Ensure we have appropriate balance based on score
    if not positives:
        if is_sell_signal:
            positives.append("Some defensive qualities")
        else:
            positives.append("Stable market position")
    if not negatives:
        if is_buy_signal:
            negatives.append("Market volatility risk")
        else:
            negatives.append("Uncertain outlook")
    
    return positives[:3], negatives[:3]


async def enhanced_synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Enhanced synthesis node that processes multiple tickers in parallel
    with adaptive scoring, explainability, and comprehensive analysis
    """
    
    tickers = state.get("tickers", [])
    if not tickers:
        logger.warning("No tickers provided for synthesis")
        state["final_output"] = {
            "tickers": [],
            "reports": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": "No tickers provided"
        }
        return state
    
    # DEBUG: Check what's in the state
    all_analysis = state.get("analysis", {})
    all_confidences = state.get("confidences", {})
    logger.info(f"DEBUG: tickers={tickers}, analysis_keys={list(all_analysis.keys())[:10]}, confidences_keys={list(all_confidences.keys())[:10]}")
    logger.info(f"DEBUG: analysis structure sample: {dict(list(all_analysis.items())[:2])}")
    
    # Get market context (would be fetched from market data APIs)
    market_context = state.get("market_context", {
        "vix": 20,
        "trend": "neutral",
        "sp500_pe": 22,
        "yield_curve": "normal"
    })
    
    # Process all tickers in parallel
    analysis_tasks = []
    for ticker in tickers:
        # Extract ticker-specific analysis and confidences
        all_analysis = state.get("analysis", {})
        all_confidences = state.get("confidences", {})
        
        # For single ticker, analysis might be flat (not nested by ticker)
        if len(tickers) == 1 and ticker not in all_analysis and any(key in all_analysis for key in ['technicals', 'fundamentals', 'news_sentiment']):
            ticker_analysis = all_analysis  # Single ticker case - use flat structure
            ticker_confidences = all_confidences
        else:
            # Multi-ticker case - use nested structure
            ticker_analysis = all_analysis.get(ticker, {})
            ticker_confidences = all_confidences.get(ticker, {})
        
        # Create analysis task for this ticker
        task = process_ticker_analysis(
            ticker,
            ticker_analysis,
            ticker_confidences,
            market_context,
            settings
        )
        analysis_tasks.append(task)
    
    # Execute all analyses in parallel
    reports = await asyncio.gather(*analysis_tasks, return_exceptions=True)
    
    # Filter out any failed analyses
    valid_reports = []
    for i, report in enumerate(reports):
        if isinstance(report, Exception):
            logger.error(f"Failed to analyze {tickers[i]}: {report}")
        else:
            valid_reports.append(report)
    
    # Sort reports by rating (highest first)
    valid_reports.sort(key=lambda x: x["decision"]["rating"], reverse=True)
    
    # Create comparative analysis if multiple tickers
    comparative_analysis = None
    if len(valid_reports) > 1:
        comparative_analysis = create_comparative_analysis(valid_reports)
    
    # Debug: Check response size before setting
    import json
    temp_output = {
        "tickers": tickers,
        "reports": valid_reports,
        "comparative_analysis": comparative_analysis,
        "market_context": market_context,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": {
            "scoring": "Adaptive sector/regime-based weighting",
            "explainability": "Component-level contribution tracking",
            "confidence": "Node-level confidence aggregation"
        }
    }
    
    try:
        # Estimate JSON size
        json_str = json.dumps(temp_output)
        logger.info(f"Final output JSON size: {len(json_str)} chars ({len(json_str)/1024/1024:.2f} MB)")
        if len(json_str) > 10_000_000:  # >10MB
            logger.error(f"Response too large! Truncating details...")
            # Strip details from reports to reduce size
            for report in valid_reports:
                for section_name, section_data in report.items():
                    if isinstance(section_data, dict) and "details" in section_data:
                        section_data["details"] = {"truncated": True, "reason": "response_too_large"}
            logger.info("Details truncated to reduce response size")
            
            # Re-calculate size after truncation
            json_str = json.dumps(temp_output)
            logger.info(f"After truncation: {len(json_str)} chars ({len(json_str)/1024/1024:.2f} MB)")
    except Exception as e:
        logger.warning(f"Failed to estimate response size: {e}")
    
    state["final_output"] = temp_output
    
    state.setdefault("confidences", {})["synthesis"] = 0.95
    
    return state


def create_comparative_analysis(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create comparative analysis across multiple tickers"""
    
    if not reports:
        return {}
    
    # Extract key metrics for comparison
    comparison_data = []
    for report in reports:
        comparison_data.append({
            "ticker": report["ticker"],
            "action": report["decision"]["action"],
            "rating": report["decision"]["rating"],
            "expected_return": report["decision"]["expected_return_pct"],
            "confidence": report["decision"]["confidence"],
            "sector": report["metadata"]["sector"],
            "pe": report["fundamentals"]["details"].get("pe"),
            "roe": report["fundamentals"]["details"].get("roe"),
            "growth": report["growth_prospects"].get("growth_outlook", {}).get("overall_outlook"),
            "valuation_upside": report["valuation"]["details"].get("consolidated_valuation", {}).get("upside_downside_pct")
        })
    
    # Identify best opportunities
    best_overall = max(comparison_data, key=lambda x: x["rating"])
    best_value = min((d for d in comparison_data if d["pe"]), key=lambda x: x["pe"], default=None) if any(d.get("pe") for d in comparison_data) else None
    best_growth = max((d for d in comparison_data if d["growth"]), key=lambda x: str(x["growth"]), default=None) if any(d.get("growth") for d in comparison_data) else None
    highest_confidence = max(comparison_data, key=lambda x: x["confidence"])
    
    return {
        "summary": f"Analyzed {len(reports)} stocks. Top pick: {best_overall['ticker']} (Rating: {best_overall['rating']:.1f}/5)",
        "rankings": comparison_data,
        "recommendations": {
            "best_overall": best_overall["ticker"],
            "best_value": best_value["ticker"] if best_value else None,
            "best_growth": best_growth["ticker"] if best_growth else None,
            "highest_confidence": highest_confidence["ticker"]
        },
        "portfolio_suggestion": generate_portfolio_suggestion(comparison_data)
    }


def generate_portfolio_suggestion(comparison_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate portfolio allocation suggestion"""
    
    # Filter for buy recommendations
    buy_candidates = [d for d in comparison_data if "Buy" in d["action"]]
    
    if not buy_candidates:
        return {"message": "No buy recommendations in current analysis"}
    
    # Simple equal-weight suggestion for now
    # Could be enhanced with risk-parity or optimization
    allocation = 100 / len(buy_candidates)
    
    return {
        "suggested_allocation": {
            candidate["ticker"]: f"{allocation:.1f}%"
            for candidate in buy_candidates
        },
        "risk_level": "Moderate",
        "diversification": f"Across {len(set(c['sector'] for c in buy_candidates))} sectors"
    }
