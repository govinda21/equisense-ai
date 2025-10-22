"""
Cache Warming System for High-Performance Data Access

This module provides intelligent cache warming for frequently accessed data
to improve response times and reduce API calls.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from app.cache.optimized_cache import get_optimized_cache_manager
from app.tools.finance import fetch_info, fetch_ohlcv
from app.tools.indian_market_data import get_indian_market_data
from app.tools.sector_rotation import SectorRotationAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class CacheWarmingConfig:
    """Configuration for cache warming"""
    enabled: bool = True
    warm_on_startup: bool = True
    warm_popular_stocks: bool = True
    warm_sector_data: bool = True
    warm_market_data: bool = True
    max_concurrent_warming: int = 5
    warming_interval_minutes: int = 30
    popular_stocks: List[str] = None
    cache_ttl_hours: int = 24


class CacheWarmer:
    """
    Intelligent cache warming system for frequently accessed data
    """
    
    def __init__(self, config: Optional[CacheWarmingConfig] = None):
        self.config = config or CacheWarmingConfig()
        self.cache = None
        self.warming_tasks: Dict[str, asyncio.Task] = {}
        self.last_warming_time: Dict[str, float] = {}
        self.warming_stats = {
            "total_warming_operations": 0,
            "successful_warmings": 0,
            "failed_warmings": 0,
            "cache_hits_after_warming": 0,
            "time_saved_seconds": 0.0
        }
        
        # Popular Indian stocks for warming
        if self.config.popular_stocks is None:
            self.config.popular_stocks = [
                "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
                "ITC.NS", "KOTAKBANK.NS", "BHARTIARTL.NS", "SBIN.NS", "ASIANPAINT.NS",
                "MARUTI.NS", "AXISBANK.NS", "LT.NS", "WIPRO.NS", "NESTLEIND.NS"
            ]
        
        logger.info(f"CacheWarmer initialized with {len(self.config.popular_stocks)} popular stocks")
    
    async def initialize(self):
        """Initialize the cache warmer"""
        if self.cache is None:
            self.cache = await get_optimized_cache_manager()
        
        if self.config.warm_on_startup:
            await self.warm_all_data()
    
    async def warm_all_data(self):
        """Warm all frequently accessed data"""
        logger.info("Starting comprehensive cache warming")
        start_time = time.time()
        
        warming_tasks = []
        
        if self.config.warm_popular_stocks:
            warming_tasks.append(self.warm_popular_stocks())
        
        if self.config.warm_sector_data:
            warming_tasks.append(self.warm_sector_data())
        
        if self.config.warm_market_data:
            warming_tasks.append(self.warm_market_data())
        
        # Execute warming tasks in parallel
        if warming_tasks:
            results = await asyncio.gather(*warming_tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Cache warming task failed: {result}")
                    self.warming_stats["failed_warmings"] += 1
                else:
                    self.warming_stats["successful_warmings"] += 1
        
        duration = time.time() - start_time
        logger.info(f"Cache warming completed in {duration:.2f} seconds")
        self.warming_stats["total_warming_operations"] += 1
    
    async def warm_popular_stocks(self):
        """Warm cache for popular stocks"""
        logger.info(f"Warming cache for {len(self.config.popular_stocks)} popular stocks")
        
        # Process stocks in batches to avoid overwhelming APIs
        batch_size = self.config.max_concurrent_warming
        
        for i in range(0, len(self.config.popular_stocks), batch_size):
            batch = self.config.popular_stocks[i:i + batch_size]
            
            # Warm each stock in the batch
            warming_tasks = []
            for ticker in batch:
                warming_tasks.append(self._warm_single_stock(ticker))
            
            # Execute batch warming
            await asyncio.gather(*warming_tasks, return_exceptions=True)
            
            # Small delay between batches to be respectful to APIs
            if i + batch_size < len(self.config.popular_stocks):
                await asyncio.sleep(1.0)
        
        logger.info("Popular stocks cache warming completed")
    
    async def _warm_single_stock(self, ticker: str):
        """Warm cache for a single stock"""
        try:
            # Check if already warmed recently
            last_warmed = self.last_warming_time.get(ticker, 0)
            if time.time() - last_warmed < 1800:  # 30 minutes
                return
            
            # Warm stock data
            await self._warm_stock_data(ticker)
            
            # Update last warming time
            self.last_warming_time[ticker] = time.time()
            
            logger.debug(f"Cache warmed for {ticker}")
            
        except Exception as e:
            logger.warning(f"Failed to warm cache for {ticker}: {e}")
    
    async def _warm_stock_data(self, ticker: str):
        """Warm specific stock data"""
        try:
            # Warm basic info data
            cache_key_info = f"yfinance_info:{ticker}"
            if not await self.cache.get(cache_key_info):
                info_data = await fetch_info(ticker)
                if info_data:
                    await self.cache.set(cache_key_info, info_data, ttl=self.config.cache_ttl_hours * 3600)
            
            # Warm OHLCV data
            cache_key_ohlcv = f"yfinance_ohlcv:{ticker}:1y:1d"
            if not await self.cache.get(cache_key_ohlcv):
                ohlcv_data = await fetch_ohlcv(ticker, period="1y", interval="1d")
                if not ohlcv_data.empty:
                    # Convert DataFrame to dict for caching
                    ohlcv_dict = {
                        "data": ohlcv_data.to_dict('records'),
                        "index": ohlcv_data.index.tolist()
                    }
                    await self.cache.set(cache_key_ohlcv, ohlcv_dict, ttl=self.config.cache_ttl_hours * 3600)
            
            # Warm Indian market data for Indian stocks
            if ticker.endswith(('.NS', '.BO')):
                cache_key_indian = f"indian_market_data:{ticker}"
                if not await self.cache.get(cache_key_indian):
                    indian_data = await get_indian_market_data(ticker)
                    if indian_data:
                        await self.cache.set(cache_key_indian, indian_data, ttl=self.config.cache_ttl_hours * 3600)
            
        except Exception as e:
            logger.warning(f"Failed to warm stock data for {ticker}: {e}")
    
    async def warm_sector_data(self):
        """Warm sector rotation and market data"""
        logger.info("Warming sector rotation data")
        
        try:
            sector_analyzer = SectorRotationAnalyzer()
            
            # Warm Indian sector data
            cache_key_india = "sector_rotation:India"
            if not await self.cache.get(cache_key_india):
                india_data = await sector_analyzer.analyze_sector_rotation("India")
                if india_data:
                    await self.cache.set(cache_key_india, india_data, ttl=self.config.cache_ttl_hours * 3600)
            
            # Warm US sector data
            cache_key_us = "sector_rotation:United States"
            if not await self.cache.get(cache_key_us):
                us_data = await sector_analyzer.analyze_sector_rotation("United States")
                if us_data:
                    await self.cache.set(cache_key_us, us_data, ttl=self.config.cache_ttl_hours * 3600)
            
            logger.info("Sector data cache warming completed")
            
        except Exception as e:
            logger.warning(f"Failed to warm sector data: {e}")
    
    async def warm_market_data(self):
        """Warm general market data"""
        logger.info("Warming general market data")
        
        try:
            # Warm market indices
            market_indices = [
                "^GSPC",  # S&P 500
                "^IXIC",  # NASDAQ
                "^DJI",   # Dow Jones
                "^NSEI",  # Nifty 50
                "^BSESN"  # BSE Sensex
            ]
            
            for index in market_indices:
                cache_key = f"market_index:{index}"
                if not await self.cache.get(cache_key):
                    try:
                        info_data = await fetch_info(index)
                        if info_data:
                            await self.cache.set(cache_key, info_data, ttl=self.config.cache_ttl_hours * 3600)
                    except Exception as e:
                        logger.debug(f"Failed to warm market index {index}: {e}")
            
            logger.info("Market data cache warming completed")
            
        except Exception as e:
            logger.warning(f"Failed to warm market data: {e}")
    
    async def warm_specific_data(self, ticker: str, data_types: List[str]):
        """Warm specific data types for a ticker"""
        logger.info(f"Warming specific data for {ticker}: {data_types}")
        
        warming_tasks = []
        
        if "info" in data_types:
            warming_tasks.append(self._warm_stock_info(ticker))
        
        if "ohlcv" in data_types:
            warming_tasks.append(self._warm_stock_ohlcv(ticker))
        
        if "indian_data" in data_types and ticker.endswith(('.NS', '.BO')):
            warming_tasks.append(self._warm_indian_data(ticker))
        
        if warming_tasks:
            await asyncio.gather(*warming_tasks, return_exceptions=True)
    
    async def _warm_stock_info(self, ticker: str):
        """Warm stock info data"""
        cache_key = f"yfinance_info:{ticker}"
        if not await self.cache.get(cache_key):
            info_data = await fetch_info(ticker)
            if info_data:
                await self.cache.set(cache_key, info_data, ttl=self.config.cache_ttl_hours * 3600)
    
    async def _warm_stock_ohlcv(self, ticker: str):
        """Warm stock OHLCV data"""
        cache_key = f"yfinance_ohlcv:{ticker}:1y:1d"
        if not await self.cache.get(cache_key):
            ohlcv_data = await fetch_ohlcv(ticker, period="1y", interval="1d")
            if not ohlcv_data.empty:
                ohlcv_dict = {
                    "data": ohlcv_data.to_dict('records'),
                    "index": ohlcv_data.index.tolist()
                }
                await self.cache.set(cache_key, ohlcv_dict, ttl=self.config.cache_ttl_hours * 3600)
    
    async def _warm_indian_data(self, ticker: str):
        """Warm Indian market data"""
        cache_key = f"indian_market_data:{ticker}"
        if not await self.cache.get(cache_key):
            indian_data = await get_indian_market_data(ticker)
            if indian_data:
                await self.cache.set(cache_key, indian_data, ttl=self.config.cache_ttl_hours * 3600)
    
    def get_warming_stats(self) -> Dict[str, Any]:
        """Get cache warming statistics"""
        return {
            **self.warming_stats,
            "popular_stocks_count": len(self.config.popular_stocks),
            "last_warming_times": len(self.last_warming_time),
            "config": {
                "enabled": self.config.enabled,
                "warm_on_startup": self.config.warm_on_startup,
                "warming_interval_minutes": self.config.warming_interval_minutes,
                "cache_ttl_hours": self.config.cache_ttl_hours
            }
        }
    
    async def schedule_periodic_warming(self):
        """Schedule periodic cache warming"""
        while True:
            try:
                await asyncio.sleep(self.config.warming_interval_minutes * 60)
                await self.warm_all_data()
            except Exception as e:
                logger.error(f"Error in periodic cache warming: {e}")


# Global cache warmer instance
_cache_warmer: Optional[CacheWarmer] = None


async def get_cache_warmer() -> CacheWarmer:
    """Get the global cache warmer instance"""
    global _cache_warmer
    
    if _cache_warmer is None:
        _cache_warmer = CacheWarmer()
        await _cache_warmer.initialize()
    
    return _cache_warmer


# Convenience functions
async def warm_cache_for_stocks(tickers: List[str]):
    """Warm cache for specific stocks"""
    warmer = await get_cache_warmer()
    for ticker in tickers:
        await warmer._warm_single_stock(ticker)


async def warm_cache_for_data_types(ticker: str, data_types: List[str]):
    """Warm specific data types for a ticker"""
    warmer = await get_cache_warmer()
    await warmer.warm_specific_data(ticker, data_types)


async def get_cache_warming_stats() -> Dict[str, Any]:
    """Get cache warming statistics"""
    warmer = await get_cache_warmer()
    return warmer.get_warming_stats()
