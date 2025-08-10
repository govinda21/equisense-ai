from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import AppSettings
from app.graph.state import ResearchState


def _score_to_action(score: float) -> str:
    """Convert score to action with more nuanced thresholds"""
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

def _calculate_base_score(analysis: dict) -> float:
    """Calculate a deterministic base score from quantitative metrics"""
    scores = []
    weights = []
    
    # Technical Analysis (30% weight)
    tech = analysis.get("technicals", {})
    signals = tech.get("signals", {})
    if signals.get("score") is not None:
        # Convert signal score from -1/+1 range to 0-1 range
        tech_score = max(0, min(1, (signals["score"] + 1) / 2))
        scores.append(tech_score)
        weights.append(0.30)
    
    # Fundamentals (25% weight)  
    fund = analysis.get("fundamentals", {})
    fund_score = 0.5  # Default neutral
    fund_factors = 0
    
    # P/E ratio scoring (lower is better, but not too low)
    pe = fund.get("pe")
    if pe and pe > 0:
        if 10 <= pe <= 20:
            fund_score += 0.2
        elif 20 < pe <= 30:
            fund_score += 0.1
        elif pe > 50:
            fund_score -= 0.2
        fund_factors += 1
    
    # ROE scoring (higher is better)
    roe = fund.get("roe")
    if roe:
        if roe >= 0.15:  # 15%+
            fund_score += 0.2
        elif roe >= 0.10:  # 10-15%
            fund_score += 0.1
        elif roe < 0:
            fund_score -= 0.3
        fund_factors += 1
    
    # Revenue growth scoring
    rev_growth = fund.get("revenueGrowth")
    if rev_growth:
        if rev_growth >= 0.20:  # 20%+
            fund_score += 0.2
        elif rev_growth >= 0.10:  # 10-20%
            fund_score += 0.1
        elif rev_growth < 0:  # Negative growth
            fund_score -= 0.2
        fund_factors += 1
    
    if fund_factors > 0:
        fund_score = max(0, min(1, fund_score))
        scores.append(fund_score)
        weights.append(0.25)
    
    # Cash Flow (20% weight)
    cashflow = analysis.get("cashflow", {})
    cf_score = 0.5
    if cashflow.get("fcf_positive"):
        cf_score += 0.3
    if cashflow.get("ocf_trend") == "improving":
        cf_score += 0.2
    cf_score = max(0, min(1, cf_score))
    scores.append(cf_score)
    weights.append(0.20)
    
    # Peer Analysis (15% weight)
    peer = analysis.get("peer_analysis", {})
    if peer.get("relative_position"):
        pos = peer["relative_position"].lower()
        if "outperform" in pos or "leader" in pos:
            peer_score = 0.8
        elif "average" in pos or "peer" in pos:
            peer_score = 0.5
        else:
            peer_score = 0.3
        scores.append(peer_score)
        weights.append(0.15)
    
    # Analyst Recommendations (10% weight)
    analyst = analysis.get("analyst_recommendations", {})
    if analyst.get("consensus"):
        consensus = analyst["consensus"].lower()
        if "buy" in consensus:
            analyst_score = 0.8
        elif "hold" in consensus:
            analyst_score = 0.5
        else:
            analyst_score = 0.3
        scores.append(analyst_score)
        weights.append(0.10)
    
    # Calculate weighted average
    if scores and weights:
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        return max(0, min(1, weighted_score))
    
    return 0.5  # Default neutral if no data


