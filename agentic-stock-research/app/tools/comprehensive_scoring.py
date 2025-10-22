"""
Comprehensive Stock Scoring & Ranking Engine
Implements multi-dimensional scoring framework with weighted pillars
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.tools.fundamentals import compute_fundamentals
from app.tools.dcf_valuation import perform_dcf_valuation
from app.tools.governance_analysis import analyze_corporate_governance

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configurable scoring weights for different pillars"""
    financial_health: float = 0.30    # 30% - Cash flow quality, profitability
    valuation: float = 0.25           # 25% - Relative + intrinsic valuation
    growth_prospects: float = 0.20    # 20% - Revenue/margin expansion potential
    governance: float = 0.15          # 15% - Corporate governance & ownership
    macro_sensitivity: float = 0.10   # 10% - Event/catalyst & macro exposure
    
    def __post_init__(self):
        """Validate weights sum to 1.0"""
        total = (self.financial_health + self.valuation + self.growth_prospects + 
                self.governance + self.macro_sensitivity)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


@dataclass
class PillarScore:
    """Individual pillar scoring result"""
    score: float          # 0-100 score
    confidence: float     # 0-1 confidence level
    key_metrics: Dict[str, Any]
    positive_factors: List[str]
    negative_factors: List[str]
    data_quality: str     # "High", "Medium", "Low"


@dataclass
class ComprehensiveScore:
    """Complete scoring result for a ticker"""
    ticker: str
    overall_score: float              # 0-100 weighted composite score
    overall_grade: str               # A+ to F letter grade
    confidence_level: float          # 0-1 overall confidence
    recommendation: str              # Buy/Hold/Sell with strength
    
    # Individual pillar scores
    financial_health: PillarScore
    valuation: PillarScore
    growth_prospects: PillarScore
    governance: PillarScore
    macro_sensitivity: PillarScore
    
    # Trading recommendations
    position_sizing_pct: float       # Recommended portfolio allocation %
    entry_zone: Tuple[float, float]  # (min_price, max_price) for entry
    entry_explanation: str          # Explanation of how entry zone was calculated
    target_price: float
    stop_loss: float
    time_horizon_months: int
    
    # Risk metrics
    risk_rating: str                 # "Low", "Medium", "High", "Very High"
    key_risks: List[str]
    key_catalysts: List[str]


