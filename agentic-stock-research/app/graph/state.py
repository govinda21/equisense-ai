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
    combined = list(set(left + right))
    return combined

def _merge_ticker_analysis(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge analysis data for multiple tickers"""
    merged = left.copy()
    merged.update(right)
    return merged

def _keep_last_final_output(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the most recent final_output value (for parallel node execution)"""
    if right and len(right) > 0:
        return right
    return left if left else {}

def _keep_last_optional_dict(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Keep most recent non-None optional dict"""
    if right is not None:
        return right
    return left

class ResearchState(TypedDict, total=False):
    tickers: Annotated[List[str], _keep_unique_tickers]
    country: Annotated[str, _keep_last_country]
    horizon_short_days: Annotated[int, _keep_last_country]
    horizon_long_days: Annotated[int, _keep_last_country]
    analysis_type: Annotated[str, _keep_last_country]
    raw_data: Annotated[Dict[str, Any], operator.or_]
    analysis: Annotated[Dict[str, Any], _merge_ticker_analysis]
    confidences: Annotated[Dict[str, Any], operator.or_]
    retries: Annotated[Dict[str, int], operator.or_]
    final_output: Annotated[Dict[str, Any], _keep_last_final_output]
    needs_rerun: Annotated[List[str], _keep_unique_tickers]
    market_context: Annotated[Dict[str, Any], operator.or_]
    currency_rates: Annotated[Dict[str, float], operator.or_]
    user_preferences: Annotated[Optional[Dict[str, Any]], _keep_last_optional_dict]
