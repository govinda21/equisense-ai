"""Common utilities for synthesis operations."""
from __future__ import annotations

from typing import Any, Optional
import numpy as np


def convert_numpy_types(obj: Any) -> Any:
    if isinstance(obj, np.integer): return int(obj)
    if isinstance(obj, np.floating): return float(obj)
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, dict): return {k: convert_numpy_types(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)): return [convert_numpy_types(i) for i in obj]
    return obj


def score_to_action(score: float) -> str:
    if score >= 0.85: return "Strong Buy"
    if score >= 0.70: return "Buy"
    if score >= 0.55: return "Hold"
    if score >= 0.40: return "Weak Hold"
    return "Sell"


def score_to_action_with_conviction(score: float, conviction_level: str = "Medium Conviction") -> str:
    adjustments = {
        "High Conviction": -0.15,
        "Medium Conviction": 0.0,
        "Low Conviction": +0.10,
        "No Investment": +0.25,
    }
    adj = adjustments.get(conviction_level, 0.0)
    if score >= 0.85 + adj: return "Strong Buy"
    if score >= 0.70 + adj: return "Buy"
    if score >= 0.55 + adj: return "Hold"
    if score >= 0.40 + adj: return "Weak Hold"
    return "Sell"


def score_to_letter_grade(score: float) -> str:
    thresholds = [
        (0.93, "A+"), (0.87, "A"), (0.83, "A-"), (0.77, "B+"), (0.70, "B"),
        (0.63, "B-"), (0.57, "C+"), (0.50, "C"), (0.43, "C-"), (0.37, "D+"), (0.30, "D"),
    ]
    for threshold, grade in thresholds:
        if score >= threshold:
            return grade
    return "F"


def score_to_stars(score: float) -> str:
    if score >= 0.90: return "★★★★★"
    if score >= 0.75: return "★★★★☆"
    if score >= 0.60: return "★★★☆☆"
    if score >= 0.40: return "★★☆☆☆"
    return "★☆☆☆☆"


def score_to_confidence_label(score: float) -> str:
    if score >= 0.85: return "Very High"
    if score >= 0.70: return "High"
    if score >= 0.55: return "Moderate"
    if score >= 0.40: return "Low"
    return "Very Low"


def format_currency(amount: Optional[float], currency: str = "USD", decimals: int = 2) -> str:
    if amount is None: return "N/A"
    symbols = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£", "JPY": "¥"}
    sym = symbols.get(currency, currency)
    a = abs(amount)
    if a >= 1e9: return f"{sym}{amount/1e9:.{decimals}f}B"
    if a >= 1e6: return f"{sym}{amount/1e6:.{decimals}f}M"
    if a >= 1e3: return f"{sym}{amount/1e3:.{decimals}f}K"
    return f"{sym}{amount:.{decimals}f}"


def format_percentage(value: Optional[float], decimals: int = 1, include_sign: bool = False) -> str:
    if value is None: return "N/A"
    sign = "+" if include_sign and value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def format_large_number(value: Optional[float], decimals: int = 2) -> str:
    if value is None: return "N/A"
    a = abs(value)
    if a >= 1e12: return f"{value/1e12:.{decimals}f}T"
    if a >= 1e9:  return f"{value/1e9:.{decimals}f}B"
    if a >= 1e6:  return f"{value/1e6:.{decimals}f}M"
    if a >= 1e3:  return f"{value/1e3:.{decimals}f}K"
    return f"{value:.{decimals}f}"


def safe_get(d: dict, *keys, default: Any = None) -> Any:
    result = d
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result if result is not None else default


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    if len(text) <= max_length: return text
    return text[:max_length - len(suffix)] + suffix


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()
