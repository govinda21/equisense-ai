"""
Data validation and sanitization utilities
"""
from __future__ import annotations

import re
import math
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import pandas as pd

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Raised when data validation fails"""
    pass

class DataValidator:
    """Comprehensive data validation and sanitization"""
    
    # Valid ticker patterns by exchange
    TICKER_PATTERNS = {
        'US': re.compile(r'^[A-Z]{1,5}$'),                    # AAPL, MSFT, etc.
        'NSE': re.compile(r'^[A-Z0-9]{1,20}\.NS$'),          # BAJFINANCE.NS
        'BSE': re.compile(r'^[A-Z0-9]{1,20}\.BO$'),          # RELIANCE.BO
        'LSE': re.compile(r'^[A-Z0-9]{1,10}\.L$'),           # VODAFONE.L
        'TSE': re.compile(r'^[A-Z0-9]{1,10}\.T$'),           # TOYOTA.T
    }
    
    VALID_COUNTRIES = {
        'US', 'India', 'United Kingdom', 'Japan', 'Canada', 
        'Germany', 'France', 'Australia', 'China', 'South Korea'
    }
    
    @staticmethod
    def validate_ticker(ticker: str, country: Optional[str] = None) -> str:
        """
        Validate and sanitize ticker symbol
        
        Args:
            ticker: Raw ticker input
            country: Country context for validation
            
        Returns:
            Sanitized ticker symbol
            
        Raises:
            ValidationError: If ticker is invalid
        """
        if not ticker or not isinstance(ticker, str):
            raise ValidationError("Ticker must be a non-empty string")
        
        # Clean the ticker
        ticker = ticker.strip().upper()
        
        if len(ticker) < 1 or len(ticker) > 20:
            raise ValidationError(f"Ticker length must be between 1-20 characters: {ticker}")
        
        # Remove invalid characters
        sanitized = re.sub(r'[^A-Z0-9\.\-]', '', ticker)
        
        if not sanitized:
            raise ValidationError(f"Ticker contains only invalid characters: {ticker}")
        
        # Country-specific validation
        if country == 'India':
            # Accept both with and without exchange suffix
            if not (sanitized.endswith('.NS') or sanitized.endswith('.BO')):
                # Auto-add .NS for Indian stocks
                sanitized += '.NS'
        
        # Validate against known patterns
        is_valid = False
        for pattern in DataValidator.TICKER_PATTERNS.values():
            if pattern.match(sanitized):
                is_valid = True
                break
        
        if not is_valid and len(sanitized) <= 5:  # Allow simple patterns
            is_valid = True
            
        if not is_valid:
            logger.warning(f"Ticker {sanitized} doesn't match known patterns but allowing it")
        
        return sanitized
    
    @staticmethod
    def validate_country(country: str) -> str:
        """Validate and normalize country name"""
        if not country or not isinstance(country, str):
            return 'India'  # Default fallback
        
        country = country.strip()
        
        # Normalize common variations
        country_mapping = {
            'usa': 'US',
            'united states': 'US',
            'america': 'US',
            'in': 'India',
            'ind': 'India',
            'uk': 'United Kingdom',
            'britain': 'United Kingdom',
            'jp': 'Japan',
        }
        
        normalized = country_mapping.get(country.lower(), country)
        
        # Allow valid countries or fallback to US
        if normalized in DataValidator.VALID_COUNTRIES:
            return normalized
        
        logger.warning(f"Unknown country {country}, defaulting to India")
        return 'India'
    
    @staticmethod
    def validate_financial_value(value: Any, field_name: str, allow_negative: bool = True) -> Optional[float]:
        """
        Validate and sanitize financial values
        
        Args:
            value: Raw financial value
            field_name: Name of the field for error messages
            allow_negative: Whether negative values are allowed
            
        Returns:
            Sanitized float value or None if invalid
        """
        if value is None or value == '' or pd.isna(value):
            return None
        
        try:
            # Handle pandas Series
            if hasattr(value, 'iloc'):
                value = value.iloc[0] if len(value) > 0 else None
                if value is None:
                    return None
            
            # Convert to float
            if isinstance(value, str):
                # Remove common formatting
                value = value.replace(',', '').replace('$', '').replace('%', '').strip()
                if value == '' or value.lower() in ('n/a', 'na', 'null', 'none'):
                    return None
            
            float_val = float(value)
            
            # Check for invalid values
            if math.isnan(float_val) or math.isinf(float_val):
                logger.warning(f"Invalid {field_name} value: {value} (NaN/Inf)")
                return None
            
            # Check negative values
            if not allow_negative and float_val < 0:
                logger.warning(f"Negative {field_name} value not allowed: {float_val}")
                return None
            
            # Sanity checks for extreme values
            if abs(float_val) > 1e15:  # Trillion+ seems suspicious
                logger.warning(f"Extremely large {field_name} value: {float_val}")
                return None
            
            return float_val
            
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning(f"Invalid {field_name} value: {value} ({e})")
            return None
    
    @staticmethod
    def validate_ratio(value: Any, field_name: str, min_val: float = -1000, max_val: float = 1000) -> Optional[float]:
        """Validate financial ratios with reasonable bounds"""
        float_val = DataValidator.validate_financial_value(value, field_name, allow_negative=True)
        
        if float_val is None:
            return None
        
        if not (min_val <= float_val <= max_val):
            logger.warning(f"Out of range {field_name} ratio: {float_val} (expected {min_val}-{max_val})")
            return None
        
        return float_val
    
    @staticmethod
    def validate_percentage(value: Any, field_name: str) -> Optional[float]:
        """Validate percentage values (0-100 or 0-1)"""
        float_val = DataValidator.validate_financial_value(value, field_name, allow_negative=True)
        
        if float_val is None:
            return None
        
        # Auto-convert decimal to percentage if needed
        if 0 <= abs(float_val) <= 1:
            float_val *= 100
        
        # Reasonable bounds for percentages
        if not (-1000 <= float_val <= 1000):
            logger.warning(f"Invalid {field_name} percentage: {float_val}")
            return None
        
        return float_val
    
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, required_columns: List[str]) -> pd.DataFrame:
        """
        Validate DataFrame structure and clean data
        
        Args:
            df: Input DataFrame
            required_columns: Columns that must be present
            
        Returns:
            Cleaned DataFrame
            
        Raises:
            ValidationError: If DataFrame is invalid
        """
        if df is None or df.empty:
            raise ValidationError("DataFrame is empty or None")
        
        # Check required columns exist
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValidationError(f"Missing required columns: {missing_cols}")
        
        # Remove duplicate rows
        original_len = len(df)
        df = df.drop_duplicates()
        if len(df) < original_len:
            logger.warning(f"Removed {original_len - len(df)} duplicate rows")
        
        # Sort by index if it's a DatetimeIndex
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.sort_index()
        
        return df
    
    @staticmethod
    def sanitize_text(text: Any, max_length: int = 500) -> str:
        """Sanitize text fields"""
        if text is None or pd.isna(text):
            return ""
        
        text = str(text).strip()
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length - 3] + "..."
        
        return text
    
    @staticmethod
    def validate_date_range(start_date: Any, end_date: Any) -> tuple[datetime, datetime]:
        """Validate and normalize date range"""
        now = datetime.now()
        
        # Default to 1 year if not provided
        if start_date is None:
            start_date = now - timedelta(days=365)
        if end_date is None:
            end_date = now
        
        # Convert to datetime if needed
        if isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        if isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)
        
        # Ensure proper order
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        # Sanity checks
        if end_date > now + timedelta(days=30):
            logger.warning("End date is in the future, adjusting to current date")
            end_date = now
        
        if start_date < now - timedelta(days=365*20):  # 20 years ago
            logger.warning("Start date is too far in the past, adjusting")
            start_date = now - timedelta(days=365*5)  # 5 years max
        
        return start_date, end_date


# Decorator for automatic validation
def validate_financial_data(func):
    """Decorator to automatically validate financial data inputs"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            logger.error(f"Validation error in {func.__name__}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            return None
    return wrapper
