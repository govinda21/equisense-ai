"""
Standardized formatting utilities for financial data
Ensures consistent units and display across the application
"""

from typing import Optional, Union


def format_percentage(value: Optional[float], decimals: int = 2) -> str:
    """
    Format a value as a percentage with proper units
    
    Args:
        value: Decimal value (e.g., 0.38 for 38%)
        decimals: Number of decimal places
    
    Returns:
        Formatted string: "38.00%"
    
    Examples:
        >>> format_percentage(0.38, 2)
        '38.00%'
        >>> format_percentage(0.085, 2)
        '8.50%'
        >>> format_percentage(None)
        'N/A'
    """
    if value is None:
        return "N/A"
    
    try:
        # Convert decimal to percentage
        percentage = float(value) * 100
        return f"{percentage:.{decimals}f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_ratio(value: Optional[float], decimals: int = 2) -> str:
    """
    Format a ratio with both decimal and percentage forms
    
    Args:
        value: Ratio value (e.g., 0.41 for 41%)
        decimals: Number of decimal places
    
    Returns:
        Formatted string: "0.41 (41.00%)"
    
    Examples:
        >>> format_ratio(0.41, 2)
        '0.41 (41.00%)'
        >>> format_ratio(1.5, 2)
        '1.50 (150.00%)'
        >>> format_ratio(None)
        'N/A'
    """
    if value is None:
        return "N/A"
    
    try:
        ratio = float(value)
        percentage = ratio * 100
        return f"{ratio:.{decimals}f} ({percentage:.{decimals}f}%)"
    except (ValueError, TypeError):
        return "N/A"


def format_currency(value: Optional[float], ticker: Optional[str] = None, decimals: int = 2) -> str:
    """
    Format currency with country-aware symbol
    
    Args:
        value: Numeric value
        ticker: Ticker symbol (e.g., "RELIANCE.NS")
        decimals: Number of decimal places
    
    Returns:
        Formatted string: "₹1,484.10" or "$1484.10"
    
    Examples:
        >>> format_currency(1484.10, "RELIANCE.NS")
        '₹1,484.10'
        >>> format_currency(1484.10, "AAPL")
        '$1,484.10'
        >>> format_currency(None)
        '—'
    """
    if value is None:
        return "—"
    
    try:
        val = float(value)
        
        # Determine currency symbol based on ticker
        if ticker and (ticker.endswith('.NS') or ticker.endswith('.BO')):
            symbol = '₹'
            
            # Format with Indian number style (Cr, L)
            abs_val = abs(val)
            if abs_val >= 1e7:
                return f"{symbol}{(val / 1e7):.{decimals}f} Cr"
            if abs_val >= 1e5:
                return f"{symbol}{(val / 1e5):.{decimals}f} L"
            return f"{symbol}{val:,.{decimals}f}"
        else:
            symbol = '$'
            
            # Format with Western number style (T, B, M)
            abs_val = abs(val)
            if abs_val >= 1e12:
                return f"{symbol}{(val / 1e12):.{decimals}f}T"
            if abs_val >= 1e9:
                return f"{symbol}{(val / 1e9):.{decimals}f}B"
            if abs_val >= 1e6:
                return f"{symbol}{(val / 1e6):.{decimals}f}M"
            return f"{symbol}{val:,.{decimals}f}"
    
    except (ValueError, TypeError):
        return "—"


def format_multiple(value: Optional[float], decimals: int = 1) -> str:
    """
    Format a multiple (e.g., P/E, EV/EBITDA) with × symbol
    
    Args:
        value: Multiple value (e.g., 24.17 for P/E)
        decimals: Number of decimal places
    
    Returns:
        Formatted string: "24.2×"
    
    Examples:
        >>> format_multiple(24.17, 1)
        '24.2×'
        >>> format_multiple(12.5, 1)
        '12.5×'
        >>> format_multiple(None)
        'N/A'
    """
    if value is None:
        return "N/A"
    
    try:
        return f"{float(value):.{decimals}f}×"
    except (ValueError, TypeError):
        return "N/A"


def format_large_number(value: Optional[float], decimals: int = 2) -> str:
    """
    Format large numbers with appropriate scale (Cr, L, T, B, M)
    
    Args:
        value: Numeric value
        decimals: Number of decimal places
    
    Returns:
        Formatted string with scale
    
    Examples:
        >>> format_large_number(2008000000000, 2)
        '2.01T'
        >>> format_large_number(10000000, 2)
        '10.00M'
        >>> format_large_number(None)
        '—'
    """
    if value is None:
        return "—"
    
    try:
        val = float(value)
        abs_val = abs(val)
        
        if abs_val >= 1e12:
            return f"{val / 1e12:.{decimals}f}T"
        if abs_val >= 1e9:
            return f"{val / 1e9:.{decimals}f}B"
        if abs_val >= 1e7:
            return f"{val / 1e7:.{decimals}f} Cr"
        if abs_val >= 1e5:
            return f"{val / 1e5:.{decimals}f} L"
        if abs_val >= 1e6:
            return f"{val / 1e6:.{decimals}f}M"
        
        return f"{val:,.{decimals}f}"
    except (ValueError, TypeError):
        return "—"


def format_interest_coverage(value: Optional[float], decimals: int = 2) -> str:
    """
    Format interest coverage ratio with × symbol
    
    Args:
        value: Interest coverage ratio
        decimals: Number of decimal places
    
    Returns:
        Formatted string: "7.50×" (true value, no capping)
    
    Examples:
        >>> format_interest_coverage(7.5, 2)
        '7.50×'
        >>> format_interest_coverage(30.0, 2)
        '30.00×'  # Shows true value
        >>> format_interest_coverage(None)
        'N/A'
    """
    if value is None:
        return "N/A"
    
    try:
        coverage = float(value)
        # Show true value - no capping
        return f"{coverage:.{decimals}f}×"
    except (ValueError, TypeError):
        return "N/A"


def currency_symbol_for_ticker(ticker: Optional[str]) -> str:
    """
    Get currency symbol for a ticker
    
    Args:
        ticker: Ticker symbol
    
    Returns:
        Currency symbol (₹ for Indian, $ for others)
    """
    if not ticker:
        return "$"
    
    ticker_upper = ticker.upper()
    if ticker_upper.endswith('.NS') or ticker_upper.endswith('.BO'):
        return '₹'
    return '$'

