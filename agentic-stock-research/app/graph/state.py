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

def _keep_last_final_output(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the most recent final_output value (for parallel node execution)
    
    This allows parallel nodes (strategic_conviction, sector_rotation) to pass through
    final_output without causing InvalidUpdateError. Only synthesis node actually writes
    to final_output, but other nodes may include it in their state return.
    """
    # If right has content, prefer it (more recent)
    if right and len(right) > 0:
        return right
    # Otherwise keep left (or empty dict if both are empty)
    return left if left else {}

class ResearchState(TypedDict, total=False):
    tickers: Annotated[List[str], _keep_unique_tickers]
    country: Annotated[str, _keep_last_country]  # Country for stock market context
    horizon_short_days: Annotated[int, _keep_last_country]  # Short-term investment horizon in days
    horizon_long_days: Annotated[int, _keep_last_country]   # Long-term investment horizon in days
    raw_data: Annotated[Dict[str, Any], operator.or_]  # {ticker: {ohlcv_summary, info}}
    analysis: Annotated[Dict[str, Any], _merge_ticker_analysis]  # {ticker: {news, tech, fund, etc}}
    confidences: Annotated[Dict[str, Any], operator.or_]  # {ticker: {node: confidence}}
    retries: Annotated[Dict[str, int], operator.or_]
    final_output: Annotated[Dict[str, Any], _keep_last_final_output]  # Only synthesis writes this, but parallel nodes may pass it through
    needs_rerun: Annotated[List[str], _keep_unique_tickers]
    # New fields for enhanced functionality
    market_context: Dict[str, Any]  # Market-wide indicators and regime
    currency_rates: Dict[str, float]  # Currency conversion rates
    user_preferences: Optional[Dict[str, Any]]  # User risk profile and preferences
