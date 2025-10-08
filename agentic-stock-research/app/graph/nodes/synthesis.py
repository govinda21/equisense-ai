from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import AppSettings
from app.graph.state import ResearchState
import logging

logger = logging.getLogger(__name__)


def _score_to_action(score: float) -> str:
    """Convert score to professional investment recommendation"""
    if score >= 0.85:
        return "Strong Buy"
    elif score >= 0.70:
        return "Buy"
    elif score >= 0.55:
        return "Hold"
    elif score >= 0.40:
        return "Sell"
    else:
        return "Strong Sell"


def _score_to_letter_grade(score: float) -> str:
    """Convert numeric score to letter grade rating"""
    if score >= 0.93:
        return "A+"
    elif score >= 0.87:
        return "A"
    elif score >= 0.83:
        return "A-"
    elif score >= 0.77:
        return "B+"
    elif score >= 0.73:
        return "B"
    elif score >= 0.67:
        return "B-"
    elif score >= 0.63:
        return "C+"
    elif score >= 0.57:
        return "C"
    elif score >= 0.53:
        return "C-"
    elif score >= 0.47:
        return "D+"
    elif score >= 0.40:
        return "D"
    elif score >= 0.33:
        return "D-"
    else:
        return "F"


def _generate_star_display(score: float) -> str:
    """Generate star display with proper unicode stars"""
    rating_out_of_5 = score * 5
    full_stars = int(rating_out_of_5)
    has_half_star = (rating_out_of_5 - full_stars) >= 0.5
    
    stars = "★" * full_stars
    if has_half_star and full_stars < 5:
        stars += "☆"
        full_stars += 1
    
    # Fill remaining with empty stars
    empty_stars = 5 - len(stars)
    stars += "☆" * empty_stars
    
    return stars


def _generate_professional_rationale(score: float, action: str, positives: list, negatives: list, analysis: dict) -> str:
    """Generate formal investment analysis rationale"""
    # Extract key data points for rationale
    fund = analysis.get("fundamentals", {})
    tech = analysis.get("technicals", {})
    growth = analysis.get("growth_prospects", {})
    cashflow = analysis.get("cashflow", {})
    
    # Build rationale based on recommendation type
    if action in ["Strong Buy", "Buy"]:
        focus_factors = positives[:2]  # Top 2 positive factors
        
        rationale_parts = []
        
        # Growth and fundamentals
        if any("growth" in factor.lower() for factor in focus_factors):
            rationale_parts.append("robust earnings growth trajectory")
        elif fund.get("roe") and fund["roe"] > 0.15:
            rationale_parts.append("strong return on equity metrics")
        else:
            rationale_parts.append("favorable fundamental indicators")
            
        # Technical or market position
        if any("technical" in factor.lower() or "momentum" in factor.lower() for factor in focus_factors):
            rationale_parts.append("positive technical momentum")
        elif any("position" in factor.lower() or "competitive" in factor.lower() for factor in focus_factors):
            rationale_parts.append("competitive market positioning")
        else:
            rationale_parts.append("supportive market dynamics")
            
        # Financial strength
        if cashflow.get("fcf_positive"):
            rationale_parts.append("solid free cash flow generation")
        elif fund.get("operatingMargins") and fund["operatingMargins"] > 0.15:
            rationale_parts.append("healthy operating margins")
        else:
            rationale_parts.append("sound financial foundation")
            
        if action == "Strong Buy":
            return f"Based on {', '.join(rationale_parts[:2])}, and {rationale_parts[2] if len(rationale_parts) > 2 else 'favorable industry trends'}, the equity demonstrates exceptional upside potential with a compelling risk-adjusted return profile over the next 12-18 months."
        else:
            return f"Supported by {', '.join(rationale_parts[:2])}, the stock presents attractive upside potential, though investors should monitor {negatives[0].lower() if negatives else 'market volatility'} as a key risk factor."
            
    elif action == "Hold":
        balanced_view = []
        if positives:
            balanced_view.append(f"while {positives[0].lower()} provides support")
        if negatives:
            balanced_view.append(f"{negatives[0].lower()} creates near-term uncertainty")
            
        return f"The investment thesis remains balanced, {' and '.join(balanced_view) if balanced_view else 'with mixed fundamental indicators'}. Current valuation appears fairly priced, warranting a cautious approach until greater clarity emerges on key operational metrics."
        
    else:  # Sell or Strong Sell
        risk_factors = negatives[:2] if negatives else ["deteriorating fundamentals", "unfavorable market conditions"]
        
        if action == "Strong Sell":
            return f"Significant concerns regarding {risk_factors[0].lower()} and {risk_factors[1].lower() if len(risk_factors) > 1 else 'operational headwinds'} present substantial downside risk. The current risk-reward profile is unfavorable, suggesting defensive positioning is prudent."
        else:
            return f"Given {risk_factors[0].lower()} and {risk_factors[1].lower() if len(risk_factors) > 1 else 'sector headwinds'}, the near-term outlook appears challenging. Profit-taking may be warranted while monitoring for potential re-entry opportunities."


