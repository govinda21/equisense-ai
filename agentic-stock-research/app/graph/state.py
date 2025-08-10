from __future__ import annotations

from typing import Any, Dict, List, TypedDict
from typing_extensions import Annotated
import operator


def _keep_last_country(left: str, right: str) -> str:
    """Keep the most recent country value"""
    return right if right else left

class ResearchState(TypedDict, total=False):
    tickers: Annotated[List[str], operator.add]
    country: Annotated[str, _keep_last_country]  # Country for stock market context
    raw_data: Annotated[Dict[str, Any], operator.or_]
    analysis: Annotated[Dict[str, Any], operator.or_]
    confidences: Annotated[Dict[str, float], operator.or_]
    retries: Annotated[Dict[str, int], operator.or_]
    final_output: Dict[str, Any]
    needs_rerun: Annotated[List[str], operator.add]
