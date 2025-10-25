"""
Institutional-Grade Equity Research Output Schemas
Phase 1: Core Investment Framework Enhancement
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class RecommendationType(str, Enum):
    """Standard investment recommendation types"""
    STRONG_BUY = "Strong Buy"
    BUY = "Buy"
    HOLD = "Hold"
    WEAK_HOLD = "Weak Hold"
    SELL = "Sell"
    STRONG_SELL = "Strong Sell"
    AVOID = "Avoid"


class ConvictionLevel(str, Enum):
    """Investment conviction levels"""
    VERY_HIGH = "Very High"
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"
    VERY_LOW = "Very Low"


class GradeLevel(str, Enum):
    """Investment grade levels"""
    A_PLUS = "A+"
    A = "A"
    A_MINUS = "A-"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    C_MINUS = "C-"
    D_PLUS = "D+"
    D = "D"
    D_MINUS = "D-"
    F = "F"


class TimeHorizon(str, Enum):
    """Analysis time horizons"""
    SHORT_TERM = "Short-term (0-6 months)"
    MEDIUM_TERM = "Medium-term (6-18 months)"
    LONG_TERM = "Long-term (18+ months)"


class InstitutionalInvestmentSummary(BaseModel):
    """
    Institutional-grade investment summary with professional standards
    """
    # Core Recommendation
    recommendation: RecommendationType
    confidence_score: float = Field(ge=0, le=100, description="Confidence score 0-100")
    conviction_level: ConvictionLevel
    
    # Professional Grading
    letter_grade: GradeLevel
    stars_rating: str = Field(pattern=r"^★{1,5}☆{0,4}$", description="1-5 star rating")
    
    # Executive Summary (≤150 words)
    executive_summary: str = Field(max_length=800, description="Professional executive summary")
    
    # Horizon-Specific Analysis
    short_term_outlook: str = Field(description="0-6 month outlook with reasoning")
    long_term_outlook: str = Field(description="12-36 month outlook with reasoning")
    
    # Investment Rationale
    key_investment_thesis: List[str] = Field(description="Top 3-5 investment drivers")
    key_risks: List[str] = Field(description="Top 3-5 risk factors")
    
    # Quantitative Evidence
    quantitative_score: float = Field(ge=0, le=100, description="Quantitative analysis score")
    qualitative_score: float = Field(ge=0, le=100, description="Qualitative analysis score")
    
    # Professional Context
    analyst_notes: str = Field(description="Senior analyst professional notes")
    last_updated: datetime = Field(default_factory=datetime.now)
    
    # Metadata
    analysis_version: str = Field(default="1.0")
    data_quality_score: float = Field(ge=0, le=100, description="Data quality assessment")


class ValuationMetrics(BaseModel):
    """
    Comprehensive valuation metrics for institutional analysis
    """
    # Current Market Data
    current_price: Optional[float] = Field(description="Current Market Price (CMP)")
    currency: str = Field(default="USD")
    market_cap: Optional[float] = Field(default=None, description="Market Capitalization")
    enterprise_value: Optional[float] = Field(default=None, description="Enterprise Value")
    
    # Price Targets
    analyst_consensus_target: Optional[float] = Field(default=None, description="Analyst consensus price target")
    analyst_target_range_low: Optional[float] = Field(default=None, description="Low end of analyst range")
    analyst_target_range_high: Optional[float] = Field(default=None, description="High end of analyst range")
    analyst_target_count: Optional[int] = Field(default=None, description="Number of analyst targets")
    
    # DCF Valuation
    dcf_intrinsic_value_base: Optional[float] = Field(default=None, description="DCF intrinsic value (base case)")
    dcf_intrinsic_value_bear: Optional[float] = Field(default=None, description="DCF intrinsic value (bear case)")
    dcf_intrinsic_value_bull: Optional[float] = Field(default=None, description="DCF intrinsic value (bull case)")
    
    # Expected Returns
    expected_return_short_term: Optional[float] = Field(default=None, description="Expected return (0-6 months)")
    expected_return_long_term: Optional[float] = Field(default=None, description="Expected return (12-36 months)")
    expected_return_source: str = Field(default="Analysis pending", description="Source of expected return calculation")
    
    # Upside/Downside Analysis
    upside_vs_intrinsic: Optional[float] = Field(default=None, description="Upside vs DCF intrinsic value (%)")
    upside_vs_consensus: Optional[float] = Field(default=None, description="Upside vs analyst consensus (%)")
    downside_risk: Optional[float] = Field(default=None, description="Downside risk assessment (%)")
    
    # Trading Levels
    entry_zone_low: Optional[float] = Field(default=None, description="Recommended entry zone (low)")
    entry_zone_high: Optional[float] = Field(default=None, description="Recommended entry zone (high)")
    target_price: Optional[float] = Field(default=None, description="Target price")
    stop_loss: Optional[float] = Field(default=None, description="Stop loss level")
    
    # Risk Metrics
    volatility_1y: Optional[float] = Field(default=None, description="1-year volatility")
    beta: Optional[float] = Field(default=None, description="Beta vs market")
    sharpe_ratio: Optional[float] = Field(default=None, description="Sharpe ratio")
    
    # Valuation Context
    valuation_percentile: Optional[float] = Field(default=None, description="Valuation percentile vs peers")
    valuation_attractiveness: str = Field(default="Analysis pending", description="Valuation attractiveness assessment")


class HorizonAnalysis(BaseModel):
    """
    Time horizon-specific analysis framework
    """
    horizon: TimeHorizon
    recommendation: RecommendationType
    confidence_score: float = Field(ge=0, le=100)
    
    # Key Drivers for this Horizon
    primary_drivers: List[str] = Field(description="Primary drivers for this horizon")
    key_catalysts: List[str] = Field(description="Key catalysts expected")
    risk_factors: List[str] = Field(description="Risk factors for this horizon")
    
    # Quantitative Metrics
    expected_return: Optional[float] = Field(description="Expected return for this horizon")
    probability_of_success: Optional[float] = Field(ge=0, le=100, description="Probability of achieving target")
    
    # Professional Analysis
    analyst_outlook: str = Field(description="Professional outlook for this horizon")
    key_monitoring_points: List[str] = Field(description="Key metrics to monitor")


class InstitutionalDecision(BaseModel):
    """
    Enhanced decision framework for institutional-grade analysis
    """
    # Core Decision
    investment_summary: InstitutionalInvestmentSummary
    valuation_metrics: ValuationMetrics
    
    # Horizon Analysis
    short_term_analysis: HorizonAnalysis
    long_term_analysis: HorizonAnalysis
    
    # Professional Context
    sector_outlook: str = Field(description="Sector outlook context")
    market_regime: str = Field(description="Current market regime assessment")
    
    # Risk Assessment
    overall_risk_rating: str = Field(description="Overall risk rating")
    position_sizing_recommendation: str = Field(description="Position sizing recommendation")
    
    # Professional Standards
    compliance_notes: str = Field(description="Compliance and regulatory notes")
    disclaimer: str = Field(description="Professional disclaimer")


class InstitutionalTickerReport(BaseModel):
    """
    Enhanced ticker report with institutional-grade structure
    """
    # Basic Information
    ticker: str
    company_name: str
    sector: str
    country: str
    exchange: str
    
    # Core Analysis
    decision: InstitutionalDecision
    
    # Analysis Sections (Enhanced)
    news_sentiment: SectionScore
    youtube_sentiment: SectionScore
    technicals: SectionScore
    fundamentals: SectionScore
    peer_analysis: SectionScore
    analyst_recommendations: SectionScore
    cashflow: SectionScore
    leadership: SectionScore
    sector_macro: SectionScore
    growth_prospects: SectionScore
    valuation: SectionScore
    strategic_conviction: Optional[SectionScore] = None
    earnings_call_analysis: Optional[Dict[str, Any]] = None
    sector_rotation: Optional[SectionScore] = None
    comprehensive_fundamentals: Optional[ComprehensiveFundamentals] = None
    
    # Professional Metadata
    report_generated_at: datetime = Field(default_factory=datetime.now)
    analyst_name: str = Field(default="Equisense AI Research")
    report_version: str = Field(default="1.0")
    data_sources: List[str] = Field(description="Data sources used")
    
    # Export Capabilities
    export_formats: List[str] = Field(default=["markdown", "csv", "json"])
    chart_data: Optional[Dict[str, Any]] = Field(description="Chart data for visualization")


class InstitutionalResearchResponse(BaseModel):
    """
    Enhanced research response with institutional-grade structure
    """
    # Request Information
    tickers: List[str]
    analysis_horizon_short_days: int
    analysis_horizon_long_days: int
    
    # Reports
    reports: List[InstitutionalTickerReport]
    
    # Professional Metadata
    generated_at: datetime = Field(default_factory=datetime.now)
    analysis_framework_version: str = Field(default="Institutional v1.0")
    data_quality_summary: Dict[str, Any] = Field(description="Overall data quality assessment")
    
    # Export Information
    available_exports: List[str] = Field(default=["markdown", "csv", "pdf", "json"])
    export_timestamp: datetime = Field(default_factory=datetime.now)


# Re-export existing schemas for compatibility
from .output import SectionScore, ComprehensiveFundamentals

__all__ = [
    "InstitutionalInvestmentSummary",
    "ValuationMetrics", 
    "HorizonAnalysis",
    "InstitutionalDecision",
    "InstitutionalTickerReport",
    "InstitutionalResearchResponse",
    "RecommendationType",
    "ConvictionLevel", 
    "GradeLevel",
    "TimeHorizon"
]