def _safe_get_letter_grade(score: float) -> str:
    """Safe wrapper for letter grade generation"""
    try:
        if score is None or not isinstance(score, (int, float)):
            return "C"
        result = _score_to_letter_grade(score)
        logger.info(f"Generated letter grade: {result} from score: {score}")
        return result if result else "C"
    except Exception as e:
        logger.error(f"Error generating letter grade: {e}")
        return "C"


def _safe_get_star_display(score: float) -> str:
    """Safe wrapper for star display generation"""
    try:
        if score is None or not isinstance(score, (int, float)):
            return "★★★☆☆"
        result = _generate_star_display(score)
        logger.info(f"Generated stars: {result} from score: {score}")
        return result if result else "★★★☆☆"
    except Exception as e:
        logger.error(f"Error generating star display: {e}")
        return "★★★☆☆"


def _safe_get_professional_rationale(score: float, action: str, positives: list, negatives: list, analysis: dict) -> str:
    """Safe wrapper for professional rationale generation"""
    try:
        if score is None or not isinstance(score, (int, float)):
            score = 0.5
        if not action:
            action = "Hold"
        result = _generate_professional_rationale(score, action, positives or [], negatives or [], analysis or {})
        logger.info(f"Generated rationale: {result[:50]}... from score: {score}, action: {action}")
        return result if result else f"Analysis supports a {action.lower()} recommendation based on current market conditions."
    except Exception as e:
        logger.error(f"Error generating professional rationale: {e}")
        return f"Analysis based on current market conditions and fundamental metrics supports a {action.lower() if action else 'hold'} recommendation with appropriate risk management considerations."


def _safe_get_professional_recommendation(action: str, score: float) -> str:
    """Safe wrapper for professional recommendation generation"""
    try:
        if score is None or not isinstance(score, (int, float)):
            score = 0.5
        if not action:
            action = "Hold"
        stars = _generate_star_display(score)[:5]
        result = f"{action} ({round(score * 5, 1)}/5 {stars})"
        logger.info(f"Generated professional recommendation: {result}")
        return result
    except Exception as e:
        logger.error(f"Error generating professional recommendation: {e}")
        return f"{action} ({round(score * 5, 1) if score else 2.5}/5)"


def _build_executive_summary(action: str, score: float, analysis: dict, positives: list, negatives: list) -> str:
    """Create a concise one-line executive summary.
    Uses comprehensive fundamentals (DCF) if available; otherwise omits gracefully.
    """
    try:
        parts: list[str] = []
        parts.append(f"{action}: {round(score * 100)}")

        comp = analysis.get("comprehensive_fundamentals") or {}
        dcf = comp.get("dcf_valuation") or {}
        iv = dcf.get("intrinsic_value")
        mos = dcf.get("margin_of_safety")

        if isinstance(iv, (int, float)):
            parts.append(f"IV {iv:.2f}")
        if isinstance(mos, (int, float)):
            parts.append(f"MoS {round(mos * 100)}%")

        if positives:
            parts.append("Key: " + ", ".join([p for p in positives[:2] if isinstance(p, str) and p]))
        if negatives:
            parts.append("Risks: " + ", ".join([n for n in negatives[:2] if isinstance(n, str) and n]))

        return "; ".join([p for p in parts if p])
    except Exception:
        try:
            return f"{action}: {round(score * 100)}; Key: {', '.join((positives or [])[:2])} | Risks: {', '.join((negatives or [])[:2])}"
        except Exception:
            return f"{action}: {round(score * 100)}"

