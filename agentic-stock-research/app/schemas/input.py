from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    tickers: List[str] = Field(default_factory=list)
    country: Optional[str] = Field(default="United States", description="Country for stock market")


class AnalysisRequest(BaseModel):
    tickers: List[str] = Field(default_factory=list)
    country: Optional[str] = Field(default="United States", description="Country for stock market")
    horizon_short_days: int = Field(default=30, ge=1, le=365)
    horizon_long_days: int = Field(default=365, ge=30, le=1825)


class ChatRequest(BaseModel):
    message: str = Field(..., description="User's chat message")
    context: str = Field(default="", description="Optional context from previous conversation")
