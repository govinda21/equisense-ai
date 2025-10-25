from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SectionScore(BaseModel):
    summary: str
    confidence: float
    details: Dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    action: str
    rating: float
    expected_return_pct: float
    top_reasons_for: List[str]
    top_reasons_against: List[str]
    
    # Backward compatibility fields
    recommendation: Optional[str] = Field(default=None)  # Maps to action
    score: Optional[float] = Field(default=None)  # Maps to rating
    confidence_score: Optional[float] = Field(default=None)  # Confidence percentage
    
    # Professional equity research fields
    letter_grade: str = Field(default="C")
    stars: str = Field(default="★★★☆☆")
    professional_rationale: str = Field(default="Analysis based on current market conditions and fundamental metrics.")
    professional_recommendation: str = Field(default="")
    
    # Senior Equity Analyst Report Components
    executive_summary: str = Field(default="")
    financial_condition_summary: str = Field(default="")
    latest_performance_summary: str = Field(default="")
    key_trends: List[str] = Field(default_factory=list)
    
    # Investment thesis
    growth_drivers: List[str] = Field(default_factory=list)
    competitive_advantages: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)
    
    # Investment justification
    quantitative_evidence: Dict[str, Any] = Field(default_factory=dict)
    key_ratios_summary: str = Field(default="")
    recent_developments: List[str] = Field(default_factory=list)
    industry_context: str = Field(default="")
    
    # Outlook and targets
    short_term_outlook: str = Field(default="")
    long_term_outlook: str = Field(default="")
    price_target_12m: Optional[float] = None
    price_target_source: str = Field(default="")
    valuation_benchmark: str = Field(default="")
    
    # Debug and metadata fields (optional)
    llm_parsed: bool = Field(default=False)
    base_score: float = Field(default=0.5)
    debug_test: str = Field(default="")


class ComprehensiveFundamentals(BaseModel):
    """Comprehensive fundamental analysis results"""
    overall_score: float
    overall_grade: str
    recommendation: str
    confidence_level: float
    
    # DCF Valuation
    intrinsic_value: Optional[float] = None
    margin_of_safety: Optional[float] = None
    upside_potential: Optional[float] = None
    
    # Pillar scores
    financial_health_score: float
    valuation_score: float
    growth_prospects_score: float
    governance_score: float
    macro_sensitivity_score: float
    
    # Trading recommendations
    position_sizing_pct: float
    entry_zone_low: float
    entry_zone_high: float
    target_price: float
    stop_loss: float
    time_horizon_months: int
    
    # Risk assessment
    risk_rating: str
    key_risks: List[str]
    key_catalysts: List[str]
    key_insights: List[str]
    
    # Data quality
    data_quality: str


class TickerReport(BaseModel):
    ticker: str
    executive_summary: Optional[str] = None
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
    strategic_conviction: Optional[SectionScore] = None  # NEW: Strategic conviction analysis
    earnings_call_analysis: Optional[Dict[str, Any]] = None  # NEW: Earnings call analysis
    sector_rotation: Optional[SectionScore] = None  # NEW: Sector rotation analysis
    comprehensive_fundamentals: Optional[ComprehensiveFundamentals] = None
    decision: Decision


class ResearchResponse(BaseModel):
    tickers: List[str]
    reports: List[TickerReport]
    generated_at: str
