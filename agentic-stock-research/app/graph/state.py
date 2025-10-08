from __future__ import annotations

from typing import Any, Dict, List, TypedDict, Optional
from typing_extensions import Annotated
import operator


def _keep_last_country(left: str, right: str) -> str:
    """Keep the most recent country value"""
    return right if right else left

def _keep_unique_tickers(left: List[str], right: List[str]) -> List[str]:
    """Keep unique tickers, avoiding duplicates that cause data explosion"""
    if not left:
        return right
    if not right:
        return left
    # Combine and deduplicate
    combined = list(set(left + right))
    return combined

def _merge_ticker_analysis(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge analysis data for multiple tickers"""
    merged = left.copy()
    merged.update(right)
    return merged

class ResearchState(TypedDict, total=False):
    tickers: Annotated[List[str], _keep_unique_tickers]
    country: Annotated[str, _keep_last_country]  # Country for stock market context
    raw_data: Annotated[Dict[str, Any], operator.or_]  # {ticker: {ohlcv_summary, info}}
    analysis: Annotated[Dict[str, Any], _merge_ticker_analysis]  # {ticker: {news, tech, fund, etc}}
    confidences: Annotated[Dict[str, Any], operator.or_]  # {ticker: {node: confidence}}
    retries: Annotated[Dict[str, int], operator.or_]
    final_output: Dict[str, Any]
    needs_rerun: Annotated[List[str], _keep_unique_tickers]
    # New fields for enhanced functionality
    market_context: Dict[str, Any]  # Market-wide indicators and regime
    currency_rates: Dict[str, float]  # Currency conversion rates
    user_preferences: Optional[Dict[str, Any]]  # User risk profile and preferences