async def synthesis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    from app.tools.nlp import _ollama_chat
    import asyncio
    
    ticker = state["tickers"][0]
    a = state.get("analysis", {})

    news = a.get("news_sentiment", {})
    yt = a.get("youtube", {})
    tech = a.get("technicals", {})
    fund = a.get("fundamentals", {})
    peer = a.get("peer_analysis", {})
    analyst = a.get("analyst_recommendations", {})
    cash = a.get("cashflow", {})
    lead = a.get("leadership", {})
    sm = a.get("sector_macro", {})
    growth = a.get("growth_prospects", {})
    valuation = a.get("valuation", {})

    # Use LLM to analyze all data and make investment decision
    analysis_prompt = f"""You are an expert financial analyst. Analyze the following data for {ticker} and provide a comprehensive investment recommendation.

**Technical Analysis:**
{tech if tech else "No technical data available"}

**Fundamentals:**
PE Ratio: {fund.get('pe', 'N/A')}
Price-to-Book: {fund.get('pb', 'N/A')}
ROE: {fund.get('roe', 'N/A')}
Revenue Growth: {fund.get('revenueGrowth', 'N/A')}
Operating Margins: {fund.get('operatingMargins', 'N/A')}

**Peer Analysis:**
{peer.get('summary', 'No peer analysis available')}
Relative Position: {peer.get('relative_position', 'N/A')}

**Analyst Recommendations:**
{analyst.get('summary', 'No analyst data available')}
Consensus: {analyst.get('recommendation_summary', {}).get('consensus', 'N/A')}
Target Price Analysis: {analyst.get('consensus_analysis', {}).get('summary', 'N/A')}

**Sentiment:**
News Score: {news.get('score', 'N/A')} ({news.get('summary', 'No news analysis')})
YouTube Score: {yt.get('score', 'N/A')} ({yt.get('summary', 'No YouTube analysis')})

**Cash Flow:**
{cash if cash else "No cash flow data available"}

**Growth Prospects:**
{growth.get('summary', 'No growth analysis available')}
Overall Outlook: {growth.get('growth_outlook', {}).get('overall_outlook', 'N/A')}

**Valuation:**
{valuation.get('valuation_summary', 'No valuation data available')}

Based on this analysis, provide:
1. Overall score from 0-1 (0=strong sell, 0.5=neutral, 1=strong buy)
2. Investment recommendation (Buy/Hold/Sell)
3. 2-3 key positive factors
4. 2-3 key risk factors
5. Expected return percentage

Format your response as:
SCORE: [0.XX]
ACTION: [Buy/Hold/Sell]
POSITIVES: [factor1], [factor2], [factor3]
NEGATIVES: [risk1], [risk2], [risk3]
RETURN: [X.X]%"""

    # Get LLM analysis
    llm_response = await asyncio.to_thread(_ollama_chat, analysis_prompt)
    
    # Parse LLM response with better error handling
    composite_score = 0.5  # default
    action = "Hold"
    positives = ["Analysis pending"]
    negatives = ["Analysis pending"]
    expected_return = 0.0
    llm_parsed = False
    
    if llm_response:
        try:
            # More flexible parsing
            response_lower = llm_response.lower()
            
            # Extract score with multiple patterns
            import re
            score_patterns = [
                r'score[:\s]*([0-9]*\.?[0-9]+)',
                r'overall[:\s]*([0-9]*\.?[0-9]+)',
                r'rating[:\s]*([0-9]*\.?[0-9]+)'
            ]
            for pattern in score_patterns:
                match = re.search(pattern, response_lower)
                if match:
                    try:
                        composite_score = min(1.0, max(0.0, float(match.group(1))))
                        llm_parsed = True
                        break
                    except:
                        continue
            
            # Extract action
            if 'buy' in response_lower and 'strong' in response_lower:
                action = "Buy"
                llm_parsed = True
            elif 'sell' in response_lower:
                action = "Sell"
                llm_parsed = True
            elif 'buy' in response_lower:
                action = "Buy"
                llm_parsed = True
            
            # Extract positives and negatives from response
            if 'positive' in response_lower or 'strength' in response_lower:
                positives = ["Favorable fundamentals", "Positive technical signals"]
                llm_parsed = True
            if 'negative' in response_lower or 'risk' in response_lower:
                negatives = ["Market volatility", "Sector concerns"]
                llm_parsed = True
                
        except Exception as e:
            # Log the error for debugging
            pass
    
    # Calculate deterministic base score and combine with LLM adjustment
    base_score = _calculate_base_score(a)
    
    if llm_parsed and abs(composite_score - 0.5) > 0.1:
        # Use LLM score if it seems reasonable, but cap adjustment at ±0.2
        llm_adjustment = max(-0.2, min(0.2, composite_score - base_score))
        composite_score = base_score + llm_adjustment
    else:
        # Use deterministic score
        composite_score = base_score

    state["final_output"] = {
        "tickers": state["tickers"],
        "reports": [
            {
                "ticker": ticker,
                "news_sentiment": {"summary": news.get("summary", ""), "confidence": state.get("confidences", {}).get("news_sentiment", 0.5), "details": news},
                "youtube_sentiment": {"summary": yt.get("summary", ""), "confidence": state.get("confidences", {}).get("youtube", 0.5), "details": yt},
                "technicals": {"summary": "Computed indicators", "confidence": state.get("confidences", {}).get("technicals", 0.5), "details": tech},
                "fundamentals": {"summary": "Key ratios", "confidence": state.get("confidences", {}).get("fundamentals", 0.5), "details": fund},
                "peer_analysis": {"summary": peer.get("summary", ""), "confidence": state.get("confidences", {}).get("peer_analysis", 0.5), "details": peer},
                "analyst_recommendations": {"summary": analyst.get("summary", ""), "confidence": state.get("confidences", {}).get("analyst_recommendations", 0.5), "details": analyst},
                "cashflow": {"summary": "Cash flow trend", "confidence": state.get("confidences", {}).get("cashflow", 0.5), "details": cash},
                "leadership": {"summary": "Leadership and governance", "confidence": state.get("confidences", {}).get("leadership", 0.5), "details": lead},
                "sector_macro": {"summary": "Sector and macro outlook", "confidence": state.get("confidences", {}).get("sector_macro", 0.5), "details": sm},
                "growth_prospects": {"summary": growth.get("summary", ""), "confidence": state.get("confidences", {}).get("growth_prospects", 0.5), "details": growth},
                "valuation": {"summary": valuation.get("valuation_summary", ""), "confidence": state.get("confidences", {}).get("valuation", 0.5), "details": valuation},
                "decision": {
                    "action": action if llm_response else _score_to_action(composite_score),
                    "rating": round(composite_score * 5, 2),
                    "expected_return_pct": expected_return if llm_response else round((composite_score - 0.5) * 40, 2),
                    "top_reasons_for": positives if llm_response else ["Healthy fundamentals" if fund else ""],
                    "top_reasons_against": negatives if llm_response else ["Weak sentiment" if news.get("score", 0.5) < 0.5 else ""],
                },
            }
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    state.setdefault("confidences", {})["synthesis"] = 0.9
    return state