class ComprehensiveScoringEngine:
    """Multi-dimensional stock scoring and ranking engine"""
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()
        
        # Sector-specific adjustments (can be expanded)
        self.sector_adjustments = {
            "Technology": {"growth_prospects": 1.2, "valuation": 0.9},
            "Banking": {"financial_health": 1.1, "governance": 1.2},
            "Pharmaceuticals": {"growth_prospects": 1.1, "macro_sensitivity": 0.8},
            "Real Estate": {"financial_health": 1.2, "macro_sensitivity": 1.3},
            "Utilities": {"financial_health": 1.1, "growth_prospects": 0.8}
        }
    
    async def score_ticker(self, ticker: str, current_price: Optional[float] = None) -> ComprehensiveScore:
        """
        Generate comprehensive score for a ticker
        """
        try:
            logger.info(f"Starting comprehensive scoring for {ticker}")
            
            # Parallel data collection for all pillars
            results = await asyncio.gather(
                self._score_financial_health(ticker),
                self._score_valuation(ticker, current_price),
                self._score_growth_prospects(ticker),
                self._score_governance(ticker),
                self._score_macro_sensitivity(ticker),
                return_exceptions=True
            )
            
            # Handle any failed pillar calculations
            pillar_scores = {}
            pillar_names = ["financial_health", "valuation", "growth_prospects", "governance", "macro_sensitivity"]
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to calculate {pillar_names[i]} for {ticker}: {result}")
                    # Create default low-confidence score
                    pillar_scores[pillar_names[i]] = PillarScore(
                        score=50.0,
                        confidence=0.1,
                        key_metrics={},
                        positive_factors=[],
                        negative_factors=[f"Data collection failed: {str(result)[:100]}"],
                        data_quality="Low"
                    )
                else:
                    pillar_scores[pillar_names[i]] = result
            
            # Apply sector adjustments if sector is identified
            sector = await self._identify_sector(ticker)
            if sector in self.sector_adjustments:
                pillar_scores = self._apply_sector_adjustments(pillar_scores, sector)
            
            # Calculate weighted overall score
            overall_score = self._calculate_weighted_score(pillar_scores)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(pillar_scores)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(overall_score, pillar_scores)
            
            # Calculate trading parameters
            trading_params = await self._calculate_trading_parameters(
                ticker, overall_score, pillar_scores, current_price
            )
            
            # Assess risk and identify catalysts
            risk_assessment = self._assess_risk_factors(pillar_scores)
            
            return ComprehensiveScore(
                ticker=ticker,
                overall_score=overall_score,
                overall_grade=self._score_to_grade(overall_score),
                confidence_level=overall_confidence,
                recommendation=recommendation,
                financial_health=pillar_scores["financial_health"],
                valuation=pillar_scores["valuation"],
                growth_prospects=pillar_scores["growth_prospects"],
                governance=pillar_scores["governance"],
                macro_sensitivity=pillar_scores["macro_sensitivity"],
                position_sizing_pct=trading_params["position_sizing"],
                entry_zone=trading_params["entry_zone"],
                entry_explanation=trading_params["entry_explanation"],
                target_price=trading_params["target_price"],
                stop_loss=trading_params["stop_loss"],
                time_horizon_months=trading_params["time_horizon"],
                risk_rating=risk_assessment["risk_rating"],
                key_risks=risk_assessment["key_risks"],
                key_catalysts=risk_assessment["key_catalysts"]
            )
            
        except Exception as e:
            logger.error(f"Comprehensive scoring failed for {ticker}: {e}")
            raise
    
    async def _score_financial_health(self, ticker: str) -> PillarScore:
        """Score financial health pillar (30% weight)"""
        try:
            fundamentals = await compute_fundamentals(ticker)
            
            # Key financial health metrics
            roe = fundamentals.get("roe", 0) or 0
            roic = fundamentals.get("roic", 0) or 0
            debt_to_equity = fundamentals.get("debtToEquity", 0) or 0
            interest_coverage = fundamentals.get("interestCoverage", 0) or 0
            fcf_yield = fundamentals.get("fcfYield", 0) or 0
            gross_margins = fundamentals.get("grossMargins", 0) or 0
            operating_margins = fundamentals.get("operatingMargins", 0) or 0
            
            # Scoring logic
            score_components = {}
            
            # ROE scoring (0-25 points) - ROE stored as percentage
            if roe >= 20.0:  # >20% ROE
                score_components["roe"] = 25
            elif roe >= 15.0:  # 15-20% ROE
                score_components["roe"] = 20
            elif roe >= 12.0:  # 12-15% ROE
                score_components["roe"] = 15
            elif roe >= 8.0:  # 8-12% ROE
                score_components["roe"] = 10
            else:
                score_components["roe"] = 5
            
            # ROIC scoring (0-20 points) - ROIC stored as percentage
            if roic >= 15.0:
                score_components["roic"] = 20
            elif roic >= 12.0:
                score_components["roic"] = 15
            elif roic >= 8.0:
                score_components["roic"] = 10
            else:
                score_components["roic"] = 5
            
            # Debt management (0-20 points)
            # Banks naturally have high D/E (deposits are liabilities), so adjust thresholds
            sector = fundamentals.get("sector", "")
            is_financial = "Financial" in sector or "Bank" in sector
            logger.info(f"Sector for {ticker}: '{sector}', is_financial={is_financial}, D/E={debt_to_equity:.1f}%")
            
            if is_financial:
                # Financial institutions: Higher thresholds (D/E of 500-1000% is normal)
                if debt_to_equity <= 400:  # Conservative for a bank
                    score_components["leverage"] = 20
                elif debt_to_equity <= 700:  # Typical bank leverage
                    score_components["leverage"] = 15
                elif debt_to_equity <= 1000:  # High but acceptable for banks
                    score_components["leverage"] = 10
                else:  # Very high even for a bank
                    score_components["leverage"] = 5
            else:
                # Non-financial: Traditional D/E thresholds
                if debt_to_equity <= 30:  # Low leverage
                    score_components["leverage"] = 20
                elif debt_to_equity <= 60:  # Moderate leverage
                    score_components["leverage"] = 15
                elif debt_to_equity <= 100:  # High but manageable
                    score_components["leverage"] = 10
                else:  # Very high leverage
                    score_components["leverage"] = 5
            
            # Interest coverage (0-15 points)
            # Handle None or 0 values (common for banks where interest expense may not be reported traditionally)
            if interest_coverage is None or interest_coverage == 0:
                score_components["interest_coverage"] = 10  # Neutral score for missing/not-applicable data
            elif interest_coverage >= 5:
                score_components["interest_coverage"] = 15
            elif interest_coverage >= 3:
                score_components["interest_coverage"] = 12
            elif interest_coverage >= 2:
                score_components["interest_coverage"] = 8
            elif interest_coverage < 1:
                score_components["interest_coverage"] = 2  # Critical distress signal
            else:
                score_components["interest_coverage"] = 5
            
            # FCF yield (0-10 points) - FCF yield stored as percentage
            if fcf_yield >= 8.0:  # >8% FCF yield
                score_components["fcf_yield"] = 10
            elif fcf_yield >= 5.0:
                score_components["fcf_yield"] = 8
            elif fcf_yield >= 2.0:
                score_components["fcf_yield"] = 5
            else:
                score_components["fcf_yield"] = 2
            
            # Margins (0-10 points) - Margins stored as percentage
            margin_score = 0
            if operating_margins >= 20.0:
                margin_score += 5
            elif operating_margins >= 15.0:
                margin_score += 4
            elif operating_margins >= 10.0:
                margin_score += 3
            
            if gross_margins >= 50.0:
                margin_score += 5
            elif gross_margins >= 30.0:
                margin_score += 3
            elif gross_margins >= 20.0:
                margin_score += 2
            
            score_components["margins"] = margin_score
            
            total_score = sum(score_components.values())
            
            # Identify positive and negative factors
            positive_factors = []
            negative_factors = []
            
            if roe >= 15.0:  # ROE stored as percentage
                positive_factors.append(f"Strong ROE of {roe:.1f}%")
            elif roe < 8.0 and roe > 0:  # ROE stored as percentage, ignore if 0 (data issue)
                negative_factors.append(f"Weak ROE of {roe:.1f}%")
            
            # Adjust D/E messaging based on sector
            if is_financial:
                # Banks: D/E of 600-700% is typical, don't flag as risk unless extreme
                if debt_to_equity <= 500:
                    positive_factors.append(f"Below-average leverage for bank (D/E: {debt_to_equity:.1f}%)")
                elif debt_to_equity > 1000:
                    negative_factors.append(f"High leverage even for bank (D/E: {debt_to_equity:.1f}%)")
            else:
                # Non-financial: Traditional thresholds
                if debt_to_equity <= 50:
                    positive_factors.append(f"Conservative leverage (D/E: {debt_to_equity:.1f}%)")
                elif debt_to_equity > 100:
                    negative_factors.append(f"High leverage (D/E: {debt_to_equity:.1f}%)")
            
            # Only report interest coverage if meaningful (not None or 0)
            if interest_coverage is not None and interest_coverage > 0:
                if interest_coverage >= 3:
                    positive_factors.append(f"Adequate interest coverage ({interest_coverage:.1f}x)")
                elif interest_coverage < 2:
                    negative_factors.append(f"Poor interest coverage ({interest_coverage:.1f}x)")
            
            if fcf_yield >= 5.0:  # FCF yield stored as percentage
                positive_factors.append(f"Good FCF yield ({fcf_yield:.1f}%)")
            
            # Determine data quality
            data_quality = "High" if len([x for x in [roe, roic, debt_to_equity] if x != 0]) >= 2 else "Medium"
            
            return PillarScore(
                score=min(100.0, total_score),
                confidence=0.8 if data_quality == "High" else 0.6,
                key_metrics={
                    "roe": roe,
                    "roic": roic,
                    "debt_to_equity": debt_to_equity,
                    "interest_coverage": interest_coverage,
                    "fcf_yield": fcf_yield,
                    "operating_margins": operating_margins
                },
                positive_factors=positive_factors,
                negative_factors=negative_factors,
                data_quality=data_quality
            )
            
        except Exception as e:
            logger.error(f"Financial health scoring failed for {ticker}: {e}")
            return PillarScore(50.0, 0.2, {}, [], [str(e)], "Low")
    
    async def _score_valuation(self, ticker: str, current_price: Optional[float]) -> PillarScore:
        """Score valuation pillar (25% weight)"""
        try:
            # Get DCF valuation
            dcf_result = await perform_dcf_valuation(ticker, current_price)
            
            # Get relative valuation metrics
            fundamentals = await compute_fundamentals(ticker)
            
            pe = fundamentals.get("pe", 0) or 0
            pb = fundamentals.get("pb", 0) or 0
            peg = fundamentals.get("peg", 0) or 0
            
            score_components = {}
            
            # DCF-based scoring (0-50 points)
            if "error" not in dcf_result and dcf_result.get("intrinsic_value"):
                logger.info(f"DCF valuation successful for {ticker}")
                margin_of_safety = dcf_result.get("margin_of_safety", 0)
                if margin_of_safety >= 0.3:  # >30% MoS
                    score_components["dcf"] = 50
                elif margin_of_safety >= 0.2:  # 20-30% MoS
                    score_components["dcf"] = 40
                elif margin_of_safety >= 0.1:  # 10-20% MoS
                    score_components["dcf"] = 30
                elif margin_of_safety >= 0:    # 0-10% MoS
                    score_components["dcf"] = 20
                else:  # Negative MoS (overvalued)
                    score_components["dcf"] = 10
            else:
                logger.warning(f"DCF failed for {ticker}, using P/E fallback valuation")
                # P/E Fallback Valuation
                pe_fallback_score = self._calculate_pe_fallback_score(fundamentals, current_price, ticker)
                score_components["dcf"] = pe_fallback_score
            
            # P/E ratio scoring (0-25 points)
            if pe > 0:
                if pe <= 12:
                    score_components["pe"] = 25
                elif pe <= 18:
                    score_components["pe"] = 20
                elif pe <= 25:
                    score_components["pe"] = 15
                elif pe <= 35:
                    score_components["pe"] = 10
                else:
                    score_components["pe"] = 5
            else:
                score_components["pe"] = 12  # Neutral for no/negative earnings
            
            # P/B ratio scoring (0-15 points)
            if pb > 0:
                if pb <= 1.0:
                    score_components["pb"] = 15
                elif pb <= 2.0:
                    score_components["pb"] = 12
                elif pb <= 3.0:
                    score_components["pb"] = 8
                else:
                    score_components["pb"] = 5
            else:
                score_components["pb"] = 8
            
            # PEG ratio scoring (0-10 points)
            if peg > 0:
                if peg <= 0.8:
                    score_components["peg"] = 10
                elif peg <= 1.2:
                    score_components["peg"] = 8
                elif peg <= 2.0:
                    score_components["peg"] = 5
                else:
                    score_components["peg"] = 2
            else:
                score_components["peg"] = 5
            
            total_score = sum(score_components.values())
            
            # Generate factors
            positive_factors = []
            negative_factors = []
            
            if "error" not in dcf_result:
                mos = dcf_result.get("margin_of_safety", 0)
                if mos >= 0.2:
                    positive_factors.append(f"Strong margin of safety ({mos*100:.1f}%)")
                elif mos < 0:
                    negative_factors.append(f"Trading above intrinsic value (MoS: {mos*100:.1f}%)")
            
            if pe > 0 and pe <= 15:
                positive_factors.append(f"Attractive P/E ratio ({pe:.1f})")
            elif pe > 30:
                negative_factors.append(f"High P/E ratio ({pe:.1f})")
            
            if pb > 0 and pb <= 1.5:
                positive_factors.append(f"Reasonable P/B ratio ({pb:.1f})")
            elif pb > 3:
                negative_factors.append(f"High P/B ratio ({pb:.1f})")
            
            return PillarScore(
                score=min(100.0, total_score),
                confidence=0.8 if "error" not in dcf_result else 0.6,
                key_metrics={
                    "intrinsic_value": dcf_result.get("intrinsic_value", 0),
                    "margin_of_safety": dcf_result.get("margin_of_safety", 0),
                    "pe_ratio": pe,
                    "pb_ratio": pb,
                    "peg_ratio": peg
                },
                positive_factors=positive_factors,
                negative_factors=negative_factors,
                data_quality="High" if "error" not in dcf_result else "Medium"
            )
            
        except Exception as e:
            logger.error(f"Valuation scoring failed for {ticker}: {e}")
            return PillarScore(50.0, 0.2, {}, [], [str(e)], "Low")
    
    def _calculate_pe_fallback_score(self, fundamentals: Dict[str, Any], current_price: Optional[float], ticker: str) -> float:
        """Calculate P/E-based fallback score when DCF fails"""
        try:
            logger.info(f"Calculating P/E fallback score for {ticker}")
            
            # Get P/E ratios
            trailing_pe = fundamentals.get("trailingPE")
            forward_pe = fundamentals.get("forwardPE")
            pe = trailing_pe or forward_pe
            
            if not pe or pe <= 0:
                logger.warning(f"No valid P/E ratio for {ticker}, using neutral score")
                return 25  # Neutral score
            
            # Get sector for industry comparison
            sector = fundamentals.get("sector", "Technology")
            industry_pe = self._get_industry_average_pe(sector)
            
            # Calculate relative P/E score
            pe_ratio = pe / industry_pe
            
            if pe_ratio <= 0.6:  # Trading at <60% of industry average
                score = 45  # Very attractive
            elif pe_ratio <= 0.8:  # Trading at <80% of industry average
                score = 35  # Attractive
            elif pe_ratio <= 1.0:  # Trading at industry average
                score = 25  # Fair
            elif pe_ratio <= 1.3:  # Trading at <130% of industry average
                score = 15  # Expensive
            else:  # Trading at >130% of industry average
                score = 5   # Very expensive
            
            logger.info(f"P/E fallback for {ticker}: pe={pe:.1f}, industry_pe={industry_pe:.1f}, ratio={pe_ratio:.2f}, score={score}")
            return float(score)
            
        except Exception as e:
            logger.error(f"P/E fallback scoring failed for {ticker}: {e}")
            return 25.0  # Neutral fallback
    
    def _get_industry_average_pe(self, sector: str) -> float:
        """Get industry average P/E ratio by sector"""
        # Industry average P/E ratios for Indian/Global markets
        industry_pes = {
            "Technology": 25.0,
            "Healthcare": 22.0,
            "Financial Services": 12.0,
            "Consumer Cyclical": 18.0,
            "Consumer Defensive": 20.0,
            "Industrials": 16.0,
            "Energy": 15.0,
            "Utilities": 18.0,
            "Real Estate": 20.0,
            "Materials": 14.0,
            "Communication Services": 20.0,
            "Basic Materials": 14.0
        }
        
        return industry_pes.get(sector, 18.0)  # Default to 18 if sector not found
    
    async def _score_growth_prospects(self, ticker: str) -> PillarScore:
        """Score growth prospects pillar (20% weight)"""
        try:
            fundamentals = await compute_fundamentals(ticker)
            
            revenue_growth = fundamentals.get("revenueGrowth", 0) or 0
            gross_margins = fundamentals.get("grossMargins", 0) or 0
            operating_margins = fundamentals.get("operatingMargins", 0) or 0
            roe = fundamentals.get("roe", 0) or 0
            
            score_components = {}
            
            # Revenue growth scoring (0-40 points) - Stored as percentage
            if revenue_growth >= 25.0:  # >25% growth
                score_components["revenue_growth"] = 40
            elif revenue_growth >= 15.0:  # 15-25% growth
                score_components["revenue_growth"] = 30
            elif revenue_growth >= 10.0:  # 10-15% growth
                score_components["revenue_growth"] = 25
            elif revenue_growth >= 5.0:  # 5-10% growth
                score_components["revenue_growth"] = 15
            elif revenue_growth >= 0:     # 0-5% growth
                score_components["revenue_growth"] = 10
            else:  # Negative growth
                score_components["revenue_growth"] = 5
            
            # Margin expansion potential (0-30 points) - Stored as percentage
            if operating_margins >= 20.0:
                score_components["margins"] = 30
            elif operating_margins >= 15.0:
                score_components["margins"] = 25
            elif operating_margins >= 10.0:
                score_components["margins"] = 20
            else:
                score_components["margins"] = 15
            
            # ROE sustainability (0-30 points) - Stored as percentage
            if roe >= 20.0:
                score_components["roe_sustainability"] = 30
            elif roe >= 15.0:
                score_components["roe_sustainability"] = 25
            elif roe >= 12.0:
                score_components["roe_sustainability"] = 20
            else:
                score_components["roe_sustainability"] = 15
            
            total_score = sum(score_components.values())
            
            # Generate factors
            positive_factors = []
            negative_factors = []
            
            if revenue_growth >= 15.0:  # Stored as percentage
                positive_factors.append(f"Strong revenue growth ({revenue_growth:.1f}%)")
            elif revenue_growth < 0:
                negative_factors.append(f"Revenue decline ({revenue_growth:.1f}%)")
            
            if operating_margins >= 15.0:  # Stored as percentage
                positive_factors.append(f"Healthy operating margins ({operating_margins:.1f}%)")
            elif operating_margins < 5.0:  # Stored as percentage
                negative_factors.append(f"Weak operating margins ({operating_margins:.1f}%)")
            
            return PillarScore(
                score=min(100.0, total_score),
                confidence=0.7,
                key_metrics={
                    "revenue_growth": revenue_growth,
                    "gross_margins": gross_margins,
                    "operating_margins": operating_margins,
                    "roe": roe
                },
                positive_factors=positive_factors,
                negative_factors=negative_factors,
                data_quality="Medium"
            )
            
        except Exception as e:
            logger.error(f"Growth prospects scoring failed for {ticker}: {e}")
            return PillarScore(50.0, 0.2, {}, [], [str(e)], "Low")
    
    async def _score_governance(self, ticker: str) -> PillarScore:
        """Score governance pillar (15% weight)"""
        try:
            governance_result = await analyze_corporate_governance(ticker)
            
            if "error" in governance_result:
                return PillarScore(50.0, 0.2, {}, [], [governance_result["error"]], "Low")
            
            governance_score = governance_result.get("governance_score", 50)
            red_flags = governance_result.get("red_flags", [])
            
            # Convert governance score (0-100) to pillar score
            pillar_score = governance_score
            
            # Identify key factors
            positive_factors = []
            negative_factors = []
            
            if governance_score >= 80:
                positive_factors.append("Strong corporate governance standards")
            elif governance_score < 60:
                negative_factors.append("Below-average governance quality")
            
            # Add red flag summaries
            critical_flags = [rf for rf in red_flags if rf["severity"] == "Critical"]
            high_flags = [rf for rf in red_flags if rf["severity"] == "High"]
            
            if critical_flags:
                negative_factors.extend([rf["description"][:50] + "..." for rf in critical_flags[:2]])
            if high_flags:
                negative_factors.extend([rf["description"][:50] + "..." for rf in high_flags[:1]])
            
            return PillarScore(
                score=pillar_score,
                confidence=0.7,
                key_metrics={
                    "governance_score": governance_score,
                    "governance_grade": governance_result.get("governance_grade", "C"),
                    "critical_red_flags": len(critical_flags),
                    "high_red_flags": len(high_flags)
                },
                positive_factors=positive_factors,
                negative_factors=negative_factors,
                data_quality="Medium"
            )
            
        except Exception as e:
            logger.error(f"Governance scoring failed for {ticker}: {e}")
            return PillarScore(50.0, 0.2, {}, [], [str(e)], "Low")
    
    async def _score_macro_sensitivity(self, ticker: str) -> PillarScore:
        """Score macro sensitivity pillar (10% weight)"""
        try:
            # This is a simplified implementation - would be enhanced with:
            # - Sector cyclicality analysis
            # - Interest rate sensitivity
            # - Commodity exposure
            # - Currency exposure
            # - Regulatory risk assessment
            
            fundamentals = await compute_fundamentals(ticker)
            
            # Basic macro sensitivity indicators
            debt_to_equity = fundamentals.get("debtToEquity", 0) or 0
            beta = 1.0  # Would fetch from market data
            
            score_components = {}
            
            # Interest rate sensitivity (debt levels)
            if debt_to_equity <= 30:
                score_components["interest_sensitivity"] = 30  # Low sensitivity
            elif debt_to_equity <= 60:
                score_components["interest_sensitivity"] = 25
            elif debt_to_equity <= 100:
                score_components["interest_sensitivity"] = 20
            else:
                score_components["interest_sensitivity"] = 15  # High sensitivity
            
            # Market volatility sensitivity (beta proxy)
            if beta <= 0.8:
                score_components["market_sensitivity"] = 25  # Defensive
            elif beta <= 1.2:
                score_components["market_sensitivity"] = 20  # Market-like
            else:
                score_components["market_sensitivity"] = 15  # High beta
            
            # Cyclicality assessment (simplified)
            # Would be enhanced with sector-specific analysis
            score_components["cyclicality"] = 20  # Neutral assumption
            
            # Regulatory risk (simplified)
            score_components["regulatory"] = 25  # Neutral assumption
            
            total_score = sum(score_components.values())
            
            positive_factors = []
            negative_factors = []
            
            if debt_to_equity <= 50:
                positive_factors.append("Low interest rate sensitivity")
            elif debt_to_equity > 100:
                negative_factors.append("High interest rate sensitivity")
            
            return PillarScore(
                score=min(100.0, total_score),
                confidence=0.5,  # Lower confidence due to simplified implementation
                key_metrics={
                    "debt_to_equity": debt_to_equity,
                    "estimated_beta": beta
                },
                positive_factors=positive_factors,
                negative_factors=negative_factors,
                data_quality="Low"  # Would be improved with more data sources
            )
            
        except Exception as e:
            logger.error(f"Macro sensitivity scoring failed for {ticker}: {e}")
            return PillarScore(50.0, 0.2, {}, [], [str(e)], "Low")
    
    async def _identify_sector(self, ticker: str) -> Optional[str]:
        """Identify company sector (simplified implementation)"""
        try:
            # Would be enhanced with proper sector classification
            # For now, return None to skip sector adjustments
            return None
        except:
            return None
    
    def _apply_sector_adjustments(self, pillar_scores: Dict[str, PillarScore], sector: str) -> Dict[str, PillarScore]:
        """Apply sector-specific scoring adjustments"""
        if sector not in self.sector_adjustments:
            return pillar_scores
        
        adjustments = self.sector_adjustments[sector]
        
        for pillar_name, adjustment_factor in adjustments.items():
            if pillar_name in pillar_scores:
                original_score = pillar_scores[pillar_name].score
                adjusted_score = min(100.0, original_score * adjustment_factor)
                pillar_scores[pillar_name].score = adjusted_score
        
        return pillar_scores
    
    def _calculate_weighted_score(self, pillar_scores: Dict[str, PillarScore]) -> float:
        """Calculate weighted overall score"""
        weighted_sum = (
            pillar_scores["financial_health"].score * self.weights.financial_health +
            pillar_scores["valuation"].score * self.weights.valuation +
            pillar_scores["growth_prospects"].score * self.weights.growth_prospects +
            pillar_scores["governance"].score * self.weights.governance +
            pillar_scores["macro_sensitivity"].score * self.weights.macro_sensitivity
        )
        
        return round(weighted_sum, 1)
    
    def _calculate_overall_confidence(self, pillar_scores: Dict[str, PillarScore]) -> float:
        """Calculate weighted overall confidence"""
        weighted_confidence = (
            pillar_scores["financial_health"].confidence * self.weights.financial_health +
            pillar_scores["valuation"].confidence * self.weights.valuation +
            pillar_scores["growth_prospects"].confidence * self.weights.growth_prospects +
            pillar_scores["governance"].confidence * self.weights.governance +
            pillar_scores["macro_sensitivity"].confidence * self.weights.macro_sensitivity
        )
        
        return round(weighted_confidence, 2)
    
    def _generate_recommendation(self, overall_score: float, pillar_scores: Dict[str, PillarScore]) -> str:
        """Generate investment recommendation"""
        # Base recommendation on score
        if overall_score >= 80:
            base_rec = "Strong Buy"
        elif overall_score >= 70:
            base_rec = "Buy"
        elif overall_score >= 60:
            base_rec = "Hold"
        elif overall_score >= 50:
            base_rec = "Weak Hold"
        else:
            base_rec = "Sell"
        
        # Adjust for specific red flags
        governance_score = pillar_scores["governance"].score
        if governance_score < 40:
            if base_rec in ["Strong Buy", "Buy"]:
                base_rec = "Hold"  # Downgrade due to governance issues
        
        valuation_score = pillar_scores["valuation"].score
        if valuation_score < 30:  # Severely overvalued
            if base_rec in ["Strong Buy", "Buy"]:
                base_rec = "Hold"
        
        return base_rec
    
    async def _calculate_trading_parameters(
        self, 
        ticker: str, 
        overall_score: float, 
        pillar_scores: Dict[str, PillarScore],
        current_price: Optional[float]
    ) -> Dict[str, Any]:
        """Calculate trading parameters"""
        
        # Position sizing based on score and confidence
        confidence = self._calculate_overall_confidence(pillar_scores)
        
        if overall_score >= 80 and confidence >= 0.7:
            position_sizing = 7.0  # 7% of portfolio
        elif overall_score >= 70 and confidence >= 0.6:
            position_sizing = 5.0  # 5% of portfolio
        elif overall_score >= 60:
            position_sizing = 3.0  # 3% of portfolio
        else:
            position_sizing = 1.0  # 1% of portfolio (minimal exposure)
        
        # Entry zone, target, and stop loss
        # Use technical analysis for entry zone, DCF for target/stop
        valuation_metrics = pillar_scores["valuation"].key_metrics
        intrinsic_value = valuation_metrics.get("intrinsic_value", 0)
        
        try:
            # Get technical analysis data for proper entry zone calculation
            from app.tools.finance import fetch_ohlcv
            from app.graph.nodes.technicals import _calculate_support_resistance, _calculate_entry_zone
            
            # Fetch OHLCV data for technical analysis
            df = await fetch_ohlcv(ticker)
            if not df.empty and len(df) >= 20:
                # Extract OHLC data
                if isinstance(df.columns, pd.MultiIndex):
                    def pick(col: str):
                        cols = [c for c in df.columns if isinstance(c, tuple) and col in c]
                        if cols:
                            series = df[cols[0]]
                            if isinstance(series, pd.DataFrame):
                                series = series.iloc[:, 0]
                            return series
                        return None
                    high_s = pick("High")
                    low_s = pick("Low")
                    close_s = pick("Close")
                else:
                    high_s = df["High"] if "High" in df.columns else None
                    low_s = df["Low"] if "Low" in df.columns else None
                    close_s = df["Close"] if "Close" in df.columns else None
                
                # Calculate support/resistance and entry zone
                support_levels, resistance_levels = _calculate_support_resistance(high_s, low_s, close_s)
                
                # Calculate moving averages for regime detection
                if close_s is not None:
                    c = close_s.astype(float).ffill().bfill()
                    sma20 = c.rolling(20).mean().iloc[-1] if len(c) >= 20 else None
                    sma50 = c.rolling(50).mean().iloc[-1] if len(c) >= 50 else None
                else:
                    sma20 = sma50 = None
                
                # Calculate technical entry zone
                tech_entry_zone = _calculate_entry_zone(current_price, support_levels, resistance_levels, sma20, sma50)
                
                entry_zone = (tech_entry_zone["entry_zone_low"], tech_entry_zone["entry_zone_high"])
                entry_explanation = tech_entry_zone["explanation"]
                
                logger.info(f"Using technical analysis entry zone for {ticker}: {entry_zone} - {entry_explanation}")
                
            else:
                # Fallback to DCF-based calculation if no technical data
                logger.warning(f"Insufficient technical data for {ticker}, falling back to DCF-based entry zone")
                entry_zone, entry_explanation = await self._fallback_entry_zone_calculation(ticker, current_price, intrinsic_value)
                
        except Exception as e:
            logger.warning(f"Error in technical analysis for {ticker}: {e}, using fallback")
            entry_zone, entry_explanation = await self._fallback_entry_zone_calculation(ticker, current_price, intrinsic_value)
        
        # Get DCF target price and stop loss (these are still useful)
        try:
            dcf_result = await perform_dcf_valuation(ticker, current_price)
            if "error" not in dcf_result:
                target_price = dcf_result.get("target_price", 0)
                stop_loss = dcf_result.get("stop_loss", 0)
                logger.info(f"Using DCF target/stop for {ticker}: target={target_price}, stop={stop_loss}")
            else:
                # Fallback target and stop loss
                if current_price:
                    target_price = current_price * 1.25
                    stop_loss = current_price * 0.85
                else:
                    target_price = 0.0
                    stop_loss = 0.0
        except Exception as e:
            logger.warning(f"DCF calculation failed for {ticker}: {e}")
            if current_price:
                target_price = current_price * 1.25
                stop_loss = current_price * 0.85
            else:
                target_price = 0.0
                stop_loss = 0.0
        
        # Time horizon based on score quality
        if overall_score >= 75:
            time_horizon = 18  # 18 months for high-quality stocks
        elif overall_score >= 60:
            time_horizon = 12  # 12 months
        else:
            time_horizon = 6   # 6 months for lower quality
        
        return {
            "position_sizing": position_sizing,
            "entry_zone": entry_zone,
            "entry_explanation": entry_explanation,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "time_horizon": time_horizon
        }
    
    async def _fallback_entry_zone_calculation(self, ticker: str, current_price: Optional[float], intrinsic_value: float) -> tuple:
        """Fallback entry zone calculation using DCF or price-based methods"""
        try:
            dcf_result = await perform_dcf_valuation(ticker, current_price)
            if "error" not in dcf_result:
                dcf_buy_zone = dcf_result.get("buy_zone", 0)
                if dcf_buy_zone and dcf_buy_zone > 0:
                    entry_zone = (dcf_buy_zone * 0.95, dcf_buy_zone * 1.05)
                    explanation = f"Fallback: DCF-based entry zone around buy zone ₹{dcf_buy_zone:.2f}"
                    return entry_zone, explanation
            
            # Fallback to intrinsic value
            if intrinsic_value > 0:
                entry_zone = (intrinsic_value * 0.8, intrinsic_value * 0.95)
                explanation = f"Fallback: Intrinsic value-based entry zone ₹{entry_zone[0]:.2f}-₹{entry_zone[1]:.2f} (20% below to 5% below intrinsic value)"
                return entry_zone, explanation
            
            # Final fallback
            if current_price and current_price > 0:
                entry_zone = (current_price * 0.9, current_price * 1.05)
                explanation = f"Fallback: Conservative entry zone ₹{entry_zone[0]:.2f}-₹{entry_zone[1]:.2f} (10% below to 5% above current price)"
                return entry_zone, explanation
            else:
                return (0.0, 0.0), "Insufficient data for entry zone calculation"
                
        except Exception as e:
            logger.error(f"Fallback entry zone calculation failed for {ticker}: {e}")
            if current_price and current_price > 0:
                entry_zone = (current_price * 0.9, current_price * 1.05)
                return entry_zone, f"Emergency fallback: ₹{entry_zone[0]:.2f}-₹{entry_zone[1]:.2f}"
            else:
                return (0.0, 0.0), "Emergency fallback: No price data available"
    
    def _assess_risk_factors(self, pillar_scores: Dict[str, PillarScore]) -> Dict[str, Any]:
        """Assess overall risk factors and catalysts"""
        
        # Risk rating based on pillar scores
        financial_health = pillar_scores["financial_health"].score
        governance = pillar_scores["governance"].score
        
        if financial_health < 40 or governance < 40:
            risk_rating = "Very High"
        elif financial_health < 60 or governance < 60:
            risk_rating = "High"
        elif financial_health < 75 and governance < 75:
            risk_rating = "Medium"
        else:
            risk_rating = "Low"
        
        # Aggregate key risks
        key_risks = []
        for pillar in pillar_scores.values():
            key_risks.extend(pillar.negative_factors[:2])  # Top 2 from each pillar
        
        # Aggregate key catalysts (positive factors)
        key_catalysts = []
        for pillar in pillar_scores.values():
            key_catalysts.extend(pillar.positive_factors[:2])  # Top 2 from each pillar
        
        return {
            "risk_rating": risk_rating,
            "key_risks": key_risks[:5],  # Top 5 risks
            "key_catalysts": key_catalysts[:5]  # Top 5 catalysts
        }
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numerical score to letter grade"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 55:
            return "C"
        elif score >= 50:
            return "C-"
        elif score >= 45:
            return "D+"
        elif score >= 40:
            return "D"
        else:
            return "F"


# Convenience function for integration
async def score_stock_comprehensively(
    ticker: str, 
    current_price: Optional[float] = None,
    custom_weights: Optional[ScoringWeights] = None
) -> ComprehensiveScore:
    """Perform comprehensive stock scoring and analysis"""
    engine = ComprehensiveScoringEngine(custom_weights)
    return await engine.score_ticker(ticker, current_price)





