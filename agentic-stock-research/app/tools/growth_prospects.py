from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import asyncio
import yfinance as yf
import pandas as pd
import statistics

from app.tools.finance import fetch_info


async def analyze_growth_prospects(ticker: str) -> Dict[str, Any]:
    """
    Analyze historical growth patterns and future growth prospects.
    Evaluate sector trends, market expansion opportunities, and strategic initiatives.
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

    def _fetch_growth_data() -> Dict[str, Any]:
        try:
            # Get company data
            t = yf.Ticker(ticker)
            info = t.info or {}
            
            # Get financial statements for historical analysis
            try:
                financials = getattr(t, "financials", None)
                quarterly_financials = getattr(t, "quarterly_financials", None)
            except Exception:
                financials = None
                quarterly_financials = None
            
            # Current metrics
            sector = info.get("sector", "Unknown")
            industry = info.get("industry", "Unknown")
            market_cap = _safe_float(info.get("marketCap"))
            
            # Historical Growth Analysis
            historical_growth = _analyze_historical_growth(financials, quarterly_financials, info)
            
            # Sector and Market Analysis
            sector_analysis = _analyze_sector_trends(sector, industry, info)
            
            # Strategic Analysis
            strategic_analysis = _analyze_strategic_factors(info)
            
            # Growth Prospects by Timeline
            growth_prospects = _assess_growth_prospects(
                historical_growth, sector_analysis, strategic_analysis, info
            )
            
            return {
                "historical_growth": historical_growth,
                "sector_analysis": sector_analysis,
                "strategic_factors": strategic_analysis,
                "growth_outlook": growth_prospects,
                "summary": growth_prospects.get("summary", "Growth analysis completed")
            }
            
        except Exception as e:
            return {
                "historical_growth": {},
                "sector_analysis": {},
                "strategic_factors": {},
                "growth_outlook": {},
                "summary": f"Growth analysis failed: {str(e)}"
            }
    
    def _analyze_historical_growth(financials: Optional[pd.DataFrame], 
                                  quarterly: Optional[pd.DataFrame], 
                                  info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze historical revenue and earnings growth patterns"""
        
        growth_metrics = {}
        
        # Get growth rates from info (trailing)
        revenue_growth = _safe_float(info.get("revenueGrowth"))
        earnings_growth = _safe_float(info.get("earningsGrowth"))
        
        if revenue_growth is not None:
            growth_metrics["revenue_growth_ttm"] = revenue_growth
        if earnings_growth is not None:
            growth_metrics["earnings_growth_ttm"] = earnings_growth
        
        # Calculate multi-year CAGR from financial statements
        if financials is not None and not financials.empty:
            revenue_cagr = _calculate_cagr(financials, "Total Revenue")
            if revenue_cagr:
                growth_metrics["revenue_cagr_3y"] = revenue_cagr.get("3year")
                growth_metrics["revenue_cagr_5y"] = revenue_cagr.get("5year")
        
        # Quarterly growth trends (if available)
        if quarterly is not None and not quarterly.empty:
            quarterly_trends = _analyze_quarterly_trends(quarterly)
            growth_metrics["quarterly_trends"] = quarterly_trends
        
        # Growth consistency analysis
        growth_quality = _assess_growth_quality(growth_metrics)
        
        return {
            "metrics": growth_metrics,
            "quality_assessment": growth_quality,
            "trend": growth_quality.get("overall_trend", "Unknown")
        }
    
    def _calculate_cagr(df: pd.DataFrame, metric: str) -> Optional[Dict[str, float]]:
        """Calculate Compound Annual Growth Rate for a metric"""
        try:
            if metric not in df.index:
                return None
            
            series = df.loc[metric].dropna()
            if len(series) < 2:
                return None
            
            # Sort by date (oldest first)
            series = series.sort_index()
            
            cagrs = {}
            current_value = float(series.iloc[-1])
            
            # 3-year CAGR
            if len(series) >= 3:
                three_year_value = float(series.iloc[-3])
                if three_year_value > 0:
                    cagr_3y = (current_value / three_year_value) ** (1/2) - 1
                    cagrs["3year"] = cagr_3y
            
            # 5-year CAGR
            if len(series) >= 5:
                five_year_value = float(series.iloc[-5])
                if five_year_value > 0:
                    cagr_5y = (current_value / five_year_value) ** (1/4) - 1
                    cagrs["5year"] = cagr_5y
            
            return cagrs if cagrs else None
            
        except Exception:
            return None
    
    def _analyze_quarterly_trends(quarterly_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze recent quarterly growth trends"""
        try:
            if "Total Revenue" in quarterly_df.index:
                revenue_series = quarterly_df.loc["Total Revenue"].dropna()
                if len(revenue_series) >= 4:
                    # Calculate quarter-over-quarter growth
                    qoq_growth = []
                    for i in range(1, len(revenue_series)):
                        if revenue_series.iloc[i-1] != 0:
                            qoq = (revenue_series.iloc[i] / revenue_series.iloc[i-1]) - 1
                            qoq_growth.append(qoq)
                    
                    if qoq_growth:
                        avg_qoq = statistics.mean(qoq_growth[-4:])  # Last 4 quarters
                        trend = "Accelerating" if qoq_growth[-1] > avg_qoq else "Decelerating"
                        
                        return {
                            "avg_qoq_growth": avg_qoq,
                            "latest_qoq": qoq_growth[-1] if qoq_growth else None,
                            "trend": trend,
                            "consistency": "High" if all(g > -0.05 for g in qoq_growth[-4:]) else "Variable"
                        }
            
            return {"note": "Insufficient quarterly data"}
            
        except Exception:
            return {"note": "Quarterly analysis failed"}
    
    def _assess_growth_quality(metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the quality and sustainability of growth"""
        
        quality_factors = {}
        
        # Revenue vs Earnings Growth Balance
        rev_growth = metrics.get("revenue_growth_ttm")
        earn_growth = metrics.get("earnings_growth_ttm")
        
        if rev_growth is not None and earn_growth is not None:
            if rev_growth > 0 and earn_growth > rev_growth:
                quality_factors["profitability_trend"] = "Improving margins"
            elif rev_growth > 0 and earn_growth < rev_growth:
                quality_factors["profitability_trend"] = "Margin pressure"
            else:
                quality_factors["profitability_trend"] = "Mixed signals"
        
        # Growth Consistency
        rev_cagr_3y = metrics.get("revenue_cagr_3y")
        rev_cagr_5y = metrics.get("revenue_cagr_5y")
        
        if rev_cagr_3y is not None and rev_cagr_5y is not None:
            if abs(rev_cagr_3y - rev_cagr_5y) < 0.03:  # Within 3%
                quality_factors["consistency"] = "High"
            else:
                quality_factors["consistency"] = "Variable"
        
        # Overall Trend Assessment
        if rev_growth and rev_growth > 0.05:  # 5%+ growth
            if quality_factors.get("consistency") == "High":
                overall_trend = "Strong & Consistent"
            else:
                overall_trend = "Strong but Variable"
        elif rev_growth and rev_growth > 0:
            overall_trend = "Modest Growth"
        else:
            overall_trend = "Declining or Stagnant"
        
        quality_factors["overall_trend"] = overall_trend
        
        return quality_factors
    
    def _analyze_sector_trends(sector: str, industry: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sector-specific growth drivers and trends"""
        
        # Sector growth characteristics
        sector_profiles = {
            "Technology": {
                "growth_drivers": ["Digital transformation", "Cloud adoption", "AI/ML", "IoT"],
                "outlook": "Strong",
                "key_metrics": ["R&D spending", "Patent filings", "User growth"],
                "cyclicality": "Low",
                "disruption_risk": "High"
            },
            "Healthcare": {
                "growth_drivers": ["Aging population", "Medical innovation", "Emerging markets"],
                "outlook": "Stable",
                "key_metrics": ["Pipeline drugs", "Regulatory approvals", "Market access"],
                "cyclicality": "Low",
                "disruption_risk": "Medium"
            },
            "Financial Services": {
                "growth_drivers": ["Economic growth", "Interest rates", "Digital banking"],
                "outlook": "Moderate",
                "key_metrics": ["Loan growth", "Net interest margin", "Fee income"],
                "cyclicality": "High",
                "disruption_risk": "Medium"
            },
            "Consumer Cyclical": {
                "growth_drivers": ["Consumer spending", "Economic growth", "Demographics"],
                "outlook": "Variable",
                "key_metrics": ["Same-store sales", "Market share", "Margin expansion"],
                "cyclicality": "High",
                "disruption_risk": "Medium"
            },
            "Energy": {
                "growth_drivers": ["Commodity prices", "Energy transition", "Global demand"],
                "outlook": "Volatile",
                "key_metrics": ["Production growth", "Cost efficiency", "ESG initiatives"],
                "cyclicality": "Very High",
                "disruption_risk": "High"
            }
        }
        
        sector_data = sector_profiles.get(sector, {
            "growth_drivers": ["Market expansion", "Operational efficiency"],
            "outlook": "Mixed",
            "key_metrics": ["Revenue growth", "Market share"],
            "cyclicality": "Medium",
            "disruption_risk": "Medium"
        })
        
        # Add company-specific factors
        market_cap = _safe_float(info.get("marketCap"))
        if market_cap:
            if market_cap > 100e9:  # >$100B
                sector_data["size_advantage"] = "Large scale benefits"
            elif market_cap > 10e9:  # >$10B
                sector_data["size_advantage"] = "Mid-scale positioning"
            else:
                sector_data["size_advantage"] = "Agility advantage"
        
        return {
            "sector": sector,
            "industry": industry,
            "sector_outlook": sector_data.get("outlook"),
            "growth_drivers": sector_data.get("growth_drivers", []),
            "key_metrics": sector_data.get("key_metrics", []),
            "cyclicality": sector_data.get("cyclicality"),
            "disruption_risk": sector_data.get("disruption_risk"),
            "competitive_position": sector_data.get("size_advantage", "Unknown")
        }
    
    def _analyze_strategic_factors(info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze strategic factors affecting growth prospects"""
        
        strategic_factors = {}
        
        # R&D Investment (for applicable sectors)
        revenue = _safe_float(info.get("totalRevenue"))
        if revenue:
            # R&D intensity (if available)
            # Note: yfinance doesn't always provide R&D data directly
            strategic_factors["revenue_base"] = revenue
        
        # Geographic diversification (simplified)
        country = info.get("country", "Unknown")
        if country and country != "United States":
            strategic_factors["geographic_exposure"] = "International"
        else:
            strategic_factors["geographic_exposure"] = "Primarily domestic"
        
        # Business model assessment
        business_summary = info.get("businessSummary", "")
        if business_summary:
            # Look for recurring revenue indicators
            recurring_indicators = ["subscription", "recurring", "saas", "license", "contract"]
            if any(indicator in business_summary.lower() for indicator in recurring_indicators):
                strategic_factors["revenue_model"] = "Recurring revenue elements"
            else:
                strategic_factors["revenue_model"] = "Transaction-based"
            
            # Innovation indicators
            innovation_indicators = ["innovation", "technology", "research", "development", "patent"]
            innovation_score = sum(1 for indicator in innovation_indicators if indicator in business_summary.lower())
            strategic_factors["innovation_focus"] = "High" if innovation_score >= 3 else "Medium" if innovation_score >= 1 else "Low"
        
        # Financial flexibility
        debt_to_equity = _safe_float(info.get("debtToEquity"))
        current_ratio = _safe_float(info.get("currentRatio"))
        
        if debt_to_equity is not None and current_ratio is not None:
            if debt_to_equity < 0.5 and current_ratio > 1.2:
                strategic_factors["financial_flexibility"] = "High"
            elif debt_to_equity < 1.0 and current_ratio > 1.0:
                strategic_factors["financial_flexibility"] = "Medium"
            else:
                strategic_factors["financial_flexibility"] = "Constrained"
        
        return strategic_factors
    
    def _assess_growth_prospects(historical: Dict[str, Any], sector: Dict[str, Any], 
                               strategic: Dict[str, Any], info: Dict[str, Any]) -> Dict[str, Any]:
        """Assess growth prospects by timeline (1, 3, 5+ years)"""
        
        prospects = {}
        
        # Base growth rate from historical performance
        base_growth = historical.get("metrics", {}).get("revenue_growth_ttm", 0.05)
        
        # Sector adjustment
        sector_outlook = sector.get("sector_outlook", "Mixed")
        if sector_outlook == "Strong":
            sector_multiplier = 1.2
        elif sector_outlook == "Stable":
            sector_multiplier = 1.0
        elif sector_outlook == "Moderate":
            sector_multiplier = 0.9
        else:
            sector_multiplier = 0.8
        
        # Strategic adjustment
        innovation_focus = strategic.get("innovation_focus", "Medium")
        financial_flexibility = strategic.get("financial_flexibility", "Medium")
        
        strategic_boost = 0
        if innovation_focus == "High":
            strategic_boost += 0.02
        if financial_flexibility == "High":
            strategic_boost += 0.01
        
        # Timeline-specific projections
        prospects["short_term"] = {
            "period": "1 year",
            "revenue_growth_estimate": max(0, min(0.15, base_growth * 0.9)),  # Slightly conservative
            "key_factors": ["Current momentum", "Near-term market conditions"],
            "confidence": "Medium" if abs(base_growth) < 0.1 else "Low"
        }
        
        prospects["medium_term"] = {
            "period": "3 years",
            "revenue_growth_estimate": max(0, min(0.12, (base_growth * sector_multiplier) + strategic_boost)),
            "key_factors": sector.get("growth_drivers", [])[:3],
            "confidence": "Medium"
        }
        
        prospects["long_term"] = {
            "period": "5+ years",
            "revenue_growth_estimate": max(0, min(0.10, (base_growth * sector_multiplier * 0.8) + strategic_boost)),
            "key_factors": ["Industry evolution", "Competitive positioning", "Innovation capacity"],
            "confidence": "Low"
        }
        
        # Overall assessment
        avg_growth = statistics.mean([
            prospects["short_term"]["revenue_growth_estimate"],
            prospects["medium_term"]["revenue_growth_estimate"],
            prospects["long_term"]["revenue_growth_estimate"]
        ])
        
        if avg_growth > 0.08:
            overall_outlook = "Strong Growth Expected"
        elif avg_growth > 0.05:
            overall_outlook = "Moderate Growth Expected"
        elif avg_growth > 0.02:
            overall_outlook = "Slow Growth Expected"
        else:
            overall_outlook = "Limited Growth Expected"
        
        prospects["overall_outlook"] = overall_outlook
        prospects["summary"] = f"{overall_outlook}. Key drivers: {', '.join(sector.get('growth_drivers', [])[:2])}"
        
        return prospects

    return await asyncio.to_thread(_fetch_growth_data)
