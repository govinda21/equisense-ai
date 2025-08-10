from __future__ import annotations

import asyncio
import logging
from typing import Dict

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.finance import fetch_ohlcv, fetch_info
from app.utils.async_utils import AsyncProcessor, monitor_performance

logger = logging.getLogger(__name__)


@monitor_performance("data_collection")
async def data_collection_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Optimized data collection with parallel fetching
    """
    tickers = state["tickers"]
    if not tickers:
        state["raw_data"] = {}
        state.setdefault("confidences", {})["data_collection"] = 0.0
        return state
    
    logger.debug(f"Collecting data for {len(tickers)} tickers in parallel")
    
    async def fetch_ticker_data(ticker: str) -> tuple[str, dict]:
        """Fetch both OHLCV and info data for a single ticker"""
        try:
            # Fetch OHLCV and info data in parallel for each ticker
            ohlcv_task = fetch_ohlcv(ticker)
            info_task = fetch_info(ticker)
            
            ohlcv_df, info = await asyncio.gather(ohlcv_task, info_task, return_exceptions=True)
            
            # Handle OHLCV data
            ohlcv_summary = {}
            if not isinstance(ohlcv_df, Exception) and hasattr(ohlcv_df, 'empty') and not ohlcv_df.empty:
                last = ohlcv_df.iloc[-1]
                
                # Safe extraction from pandas Series
                def safe_float_from_series(series_row, column_name, default=0.0):
                    try:
                        if hasattr(series_row, column_name):
                            value = getattr(series_row, column_name)
                            return float(value.iloc[0] if hasattr(value, 'iloc') else value)
                        else:
                            value = series_row.get(column_name, default)
                            return float(value.iloc[0] if hasattr(value, 'iloc') else value)
                    except (AttributeError, IndexError, TypeError):
                        return default

                ohlcv_summary = {
                    "last_close": safe_float_from_series(last, "Close", 0.0),
                    "last_volume": safe_float_from_series(last, "Volume", 0.0),
                    "rows": int(len(ohlcv_df)),
                }
            elif isinstance(ohlcv_df, Exception):
                logger.warning(f"Failed to fetch OHLCV for {ticker}: {ohlcv_df}")
            
            # Handle info data
            if isinstance(info, Exception):
                logger.warning(f"Failed to fetch info for {ticker}: {info}")
                info = {}
            
            return ticker, {"ohlcv_summary": ohlcv_summary, "info": info}
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return ticker, {"ohlcv_summary": {}, "info": {}}
    
    # Use AsyncProcessor for controlled parallel execution
    async with AsyncProcessor(max_workers=5) as processor:
        # Fetch all ticker data in parallel with concurrency control
        fetch_tasks = [fetch_ticker_data(ticker) for ticker in tickers]
        results = await processor.gather_with_concurrency(
            *fetch_tasks,
            return_exceptions=True,
            timeout=60.0  # 60 second timeout for all data collection
        )
    
    # Process results
    raw_data: Dict[str, dict] = {}
    successful_fetches = 0
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Failed to process ticker data: {result}")
            continue
        
        if isinstance(result, tuple) and len(result) == 2:
            ticker, data = result
            raw_data[ticker] = data
            successful_fetches += 1
        else:
            logger.warning(f"Invalid result format: {result}")
    
    # Calculate confidence based on success rate
    confidence = successful_fetches / len(tickers) if tickers else 0.0
    
    state["raw_data"] = raw_data
    state.setdefault("confidences", {})["data_collection"] = confidence
    
    logger.info(f"Data collection completed: {successful_fetches}/{len(tickers)} successful")
    
    return state
