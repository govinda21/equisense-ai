from __future__ import annotations

from typing import Any, Dict
import logging

import pandas as pd
import yfinance as yf

from app.cache.redis_cache import get_cache_manager
from app.utils.validation import DataValidator, ValidationError
from app.utils.rate_limiter import get_yahoo_client, get_bulk_processor

logger = logging.getLogger(__name__)


async def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch OHLCV data with validation, caching, and intelligent rate limiting
    """
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

    try:
        # Use rate-limited Yahoo Finance client
        yahoo_client = get_yahoo_client()
        data = await yahoo_client.download(ticker, period, interval)
        
        if data.empty:
            logger.warning(f"No OHLCV data returned for ticker {ticker}")
            return pd.DataFrame()
                    
        logger.debug(f"Successfully fetched {len(data)} rows of OHLCV data for {ticker}")
        
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
        
    except Exception as e:
        logger.error(f"Failed to fetch OHLCV data for {ticker}: {e}")
        return pd.DataFrame()


async def fetch_info(ticker: str) -> Dict[str, Any]:
    """
    Fetch company info data with caching and intelligent rate limiting
    """
    # Check cache first
    cache = await get_cache_manager()
    cached_data = await cache.get_company_info(ticker)
    if cached_data is not None:
        logger.debug(f"Cache hit for company info: {ticker}")
        return cached_data

    try:
        # Use rate-limited Yahoo Finance client
        yahoo_client = get_yahoo_client()
        data = await yahoo_client.get_info(ticker)
        
        if not data:
            logger.warning(f"No company info returned for ticker {ticker}")
            return {}
        
        logger.debug(f"Successfully fetched company info for {ticker}")
        
        # Cache the result (1 hour for company info)
        await cache.set_company_info(ticker, data, ttl=3600)
        
        return data
        
    except Exception as e:
        logger.error(f"Failed to fetch company info for {ticker}: {e}")
        return {}


async def fetch_multiple_ohlcv(tickers: list[str], period: str = "1y", interval: str = "1d") -> Dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for multiple tickers with controlled concurrency
    """
    bulk_processor = get_bulk_processor()
    
    async def fetch_single(ticker: str) -> tuple[str, pd.DataFrame]:
        data = await fetch_ohlcv(ticker, period, interval)
        return ticker, data
    
    results = await bulk_processor.process_batch(tickers, fetch_single)
    
    # Convert results to dictionary
    data_dict = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Failed to fetch data for ticker: {result}")
            continue
        ticker, data = result
        data_dict[ticker] = data
    
    return data_dict


async def fetch_multiple_info(tickers: list[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch company info for multiple tickers with controlled concurrency
    """
    bulk_processor = get_bulk_processor()
    
    async def fetch_single(ticker: str) -> tuple[str, Dict[str, Any]]:
        data = await fetch_info(ticker)
        return ticker, data
    
    results = await bulk_processor.process_batch(tickers, fetch_single)
    
    # Convert results to dictionary
    data_dict = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Failed to fetch info for ticker: {result}")
            continue
        ticker, data = result
        data_dict[ticker] = data
    
    return data_dict