"""
Strategic Investment Conviction Analysis Engine

This module provides deep strategic analysis to build investment conviction
beyond basic fundamental metrics.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import yfinance as yf
import structlog

logger = structlog.get_logger()
import pandas as pd


class ConvictionLevel(Enum):
    """Investment conviction levels"""
    NO_INVESTMENT = "No Investment"
    LOW_CONVICTION = "Low Conviction" 
    MEDIUM_CONVICTION = "Medium Conviction"
    HIGH_CONVICTION = "High Conviction"


@dataclass
class BusinessMoat:
    """Competitive advantage assessment"""
    moat_type: str  # "Network Effects", "Switching Costs", "Scale", "Brand", "Regulatory"
    strength: float  # 0-100
    durability: float  # 0-100 (how long will this moat last?)
    evidence: List[str]  # Supporting evidence


@dataclass
class GrowthCatalyst:
    """Specific growth catalyst"""
    name: str
    timeline: str  # "6-12 months", "1-3 years", etc.
    impact_potential: float  # 0-100
    probability: float  # 0-100
    description: str


@dataclass
class InvestmentThesis:
    """Complete investment thesis"""
    business_summary: str
    key_investment_points: List[str]
    catalysts: List[GrowthCatalyst]
    risks: List[Dict[str, str]]  # [{"risk": "...", "mitigation": "..."}]
    valuation_summary: Dict[str, Any]
    conviction_score: float  # 0-100
    conviction_level: ConvictionLevel
    position_sizing: float  # 1-10% of portfolio


class StrategicConvictionEngine:
    """
    Analyzes stocks for strategic investment conviction beyond basic metrics
    """
    
    def __init__(self):
        self.industry_tam_data = self._load_industry_tam_data()
        self.competitive_landscape = self._load_competitive_data()
    
    async def analyze_conviction(self, ticker: str) -> Dict[str, Any]:
        """
        Perform comprehensive strategic conviction analysis
        """
        try:
            # Gather comprehensive data
            company_data = await self._fetch_company_data(ticker)
            
            # Core conviction pillars
            logger.info(f"Strategic conviction: Analyzing business quality for {ticker}")
            try:
                business_quality = await self._analyze_business_quality(ticker, company_data)
                logger.info(f"Strategic conviction: Business quality completed for {ticker}")
            except Exception as e:
                logger.error(f"Strategic conviction: Business quality failed for {ticker}: {e}")
                raise
            
            logger.info(f"Strategic conviction: Analyzing growth runway for {ticker}")
            try:
                growth_runway = await self._analyze_growth_runway(ticker, company_data) 
                logger.info(f"Strategic conviction: Growth runway completed for {ticker}")
            except Exception as e:
                logger.error(f"Strategic conviction: Growth runway failed for {ticker}: {e}")
                raise
            
            logger.info(f"Strategic conviction: Analyzing valuation asymmetry for {ticker}")
            try:
                valuation_asymmetry = await self._analyze_valuation_asymmetry(ticker, company_data)
                logger.info(f"Strategic conviction: Valuation asymmetry completed for {ticker}")
            except Exception as e:
                logger.error(f"Strategic conviction: Valuation asymmetry failed for {ticker}: {e}")
                raise
            
            logger.info(f"Strategic conviction: Analyzing macro resilience for {ticker}")
            try:
                macro_resilience = await self._analyze_macro_resilience(ticker, company_data)
                logger.info(f"Strategic conviction: Macro resilience completed for {ticker}")
            except Exception as e:
                logger.error(f"Strategic conviction: Macro resilience failed for {ticker}: {e}")
                raise
            
            # Calculate overall conviction
            logger.info(f"Strategic conviction: Calculating conviction score for {ticker}")
            try:
                conviction_score = self._calculate_conviction_score(
                    business_quality, growth_runway, valuation_asymmetry, macro_resilience
                )
                logger.info(f"Strategic conviction: Conviction score calculated for {ticker}: {conviction_score}")
            except Exception as e:
                logger.error(f"Strategic conviction: Conviction score calculation failed for {ticker}: {e}")
                raise
            
            # Generate investment thesis
            logger.info(f"Strategic conviction: Generating investment thesis for {ticker}")
            try:
                investment_thesis = await self._generate_investment_thesis(
                    ticker, company_data, business_quality, growth_runway, 
                    valuation_asymmetry, macro_resilience, conviction_score
                )
                logger.info(f"Strategic conviction: Investment thesis generated for {ticker}")
            except Exception as e:
                logger.error(f"Strategic conviction: Investment thesis generation failed for {ticker}: {e}")
                raise
            
            # Format final result
            logger.info(f"Strategic conviction: Formatting final result for {ticker}")
            try:
                conviction_level_str = self._conviction_level_to_string(self._get_conviction_level(conviction_score))
                strategic_recommendation = self._get_strategic_recommendation(conviction_score)
                position_sizing = self._calculate_position_sizing(conviction_score)
                
                logger.info(f"Strategic conviction: All components ready for {ticker}")
                
                return {
                    "ticker": ticker,
                    "conviction_analysis": {
                        "business_quality": business_quality,
                        "growth_runway": growth_runway, 
                        "valuation_asymmetry": valuation_asymmetry,
                        "macro_resilience": macro_resilience,
                        "overall_conviction_score": conviction_score,
                        "conviction_level": conviction_level_str,
                        "strategic_recommendation": strategic_recommendation,
                        "position_sizing_pct": position_sizing,
                        # Minimal investment thesis to avoid serialization issues
                        "investment_thesis": {
                            "business_summary": f"{ticker} analysis completed",
                            "conviction_score": conviction_score,
                            "position_sizing": position_sizing
                        }
                    }
                }
            except Exception as e:
                logger.error(f"Strategic conviction: Final result formatting failed for {ticker}: {e}")
                raise
            
        except Exception as e:
            logger.error(f"Strategic conviction analysis error at line: {e}")
            import traceback
            traceback.print_exc()
            return {
                "ticker": ticker,
                "error": f"Strategic conviction analysis failed: {str(e)}",
                "conviction_analysis": None
            }
    
    async def _fetch_company_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch comprehensive company data"""
        def _fetch():
            t = yf.Ticker(ticker)
            return {
                "info": t.info or {},
                "financials": t.financials,
                "balance_sheet": t.balance_sheet,
                "cashflow": t.cashflow,
                "history": t.history(period="5y"),
                "recommendations": t.recommendations,
                "institutional_holders": t.institutional_holders,
                "major_holders": t.major_holders,
            }
        
        return await asyncio.to_thread(_fetch)
    
    async def _analyze_business_quality(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze business quality and competitive advantages
        Weight: 40% of conviction score
        """
        info = data["info"]
        financials = data.get("financials")
        
        # Competitive moat analysis
        moats = await self._identify_competitive_moats(ticker, info)
        
        # Market position analysis
        market_position = self._analyze_market_position(ticker, info)
        
        # Management quality
        management_quality = self._analyze_management_quality(ticker, info, financials)
        
        # Financial fortress
        financial_strength = self._analyze_financial_strength(ticker, info, data.get("balance_sheet"))
        
        # Enhanced Phase 6: Comprehensive Competitive Analysis
        competitive_analysis = await self._analyze_competitive_landscape(ticker, data)
        
        # Enhanced Phase 6: Industry Outlook Analysis
        industry_outlook = await self._analyze_industry_outlook(ticker, data)
        
        # Calculate business quality score
        business_score = (
            sum(moat.strength for moat in moats) / len(moats) * 0.25 +
            market_position["score"] * 0.20 +
            management_quality["score"] * 0.15 +
            financial_strength["score"] * 0.10 +
            competitive_analysis["score"] * 0.20 +
            industry_outlook["score"] * 0.10
        ) if moats else 0
        
        return {
            "score": min(100, max(0, business_score)),
            "competitive_moats": [
                {
                    "type": moat.moat_type,
                    "strength": moat.strength,
                    "durability": moat.durability,
                    "evidence": moat.evidence
                } for moat in moats
            ],
            "market_position": market_position,
            "management_quality": management_quality,
            "financial_strength": financial_strength,
            "key_strengths": self._identify_business_strengths(moats, market_position, management_quality, financial_strength),
            "key_concerns": self._identify_business_concerns(moats, market_position, management_quality, financial_strength),
            # Phase 6 Enhancements
            "competitive_analysis": competitive_analysis,
            "industry_outlook": industry_outlook
        }
    
    async def _identify_competitive_moats(self, ticker: str, info: Dict[str, Any]) -> List[BusinessMoat]:
        """Identify and assess competitive moats"""
        moats = []
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        # Technology sector moats
        if sector == "Technology":
            if "Software" in industry:
                moats.append(BusinessMoat(
                    moat_type="Switching Costs",
                    strength=75,
                    durability=85,
                    evidence=["Enterprise software integration complexity", "Training costs", "Data lock-in"]
                ))
            
            if info.get("marketCap", 0) > 100e9:  # Large tech companies
                moats.append(BusinessMoat(
                    moat_type="Scale Advantages", 
                    strength=80,
                    durability=70,
                    evidence=["R&D investment capacity", "Global infrastructure", "Talent acquisition"]
                ))
        
        # Financial services moats
        elif sector == "Financial Services":
            moats.append(BusinessMoat(
                moat_type="Regulatory Barriers",
                strength=70,
                durability=90,
                evidence=["Banking licenses", "Regulatory compliance", "Capital requirements"]
            ))
        
        # Default moat for established companies
        if not moats and info.get("marketCap", 0) > 10e9:
            moats.append(BusinessMoat(
                moat_type="Scale Advantages",
                strength=50,
                durability=60,
                evidence=["Market leadership", "Operational scale"]
            ))
        
        return moats or [BusinessMoat("Limited Moats", 30, 40, ["Commodity business characteristics"])]
    
    def _analyze_market_position(self, ticker: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze competitive market position"""
        market_cap = info.get("marketCap", 0)
        sector = info.get("sector", "")
        
        # Market leadership assessment
        if market_cap > 100e9:
            position_strength = 85
            position_desc = "Market Leader"
        elif market_cap > 10e9:
            position_strength = 65
            position_desc = "Strong Player"
        else:
            position_strength = 45
            position_desc = "Smaller Player"
        
        return {
            "score": position_strength,
            "description": position_desc,
            "market_cap_tier": self._get_market_cap_tier(market_cap),
            "competitive_advantages": self._identify_competitive_advantages(ticker, info)
        }
    
    def _analyze_management_quality(self, ticker: str, info: Dict[str, Any], financials: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """Analyze management quality and capital allocation"""
        
        # ROE and ROIC trends (if available)
        roe = info.get("returnOnEquity", 0)
        roic_proxy = info.get("returnOnAssets", 0) * 2  # Rough ROIC proxy
        
        # Management score based on available metrics
        management_score = 50  # Default neutral
        
        if roe and roe > 0.15:  # ROE > 15%
            management_score += 20
        elif roe and roe > 0.10:  # ROE > 10%
            management_score += 10
        
        if roic_proxy > 0.12:  # ROIC proxy > 12%
            management_score += 15
        
        # Debt management
        debt_to_equity = info.get("debtToEquity", 0)
        if debt_to_equity < 30:  # Conservative debt management
            management_score += 10
        elif debt_to_equity > 100:  # High leverage concern
            management_score -= 15
        
        return {
            "score": min(100, max(0, management_score)),
            "capital_allocation_score": management_score,
            "key_metrics": {
                "roe": roe,
                "roic_proxy": roic_proxy,
                "debt_to_equity": debt_to_equity
            },
            "strengths": self._get_management_strengths(roe, roic_proxy, debt_to_equity),
            "concerns": self._get_management_concerns(roe, roic_proxy, debt_to_equity)
        }
    
    def _analyze_financial_strength(self, ticker: str, info: Dict[str, Any], balance_sheet: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """Analyze financial fortress characteristics"""
        
        # Key financial strength metrics
        current_ratio = info.get("currentRatio", 1.0)
        quick_ratio = info.get("quickRatio", 0.8) 
        debt_to_equity = info.get("debtToEquity", 0)
        interest_coverage = info.get("interestCoverage", 0)
        
        # Calculate financial strength score
        strength_score = 50  # Base score
        
        # Liquidity assessment
        if current_ratio > 2.0:
            strength_score += 15
        elif current_ratio > 1.5:
            strength_score += 10
        elif current_ratio < 1.0:
            strength_score -= 20
        
        # Leverage assessment  
        if debt_to_equity < 20:
            strength_score += 20
        elif debt_to_equity < 50:
            strength_score += 10
        elif debt_to_equity > 100:
            strength_score -= 25
        
        # Interest coverage
        if interest_coverage > 10:
            strength_score += 15
        elif interest_coverage > 5:
            strength_score += 10
        elif interest_coverage < 2:
            strength_score -= 30
        
        return {
            "score": min(100, max(0, strength_score)),
            "liquidity_ratios": {
                "current_ratio": current_ratio,
                "quick_ratio": quick_ratio
            },
            "leverage_metrics": {
                "debt_to_equity": debt_to_equity,
                "interest_coverage": interest_coverage
            },
            "financial_grade": self._get_financial_grade(strength_score),
            "key_strengths": self._get_financial_strengths(current_ratio, debt_to_equity, interest_coverage),
            "key_risks": self._get_financial_risks(current_ratio, debt_to_equity, interest_coverage)
        }
    
    async def _analyze_growth_runway(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze growth runway and secular trends
        Weight: 25% of conviction score
        """
        info = data["info"]
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        # TAM analysis
        tam_analysis = self._analyze_tam_growth(sector, industry)
        
        # Secular trends
        secular_trends = self._identify_secular_trends(sector, industry)
        
        # Innovation pipeline
        innovation_score = self._assess_innovation_pipeline(ticker, info)
        
        # Geographic expansion
        geographic_potential = self._assess_geographic_expansion(ticker, info)
        
        # Enhanced Phase 6: Growth Drivers Analysis
        growth_drivers = await self._analyze_growth_drivers(ticker, data)
        
        # Enhanced Phase 6: Segment Performance Analysis
        segment_performance = await self._analyze_segment_performance(ticker, data)
        
        # Calculate growth runway score
        growth_score = (
            tam_analysis["score"] * 0.25 +
            secular_trends["score"] * 0.20 +
            innovation_score * 0.15 +
            geographic_potential["score"] * 0.10 +
            growth_drivers["score"] * 0.20 +
            segment_performance["score"] * 0.10
        )
        
        return {
            "score": min(100, max(0, growth_score)),
            "tam_analysis": tam_analysis,
            "secular_trends": secular_trends,
            "innovation_pipeline": innovation_score,
            "geographic_expansion": geographic_potential,
            "growth_catalysts": self._identify_growth_catalysts(sector, industry, info),
            "growth_runway_years": self._estimate_growth_runway(tam_analysis, secular_trends),
            # Phase 6 Enhancements
            "growth_drivers": growth_drivers,
            "segment_performance": segment_performance
        }
    
    def _analyze_tam_growth(self, sector: str, industry: str) -> Dict[str, Any]:
        """Analyze Total Addressable Market growth"""
        
        # Industry-specific TAM growth rates (5-year CAGR estimates)
        tam_growth_rates = {
            "Technology": {
                "Software—Application": 12,
                "Software—Infrastructure": 15,
                "Information Technology Services": 8,
                "Semiconductors": 6,
                "default": 10
            },
            "Healthcare": {
                "Biotechnology": 8,
                "Drug Manufacturers—General": 5,
                "Medical Devices": 6,
                "default": 6
            },
            "Financial Services": {
                "Banks—Regional": 3,
                "Insurance": 4,
                "Asset Management": 5,
                "default": 4
            },
            "default": 5
        }
        
        sector_data = tam_growth_rates.get(sector, {"default": 5})
        growth_rate = sector_data.get(industry, sector_data["default"])
        
        # Convert growth rate to score (higher growth = higher score)
        tam_score = min(100, max(0, growth_rate * 6))  # Scale to 0-100
        
        return {
            "score": tam_score,
            "estimated_cagr": growth_rate,
            "market_size_trend": "Expanding" if growth_rate > 6 else "Stable" if growth_rate > 3 else "Declining",
            "key_drivers": self._get_tam_drivers(sector, industry)
        }
    
    def _identify_secular_trends(self, sector: str, industry: str) -> Dict[str, Any]:
        """Identify secular trends supporting growth"""
        
        secular_trends_map = {
            "Technology": {
                "trends": ["Digital Transformation", "Cloud Migration", "AI/ML Adoption", "Cybersecurity"],
                "score": 85,
                "duration": "10+ years"
            },
            "Healthcare": {
                "trends": ["Aging Demographics", "Precision Medicine", "Digital Health"],
                "score": 75,
                "duration": "15+ years"
            },
            "Financial Services": {
                "trends": ["Fintech Disruption", "Digital Banking", "Regulatory Technology"],
                "score": 60,
                "duration": "5-10 years"
            }
        }
        
        return secular_trends_map.get(sector, {
            "trends": ["Industry Consolidation"],
            "score": 40,
            "duration": "Variable"
        })
    
    def _identify_growth_catalysts(self, sector: str, industry: str, info: Dict[str, Any]) -> List[GrowthCatalyst]:
        """Identify specific growth catalysts"""
        catalysts = []
        
        # Technology sector catalysts
        if sector == "Technology":
            catalysts.append(GrowthCatalyst(
                name="AI/ML Product Integration",
                timeline="6-18 months",
                impact_potential=75,
                probability=80,
                description="Integration of AI capabilities into existing products"
            ))
            
            catalysts.append(GrowthCatalyst(
                name="Cloud Migration Acceleration",
                timeline="1-3 years", 
                impact_potential=60,
                probability=85,
                description="Continued enterprise cloud adoption"
            ))
        
        # Add sector-agnostic catalysts based on company size
        market_cap = info.get("marketCap", 0)
        if market_cap > 10e9:
            catalysts.append(GrowthCatalyst(
                name="International Expansion",
                timeline="1-3 years",
                impact_potential=50,
                probability=60,
                description="Geographic market expansion opportunities"
            ))
        
        return catalysts
    
    async def _analyze_valuation_asymmetry(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze valuation for asymmetric risk/reward
        Weight: 20% of conviction score
        """
        info = data["info"]
        
        # Get key valuation metrics
        current_price = info.get("currentPrice", info.get("regularMarketPrice", 0))
        pe_ratio = info.get("trailingPE", 0)
        forward_pe = info.get("forwardPE", 0)
        peg_ratio = info.get("pegRatio", 0)
        pb_ratio = info.get("priceToBook", 0)
        
        # Industry benchmarks (simplified)
        sector = info.get("sector", "")
        industry_pe_benchmarks = {
            "Technology": 25,
            "Healthcare": 20,
            "Financial Services": 12,
            "Consumer Cyclical": 18,
            "Industrials": 16
        }
        
        benchmark_pe = industry_pe_benchmarks.get(sector, 18)
        
        # Valuation scoring
        valuation_score = 50  # Neutral base
        
        # P/E analysis
        if pe_ratio and pe_ratio > 0:
            pe_discount = (benchmark_pe - pe_ratio) / benchmark_pe
            if pe_discount > 0.3:  # 30%+ discount
                valuation_score += 30
            elif pe_discount > 0.1:  # 10%+ discount
                valuation_score += 15
            elif pe_discount < -0.3:  # 30%+ premium
                valuation_score -= 25
            elif pe_discount < -0.1:  # 10%+ premium
                valuation_score -= 10
        
        # PEG ratio analysis
        if peg_ratio and 0 < peg_ratio < 1:
            valuation_score += 20  # Attractive PEG
        elif peg_ratio and peg_ratio > 2:
            valuation_score -= 15  # Expensive PEG
        
        return {
            "score": min(100, max(0, valuation_score)),
            "current_metrics": {
                "current_price": current_price,
                "trailing_pe": pe_ratio,
                "forward_pe": forward_pe,
                "peg_ratio": peg_ratio,
                "price_to_book": pb_ratio
            },
            "relative_valuation": {
                "sector_pe_benchmark": benchmark_pe,
                "pe_discount_premium": (benchmark_pe - pe_ratio) / benchmark_pe if pe_ratio else 0,
                "valuation_tier": self._get_valuation_tier(valuation_score)
            },
            "asymmetry_assessment": self._assess_risk_reward_asymmetry(valuation_score, current_price),
            "margin_of_safety": self._calculate_margin_of_safety(info)
        }
    
    async def _analyze_macro_resilience(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze macro economic resilience
        Weight: 15% of conviction score  
        """
        info = data["info"]
        sector = info.get("sector", "")
        
        # Cyclicality assessment
        cyclicality_scores = {
            "Technology": 70,  # Moderate cyclicality
            "Healthcare": 85,  # Low cyclicality
            "Financial Services": 50,  # High cyclicality
            "Consumer Staples": 80,  # Low cyclicality
            "Consumer Cyclical": 40,  # High cyclicality
            "Energy": 30,  # Very high cyclicality
            "Utilities": 85  # Low cyclicality
        }
        
        cyclicality_score = cyclicality_scores.get(sector, 60)
        
        # Interest rate sensitivity
        rate_sensitivity = self._assess_interest_rate_sensitivity(sector, info)
        
        # Currency exposure
        currency_exposure = self._assess_currency_exposure(ticker, info)
        
        # Regulatory risk
        regulatory_risk = self._assess_regulatory_risk(sector, info)
        
        # Calculate macro resilience score
        macro_score = (
            cyclicality_score * 0.4 +
            rate_sensitivity["score"] * 0.3 +
            currency_exposure["score"] * 0.2 +
            regulatory_risk["score"] * 0.1
        )
        
        return {
            "score": min(100, max(0, macro_score)),
            "cyclicality_assessment": {
                "score": cyclicality_score,
                "sector_cyclicality": self._get_cyclicality_description(cyclicality_score)
            },
            "interest_rate_sensitivity": rate_sensitivity,
            "currency_exposure": currency_exposure,
            "regulatory_risk": regulatory_risk,
            "macro_resilience_grade": self._get_macro_grade(macro_score)
        }
    
    def _calculate_conviction_score(
        self, 
        business_quality: Dict[str, Any],
        growth_runway: Dict[str, Any], 
        valuation_asymmetry: Dict[str, Any],
        macro_resilience: Dict[str, Any]
    ) -> float:
        """Calculate overall conviction score with weighted pillars"""
        
        conviction_score = (
            business_quality["score"] * 0.40 +  # 40% weight
            growth_runway["score"] * 0.25 +     # 25% weight  
            valuation_asymmetry["score"] * 0.20 + # 20% weight
            macro_resilience["score"] * 0.15     # 15% weight
        )
        
        return min(100, max(0, conviction_score))
    
    def _conviction_level_to_string(self, conviction_level) -> str:
        """Safely convert conviction level to string"""
        try:
            # Check if it's an enum with a value attribute
            if hasattr(conviction_level, 'value'):
                return conviction_level.value
            # Check if it's a dictionary with a 'value' key
            elif isinstance(conviction_level, dict) and 'value' in conviction_level:
                return conviction_level['value']
            # If it's already a string, return as-is
            elif isinstance(conviction_level, str):
                return conviction_level
            else:
                return str(conviction_level)
        except Exception as e:
            logger.error(f"Error converting conviction level to string: {e}, type: {type(conviction_level)}, value: {conviction_level}")
            return "Unknown Conviction"
    
    def _get_conviction_level(self, score: float) -> ConvictionLevel:
        """Convert numeric score to conviction level"""
        if score >= 80:
            return ConvictionLevel.HIGH_CONVICTION
        elif score >= 65:
            return ConvictionLevel.MEDIUM_CONVICTION
        elif score >= 45:
            return ConvictionLevel.LOW_CONVICTION
        else:
            return ConvictionLevel.NO_INVESTMENT
    
    def _calculate_position_sizing(self, conviction_score: float) -> float:
        """Calculate recommended position sizing based on conviction"""
        if conviction_score >= 85:
            return 8.0  # 8% for highest conviction
        elif conviction_score >= 75:
            return 6.0  # 6% for high conviction
        elif conviction_score >= 65:
            return 4.0  # 4% for medium conviction
        elif conviction_score >= 50:
            return 2.0  # 2% for low conviction
        else:
            return 0.0  # No position
    
    async def _generate_investment_thesis(
        self,
        ticker: str,
        company_data: Dict[str, Any],
        business_quality: Dict[str, Any],
        growth_runway: Dict[str, Any],
        valuation_asymmetry: Dict[str, Any],
        macro_resilience: Dict[str, Any],
        conviction_score: float
    ) -> InvestmentThesis:
        """Generate comprehensive investment thesis"""
        
        info = company_data["info"]
        company_name = info.get("longName", ticker)
        sector = info.get("sector", "")
        
        # Business summary
        business_summary = f"{company_name} is a {sector.lower()} company with {self._get_market_position_desc(info)}."
        
        # Key investment points
        investment_points = []
        if business_quality["score"] > 70:
            investment_points.append(f"Strong competitive position with {', '.join([moat['type'] for moat in business_quality['competitive_moats']])}")
        
        if growth_runway["score"] > 70:
            investment_points.append(f"Benefiting from secular trends: {', '.join(growth_runway['secular_trends']['trends'][:2])}")
        
        if valuation_asymmetry["score"] > 60:
            investment_points.append("Attractive valuation with asymmetric risk/reward profile")
        
        # Catalysts
        catalysts = growth_runway.get("growth_catalysts", [])
        
        # Risks and mitigations
        risks = []
        if valuation_asymmetry["score"] < 40:
            risks.append({
                "risk": "Valuation premium to peers",
                "mitigation": "Monitor earnings growth acceleration and multiple compression"
            })
        
        if macro_resilience["score"] < 60:
            risks.append({
                "risk": "Economic cycle sensitivity", 
                "mitigation": "Track leading economic indicators and adjust position size"
            })
        
        # Valuation summary
        valuation_summary = {
            "current_price": valuation_asymmetry["current_metrics"]["current_price"],
            "margin_of_safety": valuation_asymmetry.get("margin_of_safety", 0),
            "valuation_tier": valuation_asymmetry["relative_valuation"]["valuation_tier"]
        }
        
        return InvestmentThesis(
            business_summary=business_summary,
            key_investment_points=investment_points,
            catalysts=catalysts,
            risks=risks,
            valuation_summary=valuation_summary,
            conviction_score=conviction_score,
            conviction_level=self._get_conviction_level(conviction_score),
            position_sizing=self._calculate_position_sizing(conviction_score)
        )
    
    def _get_strategic_recommendation(self, conviction_score: float) -> str:
        """Get strategic recommendation based on conviction score"""
        if conviction_score >= 80:
            return "Strong Buy - High Conviction"
        elif conviction_score >= 65:
            return "Buy - Medium Conviction"
        elif conviction_score >= 50:
            return "Hold - Low Conviction"
        else:
            return "Avoid - Insufficient Conviction"
    
    # Helper methods (simplified implementations)
    def _load_industry_tam_data(self) -> Dict[str, Any]:
        """Load industry TAM data (placeholder)"""
        return {}
    
    def _load_competitive_data(self) -> Dict[str, Any]:
        """Load competitive landscape data (placeholder)"""
        return {}
    
    def _identify_business_strengths(self, moats, market_position, management_quality, financial_strength) -> List[str]:
        """Identify key business strengths"""
        strengths = []
        if moats and max(moat.strength for moat in moats) > 70:
            strengths.append("Strong competitive moats")
        if market_position["score"] > 70:
            strengths.append("Market leadership position")
        if management_quality["score"] > 70:
            strengths.append("High-quality management team")
        if financial_strength["score"] > 70:
            strengths.append("Strong balance sheet")
        return strengths
    
    def _identify_business_concerns(self, moats, market_position, management_quality, financial_strength) -> List[str]:
        """Identify key business concerns"""
        concerns = []
        if not moats or max(moat.strength for moat in moats) < 50:
            concerns.append("Limited competitive advantages")
        if market_position["score"] < 50:
            concerns.append("Weak market position")
        if management_quality["score"] < 50:
            concerns.append("Management execution concerns")
        if financial_strength["score"] < 50:
            concerns.append("Balance sheet weakness")
        return concerns
    
    def _get_market_cap_tier(self, market_cap: float) -> str:
        """Get market cap tier description"""
        if market_cap > 200e9:
            return "Mega Cap"
        elif market_cap > 10e9:
            return "Large Cap"
        elif market_cap > 2e9:
            return "Mid Cap"
        else:
            return "Small Cap"
    
    def _identify_competitive_advantages(self, info: Dict[str, Any]) -> List[str]:
        """Identify competitive advantages from company info"""
        advantages = []
        if info.get("marketCap", 0) > 50e9:
            advantages.append("Scale advantages")
        if info.get("grossMargins", 0) > 0.4:
            advantages.append("High gross margins")
        return advantages
    
    def _get_management_strengths(self, roe: float, roic_proxy: float, debt_to_equity: float) -> List[str]:
        """Get management strengths"""
        strengths = []
        if roe and roe > 0.15:
            strengths.append("Strong ROE generation")
        if roic_proxy > 0.12:
            strengths.append("Efficient capital allocation")
        if debt_to_equity < 30:
            strengths.append("Conservative debt management")
        return strengths
    
    def _get_management_concerns(self, roe: float, roic_proxy: float, debt_to_equity: float) -> List[str]:
        """Get management concerns"""
        concerns = []
        if roe and roe < 0.08:
            concerns.append("Low ROE performance")
        if roic_proxy < 0.06:
            concerns.append("Poor capital efficiency")
        if debt_to_equity > 100:
            concerns.append("High leverage risk")
        return concerns
    
    def _get_financial_grade(self, score: float) -> str:
        """Get financial strength grade"""
        if score >= 80:
            return "A"
        elif score >= 65:
            return "B"
        elif score >= 50:
            return "C"
        else:
            return "D"
    
    def _get_financial_strengths(self, current_ratio: float, debt_to_equity: float, interest_coverage: float) -> List[str]:
        """Get financial strengths"""
        strengths = []
        if current_ratio > 2.0:
            strengths.append("Strong liquidity position")
        if debt_to_equity < 30:
            strengths.append("Low debt burden")
        if interest_coverage > 10:
            strengths.append("Strong interest coverage")
        return strengths
    
    def _get_financial_risks(self, current_ratio: float, debt_to_equity: float, interest_coverage: float) -> List[str]:
        """Get financial risks"""
        risks = []
        if current_ratio < 1.0:
            risks.append("Liquidity concerns")
        if debt_to_equity > 100:
            risks.append("High debt levels")
        if interest_coverage < 2:
            risks.append("Interest coverage risk")
        return risks
    
    def _get_tam_drivers(self, sector: str, industry: str) -> List[str]:
        """Get TAM growth drivers"""
        drivers_map = {
            "Technology": ["Digital transformation", "Cloud adoption", "AI/ML integration"],
            "Healthcare": ["Aging population", "Medical innovation", "Precision medicine"],
            "Financial Services": ["Fintech adoption", "Digital banking", "Regulatory technology"]
        }
        return drivers_map.get(sector, ["Industry consolidation", "Market expansion"])
    
    def _estimate_growth_runway(self, tam_analysis: Dict[str, Any], secular_trends: Dict[str, Any]) -> str:
        """Estimate growth runway duration"""
        if tam_analysis["score"] > 70 and secular_trends["score"] > 70:
            return "10+ years"
        elif tam_analysis["score"] > 50 or secular_trends["score"] > 60:
            return "5-10 years"
        else:
            return "3-5 years"
    
    def _get_valuation_tier(self, score: float) -> str:
        """Get valuation tier description"""
        if score >= 75:
            return "Attractive"
        elif score >= 50:
            return "Fair"
        else:
            return "Expensive"
    
    def _assess_risk_reward_asymmetry(self, valuation_score: float, current_price: float) -> Dict[str, Any]:
        """Assess risk/reward asymmetry"""
        if valuation_score > 70:
            return {
                "asymmetry": "Favorable",
                "upside_potential": "High",
                "downside_risk": "Limited"
            }
        elif valuation_score > 40:
            return {
                "asymmetry": "Neutral", 
                "upside_potential": "Moderate",
                "downside_risk": "Moderate"
            }
        else:
            return {
                "asymmetry": "Unfavorable",
                "upside_potential": "Limited", 
                "downside_risk": "High"
            }
    
    def _calculate_margin_of_safety(self, info: Dict[str, Any]) -> float:
        """Calculate margin of safety (simplified)"""
        # This would integrate with DCF analysis
        return 0.0  # Placeholder
    
    def _assess_interest_rate_sensitivity(self, sector: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Assess interest rate sensitivity"""
        sensitivity_scores = {
            "Financial Services": 30,  # High sensitivity
            "Real Estate": 25,  # High sensitivity
            "Utilities": 40,  # Moderate sensitivity
            "Technology": 70,  # Low sensitivity
            "Healthcare": 75,  # Low sensitivity
        }
        
        score = sensitivity_scores.get(sector, 60)
        return {
            "score": score,
            "sensitivity": "Low" if score > 65 else "Moderate" if score > 45 else "High"
        }
    
    def _assess_currency_exposure(self, ticker: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Assess currency exposure risk"""
        # Simplified: Indian stocks have INR exposure
        if ticker.endswith(('.NS', '.BO')):
            return {
                "score": 60,  # Moderate USD/INR exposure
                "primary_currency": "INR",
                "fx_risk": "Moderate"
            }
        else:
            return {
                "score": 80,  # USD-based, lower FX risk
                "primary_currency": "USD", 
                "fx_risk": "Low"
            }
    
    def _assess_regulatory_risk(self, sector: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Assess regulatory risk"""
        risk_scores = {
            "Financial Services": 40,  # High regulatory risk
            "Healthcare": 50,  # Moderate-high regulatory risk
            "Utilities": 45,  # High regulatory risk
            "Technology": 70,  # Moderate regulatory risk
            "Consumer Staples": 80  # Low regulatory risk
        }
        
        score = risk_scores.get(sector, 65)
        return {
            "score": score,
            "risk_level": "Low" if score > 70 else "Moderate" if score > 50 else "High"
        }
    
    def _get_cyclicality_description(self, score: float) -> str:
        """Get cyclicality description"""
        if score > 75:
            return "Low Cyclicality"
        elif score > 50:
            return "Moderate Cyclicality"
        else:
            return "High Cyclicality"
    
    def _get_macro_grade(self, score: float) -> str:
        """Get macro resilience grade"""
        if score >= 80:
            return "A"
        elif score >= 65:
            return "B"
        elif score >= 50:
            return "C"
        else:
            return "D"
    
    def _get_market_position_desc(self, info: Dict[str, Any]) -> str:
        """Get market position description"""
        market_cap = info.get("marketCap", 0)
        if market_cap > 100e9:
            return "a market-leading position"
        elif market_cap > 10e9:
            return "a strong competitive position"
        else:
            return "a developing market position"
    
    def _assess_innovation_pipeline(self, ticker: str, info: Dict[str, Any]) -> float:
        """Assess innovation pipeline and R&D capabilities"""
        sector = info.get("sector", "")
        
        # Base innovation score by sector
        sector_innovation_scores = {
            "Technology": 75,
            "Healthcare": 70,
            "Industrials": 55,
            "Consumer Cyclical": 45,
            "Financial Services": 40,
            "Energy": 35,
            "Utilities": 30
        }
        
        base_score = sector_innovation_scores.get(sector, 50)
        
        # Adjust based on company size (larger companies typically have more R&D resources)
        market_cap = info.get("marketCap", 0)
        if market_cap > 100e9:  # >$100B
            base_score += 10
        elif market_cap > 10e9:  # >$10B
            base_score += 5
        
        # Adjust based on margins (higher margins suggest differentiated products)
        gross_margins = info.get("grossMargins", 0)
        if gross_margins > 0.5:  # >50% gross margins
            base_score += 10
        elif gross_margins > 0.3:  # >30% gross margins
            base_score += 5
        
        return min(100, max(0, base_score))
    
    def _assess_geographic_expansion(self, ticker: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Assess geographic expansion potential"""
        market_cap = info.get("marketCap", 0)
        sector = info.get("sector", "").lower()
        industry = info.get("industry", "").lower()
        
        if ticker.endswith(('.NS', '.BO')):
            # Indian companies - more nuanced assessment
            base_score = 40  # Base score for Indian companies
            
            # Market cap adjustment
            if market_cap > 100e9:  # Very large cap
                base_score += 25
            elif market_cap > 50e9:  # Large cap
                base_score += 20
            elif market_cap > 10e9:  # Mid-cap
                base_score += 10
            else:  # Small cap
                base_score += 5
            
            # Sector-specific adjustments
            if "banking" in sector or "financial" in sector:
                # Banks have regulatory barriers for international expansion
                base_score -= 15
                expansion_desc = "Regulatory constraints limit international expansion"
            elif "technology" in sector or "software" in sector:
                # Tech companies can expand more easily
                base_score += 20
                expansion_desc = "Digital nature enables easier international expansion"
            elif "pharmaceutical" in sector:
                # Pharma has complex regulatory requirements
                base_score -= 10
                expansion_desc = "Regulatory complexity affects international expansion"
            elif "energy" in sector or "oil" in sector:
                # Energy companies often have global operations
                base_score += 15
                expansion_desc = "Energy sector typically has global operations"
            else:
                expansion_desc = "Moderate expansion potential"
        else:
            # Non-Indian companies (assume already global)
            base_score = 60
            expansion_desc = "Established global presence"
        
        # Ensure score is within bounds
        expansion_score = min(100, max(0, base_score))
        
        return {
            "score": expansion_score,
            "description": expansion_desc,
            "expansion_potential": "High" if expansion_score > 70 else "Medium" if expansion_score > 50 else "Low"
        }

    # ============================================================================
    # PHASE 6: STRATEGIC & BUSINESS ANALYSIS ENHANCEMENTS
    # ============================================================================
    
    async def _analyze_growth_drivers(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze key growth drivers and catalysts
        """
        info = data["info"]
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        market_cap = info.get("marketCap", 0)
        
        growth_drivers = []
        driver_scores = []
        
        # Revenue growth analysis
        revenue_growth = self._analyze_revenue_growth_drivers(ticker, info)
        if revenue_growth:
            growth_drivers.append(revenue_growth)
            driver_scores.append(revenue_growth["score"])
        
        # Market expansion drivers
        market_expansion = self._analyze_market_expansion_drivers(sector, industry, market_cap)
        if market_expansion:
            growth_drivers.append(market_expansion)
            driver_scores.append(market_expansion["score"])
        
        # Innovation drivers
        innovation_drivers = self._analyze_innovation_drivers(sector, industry, info)
        if innovation_drivers:
            growth_drivers.append(innovation_drivers)
            driver_scores.append(innovation_drivers["score"])
        
        # Operational efficiency drivers
        efficiency_drivers = self._analyze_efficiency_drivers(ticker, info)
        if efficiency_drivers:
            growth_drivers.append(efficiency_drivers)
            driver_scores.append(efficiency_drivers["score"])
        
        # Calculate overall score
        overall_score = sum(driver_scores) / len(driver_scores) if driver_scores else 50
        
        return {
            "score": min(100, max(0, overall_score)),
            "drivers": growth_drivers,
            "primary_drivers": [d for d in growth_drivers if d["score"] > 70],
            "secondary_drivers": [d for d in growth_drivers if 50 <= d["score"] <= 70],
            "growth_potential": "High" if overall_score > 70 else "Medium" if overall_score > 50 else "Low"
        }
    
    def _analyze_revenue_growth_drivers(self, ticker: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze revenue growth drivers"""
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        drivers = []
        score = 50
        
        # Sector-specific revenue drivers
        if sector == "Technology":
            if "Software" in industry:
                drivers.extend([
                    "SaaS subscription growth",
                    "Digital transformation adoption",
                    "Cloud migration trends"
                ])
                score = 80
            elif "Semiconductors" in industry:
                drivers.extend([
                    "AI/ML chip demand",
                    "5G infrastructure buildout",
                    "Automotive electronics growth"
                ])
                score = 75
        elif sector == "Healthcare":
            drivers.extend([
                "Aging population demographics",
                "Precision medicine adoption",
                "Digital health integration"
            ])
            score = 70
        elif sector == "Financial Services":
            drivers.extend([
                "Digital banking adoption",
                "Fintech integration",
                "Regulatory technology needs"
            ])
            score = 65
        
        return {
            "type": "Revenue Growth",
            "score": score,
            "drivers": drivers,
            "description": f"Revenue growth driven by {len(drivers)} key factors"
        }
    
    def _analyze_market_expansion_drivers(self, sector: str, industry: str, market_cap: float) -> Dict[str, Any]:
        """Analyze market expansion opportunities"""
        drivers = []
        score = 50
        
        # Geographic expansion
        if market_cap > 50e9:  # Large companies
            drivers.append("International market expansion")
            score += 20
        elif market_cap > 10e9:  # Mid-cap companies
            drivers.append("Regional market expansion")
            score += 15
        
        # Adjacent market expansion
        if sector == "Technology":
            drivers.extend([
                "Adjacent technology markets",
                "Platform ecosystem expansion"
            ])
            score += 25
        elif sector == "Healthcare":
            drivers.extend([
                "Therapeutic area expansion",
                "Diagnostic market entry"
            ])
            score += 20
        
        return {
            "type": "Market Expansion",
            "score": min(100, score),
            "drivers": drivers,
            "description": f"Market expansion through {len(drivers)} strategic initiatives"
        }
    
    def _analyze_innovation_drivers(self, sector: str, industry: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze innovation-driven growth"""
        drivers = []
        score = 50
        
        # R&D intensity analysis
        business_summary = info.get("businessSummary", "").lower()
        
        if "research" in business_summary or "development" in business_summary:
            drivers.append("R&D investment")
            score += 15
        
        if "innovation" in business_summary or "technology" in business_summary:
            drivers.append("Technology innovation")
            score += 20
        
        # Sector-specific innovation drivers
        if sector == "Technology":
            drivers.extend([
                "AI/ML capabilities",
                "Platform development",
                "API ecosystem"
            ])
            score += 25
        elif sector == "Healthcare":
            drivers.extend([
                "Drug discovery pipeline",
                "Medical device innovation",
                "Digital therapeutics"
            ])
            score += 20
        
        return {
            "type": "Innovation",
            "score": min(100, score),
            "drivers": drivers,
            "description": f"Innovation-driven growth through {len(drivers)} key areas"
        }
    
    def _analyze_efficiency_drivers(self, ticker: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze operational efficiency drivers"""
        drivers = []
        score = 50
        
        # Scale efficiency
        market_cap = info.get("marketCap", 0)
        if market_cap > 100e9:
            drivers.append("Economies of scale")
            score += 20
        
        # Operational efficiency indicators
        business_summary = info.get("businessSummary", "").lower()
        
        if "automation" in business_summary:
            drivers.append("Process automation")
            score += 15
        
        if "digital" in business_summary:
            drivers.append("Digital transformation")
            score += 15
        
        if "platform" in business_summary:
            drivers.append("Platform efficiency")
            score += 10
        
        return {
            "type": "Operational Efficiency",
            "score": min(100, score),
            "drivers": drivers,
            "description": f"Efficiency gains through {len(drivers)} operational improvements"
        }
    
    async def _analyze_segment_performance(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze segment-wise performance and growth
        """
        info = data["info"]
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        # For now, we'll create segment analysis based on industry characteristics
        # In a real implementation, this would use actual segment data
        
        segments = self._identify_business_segments(sector, industry, info)
        
        segment_scores = []
        for segment in segments:
            segment_scores.append(segment["score"])
        
        overall_score = sum(segment_scores) / len(segment_scores) if segment_scores else 50
        
        return {
            "score": min(100, max(0, overall_score)),
            "segments": segments,
            "top_performing_segment": max(segments, key=lambda x: x["score"]) if segments else None,
            "growth_segments": [s for s in segments if s["score"] > 70],
            "declining_segments": [s for s in segments if s["score"] < 40]
        }
    
    def _identify_business_segments(self, sector: str, industry: str, info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify and analyze business segments"""
        segments = []
        
        # Sector-specific segment analysis
        if sector == "Technology":
            if "Software" in industry:
                segments.extend([
                    {
                        "name": "Enterprise Software",
                        "score": 75,
                        "growth_rate": "12%",
                        "description": "Core enterprise software solutions"
                    },
                    {
                        "name": "Cloud Services",
                        "score": 85,
                        "growth_rate": "18%",
                        "description": "Cloud infrastructure and platform services"
                    },
                    {
                        "name": "Professional Services",
                        "score": 65,
                        "growth_rate": "8%",
                        "description": "Implementation and consulting services"
                    }
                ])
            elif "Semiconductors" in industry:
                segments.extend([
                    {
                        "name": "Data Center Chips",
                        "score": 80,
                        "growth_rate": "15%",
                        "description": "AI/ML and data center processors"
                    },
                    {
                        "name": "Consumer Electronics",
                        "score": 60,
                        "growth_rate": "5%",
                        "description": "Mobile and consumer device chips"
                    },
                    {
                        "name": "Automotive",
                        "score": 70,
                        "growth_rate": "12%",
                        "description": "Automotive semiconductor solutions"
                    }
                ])
        elif sector == "Healthcare":
            segments.extend([
                {
                    "name": "Pharmaceuticals",
                    "score": 70,
                    "growth_rate": "6%",
                    "description": "Drug development and manufacturing"
                },
                {
                    "name": "Medical Devices",
                    "score": 75,
                    "growth_rate": "8%",
                    "description": "Medical device and diagnostic equipment"
                },
                {
                    "name": "Healthcare Services",
                    "score": 65,
                    "growth_rate": "5%",
                    "description": "Healthcare delivery and services"
                }
            ])
        elif sector == "Financial Services":
            segments.extend([
                {
                    "name": "Retail Banking",
                    "score": 60,
                    "growth_rate": "3%",
                    "description": "Consumer banking and lending"
                },
                {
                    "name": "Investment Banking",
                    "score": 70,
                    "growth_rate": "8%",
                    "description": "Corporate finance and capital markets"
                },
                {
                    "name": "Asset Management",
                    "score": 75,
                    "growth_rate": "10%",
                    "description": "Investment management and advisory"
                }
            ])
        else:
            # Default segments for other sectors
            segments.append({
                "name": "Core Business",
                "score": 60,
                "growth_rate": "5%",
                "description": "Primary business operations"
            })
        
        return segments
    
    async def _analyze_competitive_landscape(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze competitive landscape and positioning
        """
        info = data["info"]
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        market_cap = info.get("marketCap", 0)
        
        # Competitive positioning
        positioning = self._assess_competitive_positioning(market_cap, sector)
        
        # Competitive threats
        threats = self._identify_competitive_threats(sector, industry)
        
        # Competitive advantages
        advantages = self._identify_competitive_advantages(ticker, info)
        
        # Calculate competitive score
        competitive_score = (
            positioning["score"] * 0.4 +
            (100 - threats["risk_score"]) * 0.3 +
            advantages["score"] * 0.3
        )
        
        return {
            "score": min(100, max(0, competitive_score)),
            "positioning": positioning,
            "threats": threats,
            "advantages": advantages,
            "competitive_strength": "Strong" if competitive_score > 70 else "Moderate" if competitive_score > 50 else "Weak"
        }
    
    def _assess_competitive_positioning(self, market_cap: float, sector: str) -> Dict[str, Any]:
        """Assess competitive market positioning"""
        if market_cap > 500e9:
            return {
                "position": "Market Leader",
                "score": 90,
                "description": "Dominant market position with significant competitive advantages"
            }
        elif market_cap > 100e9:
            return {
                "position": "Strong Player",
                "score": 75,
                "description": "Strong market position with competitive advantages"
            }
        elif market_cap > 10e9:
            return {
                "position": "Established Player",
                "score": 60,
                "description": "Established market presence with moderate competitive advantages"
            }
        else:
            return {
                "position": "Smaller Player",
                "score": 40,
                "description": "Smaller market presence with limited competitive advantages"
            }
    
    def _identify_competitive_threats(self, sector: str, industry: str) -> Dict[str, Any]:
        """Identify competitive threats and risks"""
        threats = []
        risk_score = 30  # Lower is better
        
        # Sector-specific threats
        if sector == "Technology":
            threats.extend([
                "Rapid technological change",
                "New market entrants",
                "Platform competition"
            ])
            risk_score = 60
        elif sector == "Healthcare":
            threats.extend([
                "Regulatory changes",
                "Patent expirations",
                "Generic competition"
            ])
            risk_score = 50
        elif sector == "Financial Services":
            threats.extend([
                "Fintech disruption",
                "Regulatory tightening",
                "Digital transformation pressure"
            ])
            risk_score = 55
        
        return {
            "threats": threats,
            "risk_score": risk_score,
            "risk_level": "High" if risk_score > 60 else "Medium" if risk_score > 40 else "Low"
        }
    
    def _identify_competitive_advantages(self, ticker: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Identify competitive advantages"""
        advantages = []
        score = 50
        
        market_cap = info.get("marketCap", 0)
        sector = info.get("sector", "")
        
        # Scale advantages
        if market_cap > 100e9:
            advantages.append("Economies of scale")
            score += 20
        
        # Brand strength
        if market_cap > 50e9:
            advantages.append("Brand recognition")
            score += 15
        
        # Technology advantages
        if sector == "Technology":
            advantages.extend([
                "Technology platform",
                "Network effects",
                "Data advantages"
            ])
            score += 25
        
        # Regulatory advantages
        if sector in ["Financial Services", "Healthcare", "Utilities"]:
            advantages.append("Regulatory barriers")
            score += 15
        
        return {
            "advantages": advantages,
            "score": min(100, score),
            "advantage_strength": "Strong" if score > 70 else "Moderate" if score > 50 else "Limited"
        }
    
    async def _analyze_industry_outlook(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze industry outlook and trends
        """
        info = data["info"]
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        # Industry growth outlook
        growth_outlook = self._assess_industry_growth_outlook(sector, industry)
        
        # Industry trends
        trends = self._identify_industry_trends(sector, industry)
        
        # Industry risks
        risks = self._identify_industry_risks(sector, industry)
        
        # Calculate industry outlook score
        outlook_score = (
            growth_outlook["score"] * 0.5 +
            trends["score"] * 0.3 +
            (100 - risks["risk_score"]) * 0.2
        )
        
        return {
            "score": min(100, max(0, outlook_score)),
            "growth_outlook": growth_outlook,
            "trends": trends,
            "risks": risks,
            "overall_outlook": "Positive" if outlook_score > 70 else "Neutral" if outlook_score > 50 else "Negative"
        }
    
    def _assess_industry_growth_outlook(self, sector: str, industry: str) -> Dict[str, Any]:
        """Assess industry growth outlook"""
        # Industry-specific growth rates (5-year CAGR estimates)
        growth_rates = {
            "Technology": {
                "Software—Application": 12,
                "Software—Infrastructure": 15,
                "Semiconductors": 8,
                "default": 10
            },
            "Healthcare": {
                "Biotechnology": 8,
                "Drug Manufacturers—General": 5,
                "Medical Devices": 7,
                "default": 6
            },
            "Financial Services": {
                "Banks—Regional": 3,
                "Insurance": 4,
                "Asset Management": 6,
                "default": 4
            },
            "Consumer Cyclical": {
                "Automotive": 4,
                "Retail—Apparel": 3,
                "default": 3
            },
            "default": 4
        }
        
        sector_data = growth_rates.get(sector, {"default": 4})
        growth_rate = sector_data.get(industry, sector_data["default"])
        
        # Convert to score
        score = min(100, max(0, growth_rate * 8))
        
        return {
            "growth_rate": growth_rate,
            "score": score,
            "outlook": "High Growth" if growth_rate > 8 else "Moderate Growth" if growth_rate > 4 else "Low Growth"
        }
    
    def _identify_industry_trends(self, sector: str, industry: str) -> Dict[str, Any]:
        """Identify key industry trends"""
        trends_map = {
            "Technology": {
                "trends": [
                    "Digital transformation acceleration",
                    "AI/ML integration",
                    "Cloud-first strategies",
                    "Cybersecurity focus"
                ],
                "score": 85
            },
            "Healthcare": {
                "trends": [
                    "Precision medicine",
                    "Digital health adoption",
                    "Value-based care",
                    "Telemedicine growth"
                ],
                "score": 75
            },
            "Financial Services": {
                "trends": [
                    "Digital banking transformation",
                    "Fintech integration",
                    "Regulatory technology",
                    "Sustainable finance"
                ],
                "score": 70
            },
            "Consumer Cyclical": {
                "trends": [
                    "E-commerce acceleration",
                    "Sustainability focus",
                    "Direct-to-consumer models",
                    "Personalization"
                ],
                "score": 65
            }
        }
        
        sector_trends = trends_map.get(sector, {
            "trends": ["Industry consolidation", "Digital adoption"],
            "score": 50
        })
        
        return {
            "trends": sector_trends["trends"],
            "score": sector_trends["score"],
            "trend_strength": "Strong" if sector_trends["score"] > 70 else "Moderate" if sector_trends["score"] > 50 else "Weak"
        }
    
    def _identify_industry_risks(self, sector: str, industry: str) -> Dict[str, Any]:
        """Identify industry-specific risks"""
        risks_map = {
            "Technology": {
                "risks": [
                    "Rapid technological obsolescence",
                    "Cybersecurity threats",
                    "Regulatory scrutiny",
                    "Talent competition"
                ],
                "risk_score": 60
            },
            "Healthcare": {
                "risks": [
                    "Regulatory changes",
                    "Patent cliffs",
                    "Pricing pressure",
                    "Clinical trial failures"
                ],
                "risk_score": 55
            },
            "Financial Services": {
                "risks": [
                    "Interest rate sensitivity",
                    "Regulatory tightening",
                    "Credit risk",
                    "Fintech disruption"
                ],
                "risk_score": 65
            },
            "Consumer Cyclical": {
                "risks": [
                    "Economic sensitivity",
                    "Consumer behavior changes",
                    "Supply chain disruptions",
                    "Competition intensity"
                ],
                "risk_score": 70
            }
        }
        
        sector_risks = risks_map.get(sector, {
            "risks": ["Economic sensitivity", "Competitive pressure"],
            "risk_score": 50
        })
        
        return {
            "risks": sector_risks["risks"],
            "risk_score": sector_risks["risk_score"],
            "risk_level": "High" if sector_risks["risk_score"] > 60 else "Medium" if sector_risks["risk_score"] > 40 else "Low"
        }


# Main analysis function
async def analyze_strategic_conviction(ticker: str) -> Dict[str, Any]:
    """
    Main function to analyze strategic investment conviction
    """
    engine = StrategicConvictionEngine()
    return await engine.analyze_conviction(ticker)
