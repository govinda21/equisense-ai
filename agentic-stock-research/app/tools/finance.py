from __future__ import annotations

from typing import Any, Dict
import logging

import pandas as pd
import yfinance as yf

from app.utils.retry import retry_async, circuit_breaker_async
from app.cache.redis_cache import get_cache_manager
from app.utils.validation import DataValidator, ValidationError

logger = logging.getLogger(__name__)


async def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV data with validation, caching, retry logic and circuit breaker
    """
    import asyncio
    
    # Validate inputs
    try:
        ticker = DataValidator.validate_ticker(ticker)
        if period not in ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max']:
            logger.warning(f"Invalid period {period}, defaulting to 1y")
            period = "1y"
        if interval not in ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']:
            logger.warning(f"Invalid interval {interval}, defaulting to 1d")
            interval = "1d"
    except ValidationError as e:
        logger.error(f"Ticker validation failed: {e}")
        return pd.DataFrame()  # Return empty DataFrame for invalid tickers
    
    # Check cache first
    cache = await get_cache_manager()
    cached_data = await cache.get_ohlcv(ticker, period, interval)
    if cached_data is not None:
        logger.debug(f"Cache hit for OHLCV data: {ticker} (period={period}, interval={interval})")
        return cached_data

    @retry_async(max_retries=3, base_delay=1.0, exceptions=(Exception,))
    @circuit_breaker_async(failure_threshold=5, recovery_timeout=60.0)
    async def _fetch_with_retry() -> pd.DataFrame:
        def _dl() -> pd.DataFrame:
            try:
                logger.debug(f"Fetching OHLCV data from API for {ticker} (period={period}, interval={interval})")
                data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
                
                if data.empty:
                    raise ValueError(f"No OHLCV data returned for ticker {ticker}")
                    
                logger.debug(f"Successfully fetched {len(data)} rows of OHLCV data for {ticker}")
                return data
                
            except Exception as e:
                logger.error(f"Failed to fetch OHLCV data for {ticker}: {e}")
                raise

        return await asyncio.to_thread(_dl)
    
    # Fetch from API with retry logic
    data = await _fetch_with_retry()
    
    # Validate the returned data
    try:
        if not data.empty:
            # Validate required columns exist
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if hasattr(data.columns, 'get_level_values'):  # MultiIndex
                # Extract base column names from MultiIndex
                base_cols = [col[0] if isinstance(col, tuple) else col for col in data.columns]
                missing = [col for col in required_cols if col not in base_cols]
            else:
                missing = [col for col in required_cols if col not in data.columns]
            
            if missing:
                logger.warning(f"OHLCV data missing columns {missing} for {ticker}")
            
            # Validate data ranges
            data = DataValidator.validate_dataframe(data, [])
            
        logger.debug(f"Validated OHLCV data for {ticker}: {len(data)} rows")
    except Exception as e:
        logger.warning(f"OHLCV data validation failed for {ticker}: {e}")
        # Continue with unvalidated data rather than fail completely
    
    # Cache the result (15 minutes for OHLCV data)
    await cache.set_ohlcv(ticker, data, period, interval, ttl=900)
    
    return data


async def fetch_info(ticker: str) -> Dict[str, Any]:
    """
    Fetch company info data with caching, retry logic and circuit breaker
    """
    import asyncio
    
    # Check cache first
    cache = await get_cache_manager()
    cached_data = await cache.get_company_info(ticker)
    if cached_data is not None:
        logger.debug(f"Cache hit for company info: {ticker}")
        return cached_data

    @retry_async(max_retries=3, base_delay=1.0, exceptions=(Exception,))
    @circuit_breaker_async(failure_threshold=5, recovery_timeout=60.0)
    async def _fetch_with_retry() -> Dict[str, Any]:
        def _info() -> Dict[str, Any]:
            try:
                logger.debug(f"Fetching company info from API for {ticker}")
                t = yf.Ticker(ticker)
                info = t.info or {}
                
                if not info:
                    logger.warning(f"No company info returned for ticker {ticker}")
                else:
                    logger.debug(f"Successfully fetched company info for {ticker} ({len(info)} fields)")
                    
                return info
                
            except Exception as e:
                logger.error(f"Failed to fetch company info for {ticker}: {e}")
                # Return empty dict as fallback
                return {}

        return await asyncio.to_thread(_info)
    
    # Fetch from API with retry logic
    data = await _fetch_with_retry()
    
    # Cache the result (1 hour for company info)
    await cache.set_company_info(ticker, data, ttl=3600)
    
    return data
