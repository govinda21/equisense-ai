"""
Institutional-Grade Investment Summary Engine
Phase 1: Core Investment Framework Implementation
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import asyncio

from app.schemas.institutional_output import (
    InstitutionalInvestmentSummary,
    ValuationMetrics,
    HorizonAnalysis,
    InstitutionalDecision,
    RecommendationType,
    ConvictionLevel,
    GradeLevel,
    TimeHorizon
)
from app.schemas.output import SectionScore

logger = logging.getLogger(__name__)


class InstitutionalInvestmentEngine:
    """
    Professional investment analysis engine for institutional-grade research
    """
    
    def __init__(self):
        self.confidence_thresholds = {
            "very_high": 85,
            "high": 70,
            "moderate": 55,
            "low": 40,
            "very_low": 25
        }
        
        self.grade_criteria = {
            GradeLevel.A_PLUS: {"min_score": 90, "description": "Exceptional investment quality"},
            GradeLevel.A: {"min_score": 85, "description": "Excellent investment quality"},
            GradeLevel.A_MINUS: {"min_score": 80, "description": "Very good investment quality"},
            GradeLevel.B_PLUS: {"min_score": 75, "description": "Good investment quality"},
            GradeLevel.B: {"min_score": 70, "description": "Above average investment quality"},
            GradeLevel.B_MINUS: {"min_score": 65, "description": "Average investment quality"},
            GradeLevel.C_PLUS: {"min_score": 60, "description": "Below average investment quality"},
            GradeLevel.C: {"min_score": 55, "description": "Poor investment quality"},
            GradeLevel.C_MINUS: {"min_score": 50, "description": "Very poor investment quality"},
            GradeLevel.D_PLUS: {"min_score": 45, "description": "Speculative investment quality"},
            GradeLevel.D: {"min_score": 40, "description": "Highly speculative investment quality"},
            GradeLevel.D_MINUS: {"min_score": 35, "description": "Extremely speculative investment quality"},
            GradeLevel.F: {"min_score": 0, "description": "Very poor investment quality"}
        }
    
    async def generate_institutional_summary(
        self,
        ticker: str,
        analysis_data: Dict[str, Any],
        short_term_days: int = 180,
        long_term_days: int = 1095
    ) -> InstitutionalDecision:
        """
        Generate institutional-grade investment summary
        
        Args:
            ticker: Stock ticker symbol
            analysis_data: Comprehensive analysis data from all nodes
            short_term_days: Short-term analysis horizon in days
            long_term_days: Long-term analysis horizon in days
            
        Returns:
            InstitutionalDecision with professional investment summary
        """
        try:
            # Extract key metrics from analysis data
            composite_score = analysis_data.get("composite_score", 0.5)
            confidences = analysis_data.get("confidences", {})
            decision_data = analysis_data.get("decision", {})
            
            # Calculate professional metrics
            confidence_score = self._calculate_confidence_score(confidences)
            conviction_level = self._determine_conviction_level(composite_score, confidence_score)
            recommendation = self._determine_recommendation(composite_score, conviction_level)
            letter_grade = self._determine_letter_grade(composite_score)
            
            # Generate investment summary
            investment_summary = await self._create_investment_summary(
                ticker, composite_score, confidence_score, conviction_level,
                recommendation, letter_grade, analysis_data
            )
            
            # Generate valuation metrics
            valuation_metrics = await self._create_valuation_metrics(
                ticker, analysis_data, decision_data
            )
            
            # Generate horizon-specific analysis
            short_term_analysis = await self._create_horizon_analysis(
                TimeHorizon.SHORT_TERM, composite_score, confidence_score,
                analysis_data, short_term_days
            )
            
            long_term_analysis = await self._create_horizon_analysis(
                TimeHorizon.LONG_TERM, composite_score, confidence_score,
                analysis_data, long_term_days
            )
            
            # Create institutional decision
            institutional_decision = InstitutionalDecision(
                investment_summary=investment_summary,
                valuation_metrics=valuation_metrics,
                short_term_analysis=short_term_analysis,
                long_term_analysis=long_term_analysis,
                sector_outlook=analysis_data.get("sector_macro", {}).get("summary", "Sector analysis pending"),
                market_regime=analysis_data.get("market_regime", "Mixed"),
                overall_risk_rating=self._assess_overall_risk(analysis_data),
                position_sizing_recommendation=self._recommend_position_sizing(composite_score, conviction_level),
                compliance_notes="This analysis is for informational purposes only and does not constitute investment advice.",
                disclaimer="Past performance does not guarantee future results. Please consult with a qualified financial advisor."
            )
            
            logger.info(f"Generated institutional summary for {ticker} with grade {letter_grade}")
            return institutional_decision
            
        except Exception as e:
            logger.error(f"Error generating institutional summary for {ticker}: {str(e)}")
            # Return default institutional decision
            return await self._create_default_decision(ticker)
    
    def _calculate_confidence_score(self, confidences: Dict[str, float]) -> float:
        """Calculate overall confidence score from section confidences"""
        if not confidences:
            return 50.0
        
        # Weight different sections based on importance
        weights = {
            "fundamentals": 0.25,
            "valuation": 0.20,
            "growth_prospects": 0.15,
            "technicals": 0.10,
            "news_sentiment": 0.10,
            "peer_analysis": 0.10,
            "sector_macro": 0.10
        }
        
        weighted_confidence = 0.0
        total_weight = 0.0
        
        for section, confidence in confidences.items():
            weight = weights.get(section, 0.05)
            weighted_confidence += confidence * weight * 100  # Convert to 0-100 scale
            total_weight += weight
        
        return weighted_confidence / total_weight if total_weight > 0 else 50.0
    
    def _determine_conviction_level(self, composite_score: float, confidence_score: float) -> ConvictionLevel:
        """Determine conviction level based on score and confidence"""
        # Combine composite score and confidence
        conviction_score = (composite_score * 100 + confidence_score) / 2
        
        if conviction_score >= 85:
            return ConvictionLevel.VERY_HIGH
        elif conviction_score >= 70:
            return ConvictionLevel.HIGH
        elif conviction_score >= 55:
            return ConvictionLevel.MODERATE
        elif conviction_score >= 40:
            return ConvictionLevel.LOW
        else:
            return ConvictionLevel.VERY_LOW
    
    def _determine_recommendation(self, composite_score: float, conviction_level: ConvictionLevel) -> RecommendationType:
        """Determine investment recommendation based on score and conviction"""
        score_thresholds = {
            ConvictionLevel.VERY_HIGH: {"buy": 0.7, "strong_buy": 0.8},
            ConvictionLevel.HIGH: {"buy": 0.6, "strong_buy": 0.75},
            ConvictionLevel.MODERATE: {"hold": 0.4, "buy": 0.6, "weak_hold": 0.3},
            ConvictionLevel.LOW: {"hold": 0.3, "weak_hold": 0.2, "sell": 0.1},
            ConvictionLevel.VERY_LOW: {"sell": 0.2, "strong_sell": 0.1, "avoid": 0.05}
        }
        
        thresholds = score_thresholds.get(conviction_level, score_thresholds[ConvictionLevel.MODERATE])
        
        if composite_score >= thresholds.get("strong_buy", 0.8):
            return RecommendationType.STRONG_BUY
        elif composite_score >= thresholds.get("buy", 0.6):
            return RecommendationType.BUY
        elif composite_score >= thresholds.get("hold", 0.4):
            return RecommendationType.HOLD
        elif composite_score >= thresholds.get("weak_hold", 0.3):
            return RecommendationType.WEAK_HOLD
        elif composite_score >= thresholds.get("sell", 0.2):
            return RecommendationType.SELL
        elif composite_score >= thresholds.get("strong_sell", 0.1):
            return RecommendationType.STRONG_SELL
        else:
            return RecommendationType.AVOID
    
    def _determine_letter_grade(self, composite_score: float) -> GradeLevel:
        """Determine letter grade based on composite score"""
        score_percentage = composite_score * 100
        
        for grade, criteria in self.grade_criteria.items():
            if score_percentage >= criteria["min_score"]:
                return grade
        
        return GradeLevel.F
    
    async def _create_investment_summary(
        self,
        ticker: str,
        composite_score: float,
        confidence_score: float,
        conviction_level: ConvictionLevel,
        recommendation: RecommendationType,
        letter_grade: GradeLevel,
        analysis_data: Dict[str, Any]
    ) -> InstitutionalInvestmentSummary:
        """Create professional investment summary"""
        
        # Generate executive summary
        executive_summary = await self._generate_executive_summary(
            ticker, recommendation, composite_score, analysis_data
        )
        
        # Extract key investment thesis and risks
        key_thesis = self._extract_investment_thesis(analysis_data)
        key_risks = self._extract_key_risks(analysis_data)
        
        # Calculate quantitative and qualitative scores
        quantitative_score = self._calculate_quantitative_score(analysis_data)
        qualitative_score = self._calculate_qualitative_score(analysis_data)
        
        # Generate stars rating
        stars_rating = self._generate_stars_rating(composite_score)
        
        return InstitutionalInvestmentSummary(
            recommendation=recommendation,
            confidence_score=confidence_score,
            conviction_level=conviction_level,
            letter_grade=letter_grade,
            stars_rating=stars_rating,
            executive_summary=executive_summary,
            short_term_outlook="Analysis in progress - short-term outlook being generated",
            long_term_outlook="Analysis in progress - long-term outlook being generated",
            key_investment_thesis=key_thesis,
            key_risks=key_risks,
            quantitative_score=quantitative_score,
            qualitative_score=qualitative_score,
            analyst_notes=f"Professional analysis of {ticker} based on comprehensive multi-dimensional assessment",
            data_quality_score=self._assess_data_quality(analysis_data)
        )
    
    async def _create_valuation_metrics(
        self,
        ticker: str,
        analysis_data: Dict[str, Any],
        decision_data: Dict[str, Any]
    ) -> ValuationMetrics:
        """Create comprehensive valuation metrics"""
        
        # Extract current market data
        fundamentals = analysis_data.get("fundamentals", {}).get("details", {})
        valuation = analysis_data.get("valuation", {}).get("details", {})
        
        current_price = fundamentals.get("current_price")
        market_cap = fundamentals.get("market_cap")
        
        # Extract DCF values
        dcf_intrinsic_value_base = valuation.get("dcf_intrinsic_value")
        
        # Extract analyst targets
        analyst_data = analysis_data.get("analyst_recommendations", {}).get("details", {})
        analyst_target = analyst_data.get("target_price")
        
        # Calculate expected returns
        expected_return_short = decision_data.get("expected_return_short", 0)
        expected_return_long = decision_data.get("expected_return_long", 0)
        
        # Calculate upside/downside
        upside_vs_intrinsic = None
        upside_vs_consensus = None
        
        if current_price and dcf_intrinsic_value_base:
            upside_vs_intrinsic = ((dcf_intrinsic_value_base - current_price) / current_price) * 100
        
        if current_price and analyst_target:
            upside_vs_consensus = ((analyst_target - current_price) / current_price) * 100
        
        return ValuationMetrics(
            current_price=current_price,
            currency="USD",  # Will be enhanced to detect currency
            market_cap=market_cap,
            analyst_consensus_target=analyst_target,
            dcf_intrinsic_value_base=dcf_intrinsic_value_base,
            expected_return_short_term=expected_return_short,
            expected_return_long_term=expected_return_long,
            expected_return_source="Multi-model analysis",
            upside_vs_intrinsic=upside_vs_intrinsic,
            upside_vs_consensus=upside_vs_consensus,
            valuation_percentile=self._calculate_valuation_percentile(analysis_data),
            valuation_attractiveness=self._assess_valuation_attractiveness(upside_vs_intrinsic)
        )
    
    async def _create_horizon_analysis(
        self,
        horizon: TimeHorizon,
        composite_score: float,
        confidence_score: float,
        analysis_data: Dict[str, Any],
        horizon_days: int
    ) -> HorizonAnalysis:
        """Create horizon-specific analysis"""
        
        # Determine recommendation for this horizon
        horizon_adjustment = self._get_horizon_adjustment(horizon, horizon_days)
        adjusted_score = composite_score * horizon_adjustment
        
        recommendation = self._determine_recommendation(adjusted_score, ConvictionLevel.MODERATE)
        
        # Extract horizon-specific drivers
        primary_drivers = self._extract_horizon_drivers(horizon, analysis_data)
        key_catalysts = self._extract_horizon_catalysts(horizon, analysis_data)
        risk_factors = self._extract_horizon_risks(horizon, analysis_data)
        
        return HorizonAnalysis(
            horizon=horizon,
            recommendation=recommendation,
            confidence_score=confidence_score * horizon_adjustment,
            primary_drivers=primary_drivers,
            key_catalysts=key_catalysts,
            risk_factors=risk_factors,
            expected_return=self._calculate_horizon_return(horizon, analysis_data),
            probability_of_success=self._calculate_success_probability(adjusted_score),
            analyst_outlook=f"Professional {horizon.value.lower()} outlook based on comprehensive analysis",
            key_monitoring_points=self._get_monitoring_points(horizon, analysis_data)
        )
    
    def _get_horizon_adjustment(self, horizon: TimeHorizon, horizon_days: int) -> float:
        """Get score adjustment factor for different horizons"""
        if horizon == TimeHorizon.SHORT_TERM:
            return 0.9  # Slightly more conservative for short-term
        elif horizon == TimeHorizon.LONG_TERM:
            return 1.1  # Slightly more optimistic for long-term
        else:
            return 1.0
    
    def _extract_investment_thesis(self, analysis_data: Dict[str, Any]) -> List[str]:
        """Extract key investment thesis points"""
        thesis_points = []
        
        # Extract from growth prospects
        growth = analysis_data.get("growth_prospects", {}).get("details", {})
        if growth.get("summary"):
            thesis_points.append(f"Growth prospects: {growth['summary'][:100]}...")
        
        # Extract from fundamentals
        fundamentals = analysis_data.get("fundamentals", {}).get("details", {})
        if fundamentals.get("roe") and fundamentals["roe"] > 15:
            thesis_points.append(f"Strong ROE of {fundamentals['roe']:.1f}% indicates efficient capital utilization")
        
        # Extract from valuation
        valuation = analysis_data.get("valuation", {}).get("details", {})
        if valuation.get("dcf_intrinsic_value"):
            thesis_points.append("DCF analysis suggests attractive valuation")
        
        return thesis_points[:5]  # Limit to top 5 points
    
    def _extract_key_risks(self, analysis_data: Dict[str, Any]) -> List[str]:
        """Extract key risk factors"""
        risks = []
        
        # Extract from sector macro
        sector = analysis_data.get("sector_macro", {}).get("details", {})
        if sector.get("risks"):
            risks.extend(sector["risks"][:3])
        
        # Extract from fundamentals
        fundamentals = analysis_data.get("fundamentals", {}).get("details", {})
        if fundamentals.get("debt_to_equity") and fundamentals["debt_to_equity"] > 0.5:
            risks.append("Elevated debt levels increase financial risk")
        
        # Extract from technicals
        technicals = analysis_data.get("technicals", {}).get("details", {})
        if technicals.get("rsi") and technicals["rsi"] > 70:
            risks.append("Technical indicators suggest overbought conditions")
        
        return risks[:5]  # Limit to top 5 risks
    
    def _calculate_quantitative_score(self, analysis_data: Dict[str, Any]) -> float:
        """Calculate quantitative analysis score"""
        scores = []
        
        # Fundamentals score
        fundamentals = analysis_data.get("fundamentals", {}).get("confidence", 0.5)
        scores.append(fundamentals * 100)
        
        # Valuation score
        valuation = analysis_data.get("valuation", {}).get("confidence", 0.5)
        scores.append(valuation * 100)
        
        # Technical score
        technicals = analysis_data.get("technicals", {}).get("confidence", 0.5)
        scores.append(technicals * 100)
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _calculate_qualitative_score(self, analysis_data: Dict[str, Any]) -> float:
        """Calculate qualitative analysis score"""
        scores = []
        
        # Leadership score
        leadership = analysis_data.get("leadership", {}).get("confidence", 0.5)
        scores.append(leadership * 100)
        
        # Growth prospects score
        growth = analysis_data.get("growth_prospects", {}).get("confidence", 0.5)
        scores.append(growth * 100)
        
        # Sector macro score
        sector = analysis_data.get("sector_macro", {}).get("confidence", 0.5)
        scores.append(sector * 100)
        
        return sum(scores) / len(scores) if scores else 50.0
    
    def _generate_stars_rating(self, composite_score: float) -> str:
        """Generate stars rating based on composite score"""
        score_percentage = composite_score * 100
        
        if score_percentage >= 90:
            return "★★★★★"
        elif score_percentage >= 80:
            return "★★★★☆"
        elif score_percentage >= 70:
            return "★★★☆☆"
        elif score_percentage >= 60:
            return "★★☆☆☆"
        else:
            return "★☆☆☆☆"
    
    async def _generate_executive_summary(
        self,
        ticker: str,
        recommendation: RecommendationType,
        composite_score: float,
        analysis_data: Dict[str, Any]
    ) -> str:
        """Generate professional executive summary"""
        
        score_percentage = composite_score * 100
        
        summary = f"{ticker} receives a {recommendation.value} recommendation with a composite score of {score_percentage:.1f}/100. "
        
        # Add key insights
        fundamentals = analysis_data.get("fundamentals", {}).get("details", {})
        if fundamentals.get("roe"):
            summary += f"The company demonstrates strong operational efficiency with ROE of {fundamentals['roe']:.1f}%. "
        
        valuation = analysis_data.get("valuation", {}).get("details", {})
        if valuation.get("dcf_intrinsic_value"):
            summary += "DCF analysis indicates attractive valuation relative to current market price. "
        
        growth = analysis_data.get("growth_prospects", {}).get("summary", "")
        if growth:
            summary += f"Growth prospects appear {growth[:50]}... "
        
        summary += "Investors should consider this analysis alongside their risk tolerance and investment objectives."
        
        return summary[:800]  # Ensure it fits within the 800 character limit
    
    def _assess_data_quality(self, analysis_data: Dict[str, Any]) -> float:
        """Assess overall data quality"""
        confidences = analysis_data.get("confidences", {})
        if not confidences:
            return 50.0
        
        return sum(confidences.values()) / len(confidences) * 100
    
    def _assess_overall_risk(self, analysis_data: Dict[str, Any]) -> str:
        """Assess overall risk rating"""
        composite_score = analysis_data.get("composite_score", 0.5)
        
        if composite_score >= 0.8:
            return "Low Risk"
        elif composite_score >= 0.6:
            return "Moderate Risk"
        elif composite_score >= 0.4:
            return "High Risk"
        else:
            return "Very High Risk"
    
    def _recommend_position_sizing(self, composite_score: float, conviction_level: ConvictionLevel) -> str:
        """Recommend position sizing based on score and conviction"""
        if conviction_level == ConvictionLevel.VERY_HIGH and composite_score >= 0.8:
            return "Large position (5-10% of portfolio)"
        elif conviction_level == ConvictionLevel.HIGH and composite_score >= 0.7:
            return "Medium position (3-5% of portfolio)"
        elif conviction_level == ConvictionLevel.MODERATE and composite_score >= 0.5:
            return "Small position (1-3% of portfolio)"
        else:
            return "Avoid or minimal position (<1% of portfolio)"
    
    def _calculate_valuation_percentile(self, analysis_data: Dict[str, Any]) -> Optional[float]:
        """Calculate valuation percentile vs peers"""
        # This will be enhanced in Phase 2 with peer analysis
        return None
    
    def _assess_valuation_attractiveness(self, upside_vs_intrinsic: Optional[float]) -> str:
        """Assess valuation attractiveness"""
        if upside_vs_intrinsic is None:
            return "Analysis pending"
        elif upside_vs_intrinsic > 20:
            return "Very Attractive"
        elif upside_vs_intrinsic > 10:
            return "Attractive"
        elif upside_vs_intrinsic > 0:
            return "Fairly Valued"
        else:
            return "Overvalued"
    
    def _extract_horizon_drivers(self, horizon: TimeHorizon, analysis_data: Dict[str, Any]) -> List[str]:
        """Extract drivers specific to the horizon"""
        drivers = []
        
        if horizon == TimeHorizon.SHORT_TERM:
            drivers.append("Technical momentum and market sentiment")
            drivers.append("Upcoming earnings and guidance")
            drivers.append("Sector rotation dynamics")
        else:  # Long-term
            drivers.append("Fundamental business model strength")
            drivers.append("Competitive positioning and moats")
            drivers.append("Long-term growth prospects")
        
        return drivers
    
    def _extract_horizon_catalysts(self, horizon: TimeHorizon, analysis_data: Dict[str, Any]) -> List[str]:
        """Extract catalysts specific to the horizon"""
        catalysts = []
        
        if horizon == TimeHorizon.SHORT_TERM:
            catalysts.append("Earnings beat/miss expectations")
            catalysts.append("Management guidance updates")
            catalysts.append("Market sentiment shifts")
        else:  # Long-term
            catalysts.append("Strategic initiatives and expansion")
            catalysts.append("Industry consolidation opportunities")
            catalysts.append("Technology and innovation adoption")
        
        return catalysts
    
    def _extract_horizon_risks(self, horizon: TimeHorizon, analysis_data: Dict[str, Any]) -> List[str]:
        """Extract risks specific to the horizon"""
        risks = []
        
        if horizon == TimeHorizon.SHORT_TERM:
            risks.append("Volatility and market corrections")
            risks.append("Earnings disappointment risk")
            risks.append("Sector headwinds")
        else:  # Long-term
            risks.append("Competitive landscape changes")
            risks.append("Regulatory and policy risks")
            risks.append("Technology disruption risk")
        
        return risks
    
    def _calculate_horizon_return(self, horizon: TimeHorizon, analysis_data: Dict[str, Any]) -> Optional[float]:
        """Calculate expected return for the horizon"""
        decision_data = analysis_data.get("decision", {})
        
        if horizon == TimeHorizon.SHORT_TERM:
            return decision_data.get("expected_return_short")
        else:  # Long-term
            return decision_data.get("expected_return_long")
    
    def _calculate_success_probability(self, adjusted_score: float) -> float:
        """Calculate probability of achieving target return"""
        return min(95, max(5, adjusted_score * 100))
    
    def _get_monitoring_points(self, horizon: TimeHorizon, analysis_data: Dict[str, Any]) -> List[str]:
        """Get key monitoring points for the horizon"""
        points = []
        
        if horizon == TimeHorizon.SHORT_TERM:
            points.append("Technical support and resistance levels")
            points.append("Earnings calendar and guidance updates")
            points.append("Sector performance and rotation")
        else:  # Long-term
            points.append("Fundamental metrics and ratios")
            points.append("Competitive positioning changes")
            points.append("Management execution and strategy")
        
        return points
    
    async def _create_default_decision(self, ticker: str) -> InstitutionalDecision:
        """Create default decision when analysis fails"""
        return InstitutionalDecision(
            investment_summary=InstitutionalInvestmentSummary(
                recommendation=RecommendationType.HOLD,
                confidence_score=50.0,
                conviction_level=ConvictionLevel.MODERATE,
                letter_grade=GradeLevel.C,
                stars_rating="★★★☆☆",
                executive_summary=f"Analysis for {ticker} is pending. Please retry the analysis.",
                short_term_outlook="Analysis pending",
                long_term_outlook="Analysis pending",
                key_investment_thesis=["Analysis in progress"],
                key_risks=["Data availability limitations"],
                quantitative_score=50.0,
                qualitative_score=50.0,
                analyst_notes="Default analysis due to data limitations",
                data_quality_score=30.0
            ),
            valuation_metrics=ValuationMetrics(
                current_price=None,
                analyst_consensus_target=None,
                expected_return_source="Analysis pending"
            ),
            short_term_analysis=HorizonAnalysis(
                horizon=TimeHorizon.SHORT_TERM,
                recommendation=RecommendationType.HOLD,
                confidence_score=50.0,
                primary_drivers=["Analysis pending"],
                key_catalysts=["Analysis pending"],
                risk_factors=["Analysis pending"],
                analyst_outlook="Analysis pending"
            ),
            long_term_analysis=HorizonAnalysis(
                horizon=TimeHorizon.LONG_TERM,
                recommendation=RecommendationType.HOLD,
                confidence_score=50.0,
                primary_drivers=["Analysis pending"],
                key_catalysts=["Analysis pending"],
                risk_factors=["Analysis pending"],
                analyst_outlook="Analysis pending"
            ),
            sector_outlook="Analysis pending",
            market_regime="Unknown",
            overall_risk_rating="Unknown",
            position_sizing_recommendation="Analysis pending",
            compliance_notes="Analysis pending",
            disclaimer="Please retry analysis for complete results"
        )


# Global instance
institutional_engine = InstitutionalInvestmentEngine()
