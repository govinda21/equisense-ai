from __future__ import annotations

from typing import Any, Dict, List
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


class TickerReport(BaseModel):
    ticker: str
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
    decision: Decision


class ResearchResponse(BaseModel):
    tickers: List[str]
    reports: List[TickerReport]
    generated_at: str
