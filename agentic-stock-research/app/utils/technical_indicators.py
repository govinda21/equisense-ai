"""
Custom technical indicators implementation
Fallback when pandas_ta is incompatible with numpy
"""
from __future__ import annotations

import math
import logging
from typing import Optional, Tuple, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """
    Custom implementation of common technical indicators
    """
    
    @staticmethod
    def rsi(close: pd.Series, length: int = 14) -> Optional[float]:
        """
        Calculate Relative Strength Index (RSI)
        
        Args:
            close: Close price series
            length: RSI period (default 14)
            
        Returns:
            RSI value (0-100) or None if insufficient data
        """
        try:
            if len(close) < length + 1:
                return None
            
            # Calculate price changes
            delta = close.diff()
            
            # Separate gains and losses
            gains = delta.where(delta > 0, 0)
            losses = -delta.where(delta < 0, 0)
            
            # Calculate average gains and losses using Wilder's smoothing
            avg_gain = gains.rolling(window=length, min_periods=length).mean().iloc[length]
            avg_loss = losses.rolling(window=length, min_periods=length).mean().iloc[length]
            
            # Continue with exponential smoothing for remaining values
            for i in range(length + 1, len(close)):
                avg_gain = (avg_gain * (length - 1) + gains.iloc[i]) / length
                avg_loss = (avg_loss * (length - 1) + losses.iloc[i]) / length
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi) if not math.isnan(rsi) else None
            
        except Exception as e:
            logger.warning(f"RSI calculation failed: {e}")
            return None
    
    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Optional[float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Args:
            close: Close price series
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line EMA period (default 9)
            
        Returns:
            Dictionary with 'macd', 'signal', 'histogram' values
        """
        try:
            if len(close) < slow + signal:
                return {'macd': None, 'signal': None, 'histogram': None}
            
            # Calculate EMAs
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            
            # MACD line
            macd_line = ema_fast - ema_slow
            
            # Signal line
            signal_line = macd_line.ewm(span=signal).mean()
            
            # Histogram
            histogram = macd_line - signal_line
            
            return {
                'macd': float(macd_line.iloc[-1]) if not math.isnan(macd_line.iloc[-1]) else None,
                'signal': float(signal_line.iloc[-1]) if not math.isnan(signal_line.iloc[-1]) else None,
                'histogram': float(histogram.iloc[-1]) if not math.isnan(histogram.iloc[-1]) else None
            }
            
        except Exception as e:
            logger.warning(f"MACD calculation failed: {e}")
            return {'macd': None, 'signal': None, 'histogram': None}
    
    @staticmethod
    def bollinger_bands(close: pd.Series, length: int = 20, std: float = 2) -> Dict[str, Optional[float]]:
        """
        Calculate Bollinger Bands
        
        Args:
            close: Close price series
            length: Moving average period (default 20)
            std: Standard deviation multiplier (default 2)
            
        Returns:
            Dictionary with 'upper', 'middle', 'lower' values
        """
        try:
            if len(close) < length:
                return {'upper': None, 'middle': None, 'lower': None}
            
            # Simple Moving Average (middle band)
            sma = close.rolling(window=length).mean()
            
            # Standard deviation
            rolling_std = close.rolling(window=length).std()
            
            # Upper and lower bands
            upper = sma + (rolling_std * std)
            lower = sma - (rolling_std * std)
            
            return {
                'upper': float(upper.iloc[-1]) if not math.isnan(upper.iloc[-1]) else None,
                'middle': float(sma.iloc[-1]) if not math.isnan(sma.iloc[-1]) else None,
                'lower': float(lower.iloc[-1]) if not math.isnan(lower.iloc[-1]) else None
            }
            
        except Exception as e:
            logger.warning(f"Bollinger Bands calculation failed: {e}")
            return {'upper': None, 'middle': None, 'lower': None}
    
    @staticmethod
    def simple_moving_average(close: pd.Series, length: int) -> Optional[float]:
        """
        Calculate Simple Moving Average
        
        Args:
            close: Close price series
            length: Moving average period
            
        Returns:
            SMA value or None if insufficient data
        """
        try:
            if len(close) < length:
                return None
            
            sma = close.rolling(window=length).mean().iloc[-1]
            return float(sma) if not math.isnan(sma) else None
            
        except Exception as e:
            logger.warning(f"SMA calculation failed: {e}")
            return None
    
    @staticmethod
    def momentum(close: pd.Series, length: int = 20) -> Optional[float]:
        """
        Calculate Momentum (rate of change)
        
        Args:
            close: Close price series
            length: Lookback period
            
        Returns:
            Momentum as percentage change or None
        """
        try:
            if len(close) < length + 1:
                return None
            
            current = close.iloc[-1]
            past = close.iloc[-length - 1]
            
            if past == 0:
                return None
            
            momentum = (current / past) - 1.0
            return float(momentum) if not math.isnan(momentum) else None
            
        except Exception as e:
            logger.warning(f"Momentum calculation failed: {e}")
            return None


# Test availability of pandas_ta
def _test_pandas_ta() -> bool:
    """Test if pandas_ta is working properly"""
    try:
        import pandas_ta as ta
        # Test a simple indicator
        test_data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 10)
        result = ta.rsi(test_data, length=14)
        return result is not None and not result.empty
    except Exception:
        return False

# Global flag for pandas_ta availability
PANDAS_TA_AVAILABLE = _test_pandas_ta()

if not PANDAS_TA_AVAILABLE:
    logger.warning("pandas_ta is not available or incompatible, using custom indicators")
else:
    logger.info("pandas_ta is available and working")