def _create_comprehensive_fundamentals_output(comprehensive_fund: dict) -> dict:
    """Create comprehensive fundamentals output for API response"""
    try:
        trading_recs = comprehensive_fund.get("trading_recommendations", {})
        entry_zone = trading_recs.get("entry_zone", (0.0, 0.0))
        
        return {
            "overall_score": comprehensive_fund.get("overall_score", 50.0),
            "overall_grade": comprehensive_fund.get("overall_grade", "C"),
            "recommendation": comprehensive_fund.get("recommendation", "Hold"),
            "confidence_level": comprehensive_fund.get("confidence_level", 0.5),
            
            # DCF Valuation
            "intrinsic_value": comprehensive_fund.get("dcf_valuation", {}).get("intrinsic_value"),
            "margin_of_safety": comprehensive_fund.get("dcf_valuation", {}).get("margin_of_safety"),
            "upside_potential": comprehensive_fund.get("dcf_valuation", {}).get("upside_potential"),
            
            # Pillar scores
            "financial_health_score": comprehensive_fund.get("pillar_scores", {}).get("financial_health", {}).get("score", 50.0),
            "valuation_score": comprehensive_fund.get("pillar_scores", {}).get("valuation", {}).get("score", 50.0),
            "growth_prospects_score": comprehensive_fund.get("pillar_scores", {}).get("growth_prospects", {}).get("score", 50.0),
            "governance_score": comprehensive_fund.get("pillar_scores", {}).get("governance", {}).get("score", 50.0),
            "macro_sensitivity_score": comprehensive_fund.get("pillar_scores", {}).get("macro_sensitivity", {}).get("score", 50.0),
            
            # Trading recommendations
            "position_sizing_pct": trading_recs.get("position_sizing_pct", 1.0),
            "entry_zone_low": entry_zone[0] if isinstance(entry_zone, (list, tuple)) and len(entry_zone) > 0 else 0.0,
            "entry_zone_high": entry_zone[1] if isinstance(entry_zone, (list, tuple)) and len(entry_zone) > 1 else 0.0,
            "target_price": trading_recs.get("target_price", 0.0),
            "stop_loss": trading_recs.get("stop_loss", 0.0),
            "time_horizon_months": trading_recs.get("time_horizon_months", 12),
            
            # Risk assessment
            "risk_rating": comprehensive_fund.get("risk_assessment", {}).get("risk_rating", "Medium"),
            "key_risks": comprehensive_fund.get("risk_assessment", {}).get("key_risks", []),
            "key_catalysts": comprehensive_fund.get("risk_assessment", {}).get("key_catalysts", []),
            "key_insights": comprehensive_fund.get("key_insights", []),
            
            # Data quality
            "data_quality": comprehensive_fund.get("data_quality", {}).get("overall_quality", "medium")
        }
    except Exception as e:
        logger.error(f"Error creating comprehensive fundamentals output: {e}")
        return {
            "overall_score": 50.0,
            "overall_grade": "C",
            "recommendation": "Hold",
            "confidence_level": 0.1,
            "error": str(e)
        }


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

    # Check if comprehensive fundamentals analysis is available
    comprehensive_fund = a.get("comprehensive_fundamentals", {})
    
    # Use comprehensive analysis if available, otherwise fall back to LLM
    if comprehensive_fund and comprehensive_fund.get("overall_score"):
        logger.info(f"Using comprehensive fundamentals analysis for {ticker}")
        
        # Convert 0-100 score to 0-1 scale
        composite_score = comprehensive_fund["overall_score"] / 100.0
        action = comprehensive_fund.get("recommendation", "Hold")
        # Prefer comprehensive expected return if present, else infer from intrinsic value
        tr = comprehensive_fund.get("trading_recommendations", {})
        expected_return = None
        try:
            mos = comprehensive_fund.get("dcf_valuation", {}).get("margin_of_safety")
            if isinstance(mos, (int, float)):
                expected_return = round(mos * 100, 1)
        except Exception:
            expected_return = None
        if expected_return is None:
            try:
                upside = tr.get("upside_potential")
                if isinstance(upside, (int, float)):
                    expected_return = round(upside * 100, 1)
            except Exception:
                pass
        if expected_return is None:
            expected_return = 0.0
        
        # Extract factors from comprehensive analysis
        positives = []
        negatives = []
        
        # Collect positive factors from all pillars
        for pillar_name, pillar_data in comprehensive_fund.get("pillar_scores", {}).items():
            if isinstance(pillar_data, dict):
                positives.extend(pillar_data.get("positive_factors", [])[:1])  # Top 1 from each pillar
                negatives.extend(pillar_data.get("negative_factors", [])[:1])   # Top 1 from each pillar
        
        # Use key insights if available
        key_insights = comprehensive_fund.get("key_insights", [])
        if key_insights:
            positives.extend([insight for insight in key_insights if any(word in insight.lower() for word in ["strong", "good", "excellent", "positive", "attractive"])])
            negatives.extend([insight for insight in key_insights if any(word in insight.lower() for word in ["weak", "poor", "concern", "risk", "high"])])
        
        # Limit to top 3 each
        positives = positives[:3] if positives else ["Strong comprehensive analysis"]
        negatives = negatives[:3] if negatives else ["Market volatility risk"]
        
        llm_parsed = True  # Mark as parsed since we have structured data
        
    else:
        # Fall back to LLM analysis
        logger.info(f"Using LLM analysis for {ticker} (no comprehensive fundamentals available)")
        
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
        
        # Debug logging
        if llm_response:
            logger.info(f"LLM response length: {len(llm_response)} chars")
            logger.info(f"LLM response preview: {llm_response[:500]}...")
        else:
            logger.warning("No LLM response received")
        
        # Parse LLM response with better error handling
        composite_score = 0.5  # default
        action = "Hold"
        positives = ["Analysis pending"]
        negatives = ["Analysis pending"]
        expected_return = 0.0
        llm_parsed = False
        
        if llm_response:
            try:
                # Truncate extremely long responses (might indicate an issue)
                if len(llm_response) > 10000:
                    logger.warning(f"Truncating very long LLM response: {len(llm_response)} chars")
                    llm_response = llm_response[:10000]
                
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
                            parsed_score = float(match.group(1))
                            composite_score = min(1.0, max(0.0, parsed_score))
                            logger.info(f"Parsed LLM score: {parsed_score} -> {composite_score}")
                            llm_parsed = True
                            break
                        except Exception as parse_err:
                            logger.warning(f"Failed to parse score '{match.group(1)}': {parse_err}")
                            continue
                
                # Extract action with better patterns
                action_patterns = [
                    (r'action[:\s]*(buy|hold|sell)', 1),
                    (r'recommendation[:\s]*(buy|hold|sell)', 1),
                    (r'\b(strong\s+buy|buy|hold|sell|strong\s+sell)\b', 1)
                ]
                for pattern, group in action_patterns:
                    match = re.search(pattern, response_lower)
                    if match:
                        extracted_action = match.group(group).strip()
                        if 'buy' in extracted_action:
                            action = "Strong Buy" if 'strong' in extracted_action else "Buy"
                        elif 'sell' in extracted_action:
                            action = "Strong Sell" if 'strong' in extracted_action else "Sell"
                        elif 'hold' in extracted_action:
                            action = "Hold"
                        logger.info(f"Parsed LLM action: {extracted_action} -> {action}")
                        llm_parsed = True
                        break
                
                # Extract positives and negatives using simple string parsing
                pos_start = llm_response.find('**POSITIVES:**')
                pos_end = llm_response.find('**NEGATIVES:**')
                if pos_start >= 0 and pos_end >= 0:
                    pos_text = llm_response[pos_start+14:pos_end].strip()
                    logger.info(f"DEBUG: Positives text found: {repr(pos_text[:200])}")
                    
                    # Extract numbered list items with titles
                    pos_items = re.findall(r'(?:\d+\.|\*)\s*\*\*([^*]+)\*\*', pos_text)
                    if pos_items:
                        positives = [title.strip().rstrip(':') for title in pos_items[:3] if title.strip()]
                        logger.info(f"Parsed positives: {positives}")
                        llm_parsed = True
                    else:
                        positives = ["Strong fundamentals"]
                        logger.info("Using fallback positives")
                else:
                    positives = ["Strong fundamentals"]
                    logger.info("POSITIVES section not found")
                
                neg_start = llm_response.find('**NEGATIVES:**')
                neg_end_candidates = [
                    llm_response.find('**RETURN:'),
                    llm_response.find('**SCORE:'),
                    len(llm_response)
                ]
                neg_end = min([x for x in neg_end_candidates if x > neg_start]) if neg_start >= 0 else -1
                
                if neg_start >= 0 and neg_end > neg_start:
                    neg_text = llm_response[neg_start+13:neg_end].strip()
                    logger.info(f"DEBUG: Negatives text found: {repr(neg_text[:200])}")
                    
                    # Extract numbered list items with titles
                    neg_items = re.findall(r'(?:\d+\.|\*)\s*\*\*([^*]+)\*\*', neg_text)
                    if neg_items:
                        negatives = [title.strip().rstrip(':') for title in neg_items[:3] if title.strip()]
                        logger.info(f"Parsed negatives: {negatives}")
                        llm_parsed = True
                    else:
                        negatives = ["Market volatility"]
                        logger.info("Using fallback negatives")
                else:
                    negatives = ["Market volatility"]
                    logger.info("NEGATIVES section not found")
                
                # Extract expected return
                return_match = re.search(r'return[:\s]*([+-]?[0-9]*\.?[0-9]+)', response_lower)
                if return_match:
                    try:
                        expected_return = float(return_match.group(1))
                        logger.info(f"Parsed expected return: {expected_return}%")
                        llm_parsed = True
                    except Exception as ret_err:
                        logger.warning(f"Failed to parse return '{return_match.group(1)}': {ret_err}")
                    
            except Exception as e:
                logger.error(f"Error parsing LLM response: {e}")
                logger.debug(f"Full response: {llm_response}")
                pass
    
    # Calculate deterministic base score and combine with LLM adjustment
    base_score = _calculate_base_score(a)
    
    if llm_parsed and abs(composite_score - 0.5) > 0.1:
        # Use LLM score if it seems reasonable, but cap adjustment at ±0.2
        llm_adjustment = max(-0.2, min(0.2, composite_score - base_score))
        composite_score = base_score + llm_adjustment
        logger.info(f"Using LLM-adjusted score: {base_score} + {llm_adjustment} = {composite_score}")
    else:
        # Use deterministic score
        composite_score = base_score
        logger.info(f"Using deterministic score: {composite_score}")
        
        # Generate consistent fallback reasons based on the score
        if not llm_parsed:
            logger.info("LLM parsing failed, generating fallback reasons based on score")
            action = _score_to_action(composite_score)
            
            if composite_score >= 0.6:
                positives = ["Strong fundamentals" if fund else "Favorable metrics", 
                           "Positive technicals" if tech else "Market position",
                           "Growth potential" if growth else "Analyst support"]
                negatives = ["Market volatility risk", "Sector headwinds"]
            elif composite_score >= 0.4:
                positives = ["Some positive signals", "Stable operations"]
                negatives = ["Mixed indicators", "Uncertain outlook", "Risk factors present"]
            else:
                positives = ["Limited upside potential", "Some defensive qualities"]
                negatives = ["Weak fundamentals" if fund else "Poor metrics",
                           "Negative technicals" if tech else "Underperformance", 
                           "High risk factors"]
                           
            # Calculate expected return based on score
            expected_return = round((composite_score - 0.5) * 40, 1)
            
            logger.info(f"Generated fallback: action={action}, expected_return={expected_return}%")

    # Build robust executive summary string
    exec_summary = _build_executive_summary(action, composite_score, a, positives, negatives)

    state["final_output"] = {
        "tickers": state["tickers"],
        "reports": [
            {
                "ticker": ticker,
                "executive_summary": exec_summary,
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
                "comprehensive_fundamentals": _create_comprehensive_fundamentals_output(comprehensive_fund) if comprehensive_fund else None,
            }
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # DEBUG: About to create decision with professional fields
    logger.info(f"Creating decision object with score={composite_score}, action={action}")
    
    # Add decision to the first report
    state["final_output"]["reports"][0]["decision"] = {
                    "action": action,
                    "rating": round(composite_score * 5, 2),
                    "letter_grade": _safe_get_letter_grade(composite_score),
                    "stars": _safe_get_star_display(composite_score),
                    "professional_rationale": _safe_get_professional_rationale(
                        composite_score, action, positives, negatives, a
                    ),
                    "expected_return_pct": expected_return,
                    "top_reasons_for": positives,
                    "top_reasons_against": negatives,
                    "llm_parsed": llm_parsed,
                    "base_score": round(base_score, 3),
                    "professional_recommendation": _safe_get_professional_recommendation(action, composite_score),
                    "debug_test": "professional_fields_in_main_decision"
    }
    state.setdefault("confidences", {})["synthesis"] = 0.9
    return state
