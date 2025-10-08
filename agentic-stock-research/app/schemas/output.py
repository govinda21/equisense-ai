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
    
    # Professional equity research fields
    letter_grade: str = Field(default="C")
    stars: str = Field(default="★★★☆☆")
    professional_rationale: str = Field(default="Analysis based on current market conditions and fundamental metrics.")
    professional_recommendation: str = Field(default="")
    
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
    comprehensive_fundamentals: Optional[ComprehensiveFundamentals] = None
    decision: Decision


class ResearchResponse(BaseModel):
    tickers: List[str]
    reports: List[TickerReport]
    generated_at: str
