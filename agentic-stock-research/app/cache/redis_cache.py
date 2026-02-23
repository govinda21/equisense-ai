"""
Redis-based caching system for financial data
"""
from __future__ import annotations

import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional, Union
import asyncio
import os

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

class CacheManager:
    """
    Redis-based cache manager with fallback to in-memory caching
    """
    
    def __init__(
        self, 
        redis_url: Optional[str] = None, 
        default_ttl: int = 300,
        max_connections: int = 10,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0
    ):
        """
        Initialize cache manager
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live for cache entries (seconds)
            max_connections: Maximum connections in the pool
            socket_timeout: Socket timeout (seconds)
            socket_connect_timeout: Socket connect timeout (seconds)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.redis_client: Optional[redis.Redis] = None
        self._memory_cache: dict[str, tuple[Any, datetime]] = {}
        self._use_redis = REDIS_AVAILABLE
        self._connected = False
        
        # Connection pool stats
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def connect(self) -> bool:
        """Initialize Redis connection with connection pooling"""
        if not self._use_redis:
            logger.warning("Redis not available, falling back to in-memory cache")
            return False
            
        try:
            # Create connection pool for better performance
            pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_connect_timeout,
                decode_responses=False
            )
            
            self.redis_client = redis.Redis(connection_pool=pool)
            await self.redis_client.ping()
            self._connected = True
            logger.info(
                f"Connected to Redis at {self.redis_url} "
                f"(pool size: {self.max_connections}, timeout: {self.socket_timeout}s)"
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Redis ({e}), using in-memory cache")
            self._use_redis = False
            return False
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
    
    def _make_key(self, prefix: str, identifier: str, **kwargs) -> str:
        """Create cache key with optional parameters"""
        key_parts = [prefix, identifier]
        if kwargs:
            # Sort kwargs for consistent key generation
            params = "&".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            key_parts.append(params)
        return ":".join(key_parts)
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache with hit/miss tracking"""
        try:
            if self._use_redis and self.redis_client and self._connected:
                data = await self.redis_client.get(key)
                if data:
                    self.cache_hits += 1
                    return pickle.loads(data)
                else:
                    self.cache_misses += 1
            else:
                # In-memory fallback
                if key in self._memory_cache:
                    value, expiry = self._memory_cache[key]
                    if datetime.now() < expiry:
                        self.cache_hits += 1
                        return value
                    else:
                        del self._memory_cache[key]
                        self.cache_misses += 1
                else:
                    self.cache_misses += 1
            
            return default
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        ttl = ttl or self.default_ttl
        
        try:
            if self._use_redis and self.redis_client and self._connected:
                data = pickle.dumps(value)
                await self.redis_client.setex(key, ttl, data)
                return True
            else:
                # In-memory fallback
                expiry = datetime.now() + timedelta(seconds=ttl)
                self._memory_cache[key] = (value, expiry)
                
                # Cleanup expired entries occasionally
                if len(self._memory_cache) > 1000:
                    await self._cleanup_memory_cache()
                
                return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            if self._use_redis and self.redis_client and self._connected:
                await self.redis_client.delete(key)
            else:
                self._memory_cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def clear_all(self) -> bool:
        """Clear all cache data (Redis and in-memory)"""
        try:
            cleared_count = 0
            if self._use_redis and self.redis_client and self._connected:
                # Flush all Redis keys
                await self.redis_client.flushdb()
                cleared_count = await self.redis_client.dbsize()
                logger.info(f"Cleared all Redis cache data ({cleared_count} keys)")
            
            # Clear in-memory cache
            memory_count = len(self._memory_cache)
            self._memory_cache.clear()
            cleared_count += memory_count
            logger.info(f"Cleared in-memory cache ({memory_count} entries)")
            
            # Reset cache stats
            self.cache_hits = 0
            self.cache_misses = 0
            
            logger.info(f"✅ Cache cleared successfully: {cleared_count} total entries removed")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    async def clear_ticker(self, ticker: str) -> bool:
        """Clear all cache data for a specific ticker"""
        try:
            cleared_count = 0
            if self._use_redis and self.redis_client and self._connected:
                # Find and delete all keys for this ticker
                pattern = f"*:{ticker}*"
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern):
                    keys.append(key)
                
                if keys:
                    await self.redis_client.delete(*keys)
                    cleared_count = len(keys)
                    logger.info(f"[{ticker}] Cleared {cleared_count} Redis cache entries")
            
            # Clear in-memory cache for this ticker
            memory_keys = [k for k in self._memory_cache.keys() if ticker in k]
            for key in memory_keys:
                del self._memory_cache[key]
            cleared_count += len(memory_keys)
            
            if cleared_count > 0:
                logger.info(f"[{ticker}] Cleared {cleared_count} total cache entries")
            return True
        except Exception as e:
            logger.error(f"Cache clear error for {ticker}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            if self._use_redis and self.redis_client and self._connected:
                return bool(await self.redis_client.exists(key))
            else:
                if key in self._memory_cache:
                    _, expiry = self._memory_cache[key]
                    if datetime.now() < expiry:
                        return True
                    else:
                        del self._memory_cache[key]
                return False
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def _cleanup_memory_cache(self):
        """Remove expired entries from memory cache"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expiry) in self._memory_cache.items() 
            if now >= expiry
        ]
        for key in expired_keys:
            del self._memory_cache[key]
        
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    # Financial data specific cache methods
    async def get_ohlcv(self, ticker: str, period: str = "1y", interval: str = "1d") -> Any:
        """Get OHLCV data from cache"""
        key = self._make_key("ohlcv", ticker, period=period, interval=interval)
        return await self.get(key)
    
    async def set_ohlcv(self, ticker: str, data: Any, period: str = "1y", interval: str = "1d", ttl: int = 900) -> bool:
        """Cache OHLCV data (15 min TTL for market data)"""
        key = self._make_key("ohlcv", ticker, period=period, interval=interval)
        return await self.set(key, data, ttl)
    
    async def get_company_info(self, ticker: str) -> Any:
        """Get company info from cache"""
        key = self._make_key("info", ticker)
        return await self.get(key)
    
    async def set_company_info(self, ticker: str, data: Any, ttl: int = 3600) -> bool:
        """Cache company info (1 hour TTL)"""
        key = self._make_key("info", ticker)
        return await self.set(key, data, ttl)
    
    async def get_news(self, ticker: str) -> Any:
        """Get news from cache"""
        key = self._make_key("news", ticker)
        return await self.get(key)
    
    async def set_news(self, ticker: str, data: Any, ttl: int = 600) -> bool:
        """Cache news data (10 min TTL)"""
        key = self._make_key("news", ticker)
        return await self.set(key, data, ttl)
    
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            "cache_type": "redis" if (self._use_redis and self._connected) else "in_memory",
            "connected": self._connected,
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "total_requests": total_requests,
            "hit_rate": round(hit_rate, 2),
        }
        
        if self._use_redis and self.redis_client:
            stats["connection_pool"] = {
                "max_connections": self.max_connections,
                "socket_timeout": self.socket_timeout
            }
        
        if not self._use_redis:
            stats["memory_cache_size"] = len(self._memory_cache)
        
        return stats


# Global cache instance
_cache_manager: Optional[CacheManager] = None

async def get_cache_manager() -> CacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        await _cache_manager.connect()
    return _cache_manager

async def close_cache():
    """Close cache connections"""
    global _cache_manager
    if _cache_manager:
        await _cache_manager.disconnect()
        _cache_manager = None

async def clear_all_cache():
    """Clear all cache data"""
    cache = await get_cache_manager()
    return await cache.clear_all()

async def clear_ticker_cache(ticker: str):
    """Clear cache data for a specific ticker"""
    cache = await get_cache_manager()
    return await cache.clear_ticker(ticker)
