"""
Common utilities for synthesis operations
Shared between single-stock and multi-stock synthesis to eliminate duplication
"""

from __future__ import annotations

import numpy as np
from typing import Any, Optional


def convert_numpy_types(obj: Any) -> Any:
    """
    Convert numpy types to Python native types for Pydantic serialization
    
    Args:
        obj: Object potentially containing numpy types
        
    Returns:
        Object with numpy types converted to Python native types
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    return obj


def score_to_action_with_conviction(score: float, conviction_level: str = "Medium Conviction") -> str:
    """
    Convert numeric score to investment recommendation with conviction-adjusted thresholds
    
    Args:
        score: Confidence score (0.0 to 1.0)
        conviction_level: Strategic conviction level
        
    Returns:
        Investment action recommendation
    """
    # Define base thresholds
    base_thresholds = {
        "Strong Buy": 0.85,
        "Buy": 0.70,
        "Hold": 0.55,
        "Weak Hold": 0.40,
        "Sell": 0.0
    }
    
    # Conviction adjustments to thresholds
    conviction_adjustments = {
        "High Conviction": -0.15,    # Lower thresholds (easier to achieve Buy/Strong Buy)
        "Medium Conviction": 0.0,    # No adjustment (neutral)
        "Low Conviction": +0.10,     # Higher thresholds (harder to Buy)
        "No Investment": +0.25       # Much higher thresholds (significantly harder to Buy)
    }
    
    adjustment = conviction_adjustments.get(conviction_level, 0.0)
    
    # Apply adjustment to thresholds
    # For "No Investment": RAISE thresholds (make it harder to achieve Buy)
    # For "High Conviction": LOWER thresholds (make it easier to achieve Buy)
    adjusted_thresholds = {
        "Strong Buy": base_thresholds["Strong Buy"] + adjustment,  # +0.25 for "No Investment" = harder
        "Buy": base_thresholds["Buy"] + adjustment,                # +0.25 for "No Investment" = harder
        "Hold": base_thresholds["Hold"] + adjustment,               # +0.25 for "No Investment" = harder
        "Weak Hold": base_thresholds["Weak Hold"] + adjustment,     # +0.25 for "No Investment" = harder
        "Sell": base_thresholds["Sell"]
    }
    
    # Determine action based on adjusted thresholds
    if score >= adjusted_thresholds["Strong Buy"]:
        return "Strong Buy"
    elif score >= adjusted_thresholds["Buy"]:
        return "Buy"
    elif score >= adjusted_thresholds["Hold"]:
        return "Hold"
    elif score >= adjusted_thresholds["Weak Hold"]:
        return "Weak Hold"
    else:
        return "Sell"


def score_to_action(score: float) -> str:
    """
    Convert numeric score to professional investment recommendation
    
    Args:
        score: Confidence score (0.0 to 1.0)
        
    Returns:
        Investment action recommendation
    """
    if score >= 0.85:
        return "Strong Buy"
    elif score >= 0.70:
        return "Buy"
    elif score >= 0.55:
        return "Hold"
    elif score >= 0.40:
        return "Weak Hold"
    else:
        return "Sell"


def score_to_letter_grade(score: float) -> str:
    """
    Convert numeric score to letter grade rating
    
    Args:
        score: Confidence score (0.0 to 1.0)
        
    Returns:
        Letter grade (A+ to F)
    """
    if score >= 0.93:
        return "A+"
    elif score >= 0.87:
        return "A"
    elif score >= 0.83:
        return "A-"
    elif score >= 0.77:
        return "B+"
    elif score >= 0.70:
        return "B"
    elif score >= 0.63:
        return "B-"
    elif score >= 0.57:
        return "C+"
    elif score >= 0.50:
        return "C"
    elif score >= 0.43:
        return "C-"
    elif score >= 0.37:
        return "D+"
    elif score >= 0.30:
        return "D"
    else:
        return "F"


def score_to_stars(score: float) -> str:
    """
    Convert score to visual star rating
    
    Args:
        score: Confidence score (0.0 to 1.0)
        
    Returns:
        Star rating string (★★★★★ to ★☆☆☆☆)
    """
    if score >= 0.90:
        return "★★★★★"
    elif score >= 0.75:
        return "★★★★☆"
    elif score >= 0.60:
        return "★★★☆☆"
    elif score >= 0.40:
        return "★★☆☆☆"
    else:
        return "★☆☆☆☆"


def score_to_confidence_label(score: float) -> str:
    """
    Convert score to confidence level label
    
    Args:
        score: Confidence score (0.0 to 1.0)
        
    Returns:
        Confidence label
    """
    if score >= 0.85:
        return "Very High"
    elif score >= 0.70:
        return "High"
    elif score >= 0.55:
        return "Moderate"
    elif score >= 0.40:
        return "Low"
    else:
        return "Very Low"


def format_currency(amount: Optional[float], currency: str = "USD", decimals: int = 2) -> str:
    """
    Format currency amount with appropriate symbol and formatting
    
    Args:
        amount: Currency amount
        currency: Currency code (USD, INR, etc.)
        decimals: Number of decimal places
        
    Returns:
        Formatted currency string
    """
    if amount is None:
        return "N/A"
    
    symbols = {
        "USD": "$",
        "INR": "₹",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥"
    }
    
    symbol = symbols.get(currency, currency)
    
    # Handle large numbers with K, M, B suffixes
    abs_amount = abs(amount)
    if abs_amount >= 1_000_000_000:
        return f"{symbol}{amount / 1_000_000_000:.{decimals}f}B"
    elif abs_amount >= 1_000_000:
        return f"{symbol}{amount / 1_000_000:.{decimals}f}M"
    elif abs_amount >= 1_000:
        return f"{symbol}{amount / 1_000:.{decimals}f}K"
    else:
        return f"{symbol}{amount:.{decimals}f}"


def format_percentage(value: Optional[float], decimals: int = 1, include_sign: bool = False) -> str:
    """
    Format percentage value
    
    Args:
        value: Percentage value (already in 0-100 scale)
        decimals: Number of decimal places
        include_sign: Whether to include + sign for positive values
        
    Returns:
        Formatted percentage string
    """
    if value is None:
        return "N/A"
    
    sign = "+" if include_sign and value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def format_large_number(value: Optional[float], decimals: int = 2) -> str:
    """
    Format large numbers with K, M, B, T suffixes
    
    Args:
        value: Numeric value
        decimals: Number of decimal places
        
    Returns:
        Formatted number string
    """
    if value is None:
        return "N/A"
    
    abs_value = abs(value)
    if abs_value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.{decimals}f}T"
    elif abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.{decimals}f}B"
    elif abs_value >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f}M"
    elif abs_value >= 1_000:
        return f"{value / 1_000:.{decimals}f}K"
    else:
        return f"{value:.{decimals}f}"


def safe_get(d: dict, *keys, default: Any = None) -> Any:
    """
    Safely get nested dictionary value
    
    Args:
        d: Dictionary to access
        *keys: Sequence of keys to traverse
        default: Default value if key not found
        
    Returns:
        Value at nested key or default
        
    Example:
        safe_get(data, "fundamentals", "roe", default=0.0)
    """
    result = d
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result if result is not None else default


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker symbol format
    
    Args:
        ticker: Raw ticker symbol
        
    Returns:
        Normalized ticker symbol (uppercase, trimmed)
    """
    return ticker.strip().upper()


