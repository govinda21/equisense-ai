from __future__ import annotations

from typing import Any, Dict, List, Optional
import asyncio
import yfinance as yf
import statistics
from datetime import datetime, timedelta
import pandas as pd

from app.tools.finance import fetch_info


async def analyze_analyst_recommendations(ticker: str) -> Dict[str, Any]:
    """
    Retrieve and analyze consensus analyst recommendations from multiple sources.
    Calculate average price targets and provide recommendation distribution.
    """
    
    def _safe_float(x: Any) -> Optional[float]:
        try:
            if x is None:
                return None
            f = float(x)
            if f != f:  # Check for NaN
                return None
            return f
        except Exception:
            return None

    def _fetch_analyst_data() -> Dict[str, Any]:
        try:
            # Get company info and recommendations from yfinance
            company_info = yf.Ticker(ticker).info or {}
            current_price = _safe_float(company_info.get("currentPrice") or company_info.get("regularMarketPrice"))
            
            # Extract analyst recommendation data
            recommendation_key = company_info.get("recommendationKey", "").lower()
            recommendation_mean = _safe_float(company_info.get("recommendationMean"))
            
            # Get price targets
            target_high_price = _safe_float(company_info.get("targetHighPrice"))
            target_low_price = _safe_float(company_info.get("targetLowPrice"))
            target_mean_price = _safe_float(company_info.get("targetMeanPrice"))
            target_median_price = _safe_float(company_info.get("targetMedianPrice"))
            
            # Get analyst counts
            number_of_analyst_opinions = company_info.get("numberOfAnalystOpinions")
            
            # Try to get more detailed recommendation data with dates
            try:
                ticker_obj = yf.Ticker(ticker)
                recommendations_df = getattr(ticker_obj, "recommendations", None)
                upgrades_downgrades_df = getattr(ticker_obj, "upgrades_downgrades", None)
                
                recent_recommendations = []
                data_freshness = {}
                
                if recommendations_df is not None and not recommendations_df.empty:
                    # Get recent recommendations (last 10 entries)
                    recent_recs = recommendations_df.tail(10)
                    
                    for idx, row in recent_recs.iterrows():
                        # Extract date from index (can be datetime or Period)
                        if isinstance(idx, pd.Timestamp):
                            date_str = idx.strftime("%Y-%m-%d")
                        elif isinstance(idx, pd.Period):
                            date_str = str(idx)
                        else:
                            date_str = str(idx)
                        
                        rec_data = {
                            "date": date_str,
                            "strongBuy": int(row.get("strongBuy", 0)) if row.get("strongBuy") is not None else 0,
                            "buy": int(row.get("buy", 0)) if row.get("buy") is not None else 0,
                            "hold": int(row.get("hold", 0)) if row.get("hold") is not None else 0,
                            "sell": int(row.get("sell", 0)) if row.get("sell") is not None else 0,
                            "strongSell": int(row.get("strongSell", 0)) if row.get("strongSell") is not None else 0,
                        }
                        recent_recommendations.append(rec_data)
                    
                    # Calculate data freshness
                    if len(recent_recs) > 0:
                        latest_idx = recent_recs.index[-1]
                        oldest_idx = recent_recs.index[0]
                        
                        if isinstance(latest_idx, (pd.Timestamp, pd.Period)):
                            latest_date = pd.to_datetime(latest_idx).date() if isinstance(latest_idx, pd.Timestamp) else pd.to_datetime(str(latest_idx)).date()
                            oldest_date = pd.to_datetime(oldest_idx).date() if isinstance(oldest_idx, pd.Timestamp) else pd.to_datetime(str(oldest_idx)).date()
                            
                            days_old = (datetime.now().date() - latest_date).days
                            
                            data_freshness = {
                                "latest_recommendation_date": latest_date.isoformat(),
                                "oldest_recommendation_date": oldest_date.isoformat(),
                                "days_since_latest": days_old,
                                "data_span_days": (latest_date - oldest_date).days,
                                "freshness_status": "Current" if days_old <= 30 else "Stale" if days_old <= 90 else "Outdated"
                            }
                
                # Get recent upgrades/downgrades with dates
                recent_changes = []
                if upgrades_downgrades_df is not None and not upgrades_downgrades_df.empty:
                    recent_changes_df = upgrades_downgrades_df.tail(5)  # Last 5 changes
                    for idx, row in recent_changes_df.iterrows():
                        # Extract date from index
                        if isinstance(idx, pd.Timestamp):
                            date_str = idx.strftime("%Y-%m-%d")
                        else:
                            date_str = str(idx)
                            
                        change_data = {
                            "date": date_str,
                            "firm": row.get("Firm", "Unknown"),
                            "action": row.get("Action", ""),
                            "fromGrade": row.get("From Grade", ""),
                            "toGrade": row.get("To Grade", "")
                        }
                        recent_changes.append(change_data)
                        
            except Exception as e:
                recent_recommendations = []
                recent_changes = []
                data_freshness = {"error": f"Failed to extract dates: {str(e)}"}
            
            # Calculate consensus metrics
            consensus = _calculate_consensus(
                current_price, target_mean_price, target_high_price, target_low_price,
                target_median_price, recommendation_mean, recommendation_key,
                recent_recommendations
            )
            
            return {
                "current_price": current_price,
                "target_prices": {
                    "mean": target_mean_price,
                    "median": target_median_price,
                    "high": target_high_price,
                    "low": target_low_price,
                },
                "recommendation_summary": {
                    "consensus": recommendation_key.title() if recommendation_key else "N/A",
                    "mean_rating": recommendation_mean,
                    "analyst_count": number_of_analyst_opinions,
                },
                "recent_recommendations": recent_recommendations[-1] if recent_recommendations else {},
                "all_recommendations": recent_recommendations,  # All recommendations with dates
                "recent_changes": recent_changes,
                "data_freshness": data_freshness,  # New: Date metadata
                "consensus_analysis": consensus,
                "price_target_analysis": _analyze_price_targets(
                    current_price, target_mean_price, target_high_price, target_low_price
                ),
                "summary": consensus.get("summary", "Limited analyst data available"),
                "data_as_of": datetime.now().isoformat()  # Timestamp when data was fetched
            }
            
        except Exception as e:
            return {
                "current_price": None,
                "target_prices": {},
                "recommendation_summary": {},
                "recent_recommendations": {},
                "recent_changes": [],
                "consensus_analysis": {},
                "price_target_analysis": {},
                "summary": f"Unable to retrieve analyst data: {str(e)}"
            }
    
    def _calculate_consensus(current_price: Optional[float], target_mean: Optional[float],
                           target_high: Optional[float], target_low: Optional[float],
                           target_median: Optional[float], rec_mean: Optional[float],
                           rec_key: str, recent_recs: List[Dict]) -> Dict[str, Any]:
        """Calculate consensus analysis from available data"""
        
        analysis = {}
        
        # Price target consensus
        if current_price and target_mean:
            upside_downside = ((target_mean - current_price) / current_price) * 100
            analysis["implied_return"] = upside_downside
            
            if upside_downside > 20:
                analysis["price_sentiment"] = "Very Bullish"
            elif upside_downside > 10:
                analysis["price_sentiment"] = "Bullish"
            elif upside_downside > 0:
                analysis["price_sentiment"] = "Slightly Bullish"
            elif upside_downside > -10:
                analysis["price_sentiment"] = "Neutral"
            else:
                analysis["price_sentiment"] = "Bearish"
        
        # Price target dispersion (measure of analyst agreement)
        if target_high and target_low and target_mean:
            dispersion = ((target_high - target_low) / target_mean) * 100
            analysis["target_dispersion"] = dispersion
            
            if dispersion < 20:
                analysis["analyst_agreement"] = "High"
            elif dispersion < 40:
                analysis["analyst_agreement"] = "Moderate"
            else:
                analysis["analyst_agreement"] = "Low"
        
        # Recommendation distribution analysis
        if recent_recs:
            latest_rec = recent_recs[-1]
            total_analysts = sum([
                latest_rec.get("strongBuy", 0),
                latest_rec.get("buy", 0),
                latest_rec.get("hold", 0),
                latest_rec.get("sell", 0),
                latest_rec.get("strongSell", 0)
            ])
            
            if total_analysts > 0:
                buy_percentage = ((latest_rec.get("strongBuy", 0) + latest_rec.get("buy", 0)) / total_analysts) * 100
                hold_percentage = (latest_rec.get("hold", 0) / total_analysts) * 100
                sell_percentage = ((latest_rec.get("sell", 0) + latest_rec.get("strongSell", 0)) / total_analysts) * 100
                
                analysis["recommendation_distribution"] = {
                    "buy_percentage": buy_percentage,
                    "hold_percentage": hold_percentage,
                    "sell_percentage": sell_percentage,
                    "total_analysts": total_analysts
                }
        
        # Generate summary
        summary_parts = []
        
        if analysis.get("price_sentiment"):
            summary_parts.append(f"Price sentiment: {analysis['price_sentiment']}")
        
        if analysis.get("implied_return"):
            summary_parts.append(f"Implied return: {analysis['implied_return']:.1f}%")
        
        if analysis.get("analyst_agreement"):
            summary_parts.append(f"Analyst agreement: {analysis['analyst_agreement']}")
        
        if rec_key:
            summary_parts.append(f"Consensus: {rec_key.title()}")
        
        analysis["summary"] = "; ".join(summary_parts) if summary_parts else "Limited consensus data available"
        
        return analysis
    
    def _analyze_price_targets(current_price: Optional[float], target_mean: Optional[float],
                              target_high: Optional[float], target_low: Optional[float]) -> Dict[str, Any]:
        """Analyze price target metrics"""
        
        if not current_price:
            return {"analysis": "Current price not available"}
        
        analysis = {}
        
        if target_mean:
            upside = ((target_mean - current_price) / current_price) * 100
            analysis["mean_target_upside"] = upside
            
        if target_high:
            max_upside = ((target_high - current_price) / current_price) * 100
            analysis["max_upside"] = max_upside
            
        if target_low:
            min_upside = ((target_low - current_price) / current_price) * 100
            analysis["downside_risk"] = min_upside
        
        # Risk-reward assessment
        if target_high and target_low and current_price:
            upside_potential = target_high - current_price
            downside_risk = current_price - target_low
            
            if downside_risk > 0:
                risk_reward_ratio = upside_potential / downside_risk
                analysis["risk_reward_ratio"] = risk_reward_ratio
                
                if risk_reward_ratio > 3:
                    analysis["risk_assessment"] = "Favorable risk-reward"
                elif risk_reward_ratio > 1.5:
                    analysis["risk_assessment"] = "Balanced risk-reward"
                else:
                    analysis["risk_assessment"] = "Limited upside vs risk"
        
        return analysis

    return await asyncio.to_thread(_fetch_analyst_data)
