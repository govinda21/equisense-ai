"""
Context Manager for Per-Ticker Isolation

This module provides utilities for safely managing per-ticker contexts
and merging results to prevent data contamination across tickers.
"""

from copy import deepcopy
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def create_isolated_context(base_context: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """
    Create an isolated context for a single ticker by deep copying the base context.
    
    Args:
        base_context: The base context/state to clone
        ticker: The ticker symbol for this isolated context
        
    Returns:
        Deep copy of base_context with ticker set
    """
    isolated_context = deepcopy(base_context)
    isolated_context["ticker"] = ticker
    isolated_context["tickers"] = [ticker]  # Ensure single ticker list
    isolated_context["raw_data"] = {}
    isolated_context["analysis"] = {}
    isolated_context["confidences"] = {}
    return isolated_context


def merge_results(
    global_results: Dict[str, Any], 
    ticker: str, 
    ticker_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Safely merge a single ticker's result into the global results dictionary.
    
    This ensures no reference sharing and proper isolation.
    
    Args:
        global_results: The global results dictionary to merge into
        ticker: The ticker symbol
        ticker_result: The result dictionary for this ticker
        
    Returns:
        Updated global_results dictionary
    """
    if ticker not in global_results:
        global_results[ticker] = {}
    
    # Deep copy the result to prevent reference sharing
    global_results[ticker] = deepcopy(ticker_result)
    
    logger.debug(f"[{ticker}] Merged result into global_results")
    return global_results


def merge_ticker_analysis(
    global_analysis: Dict[str, Any],
    ticker: str,
    ticker_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge ticker-specific analysis into global analysis dictionary.
    
    Args:
        global_analysis: Global analysis dictionary
        ticker: Ticker symbol
        ticker_analysis: Analysis data for this ticker
        
    Returns:
        Updated global_analysis dictionary
    """
    if ticker not in global_analysis:
        global_analysis[ticker] = {}
    
    # Deep copy to prevent reference sharing
    global_analysis[ticker] = deepcopy(ticker_analysis)
    
    return global_analysis


def merge_ticker_raw_data(
    global_raw_data: Dict[str, Any],
    ticker: str,
    ticker_raw_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge ticker-specific raw data into global raw_data dictionary.
    
    Args:
        global_raw_data: Global raw_data dictionary
        ticker: Ticker symbol
        ticker_raw_data: Raw data for this ticker
        
    Returns:
        Updated global_raw_data dictionary
    """
    if ticker not in global_raw_data:
        global_raw_data[ticker] = {}
    
    # Deep copy to prevent reference sharing
    global_raw_data[ticker] = deepcopy(ticker_raw_data)
    
    return global_raw_data


def validate_ticker_isolation(
    ticker: str,
    result: Dict[str, Any],
    expected_fields: List[str] = None
) -> bool:
    """
    Validate that a result is properly isolated for a ticker.
    
    Args:
        ticker: Expected ticker symbol
        result: Result dictionary to validate
        expected_fields: Optional list of expected field names
        
    Returns:
        True if validation passes, False otherwise
    """
    if expected_fields:
        for field in expected_fields:
            if field not in result:
                logger.warning(f"[{ticker}] Missing expected field: {field}")
                return False
    
    # Check if ticker matches in result
    if "ticker" in result and result["ticker"] != ticker:
        logger.error(f"[{ticker}] Ticker mismatch in result: {result.get('ticker')}")
        return False
    
    return True



