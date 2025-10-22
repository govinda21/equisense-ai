"""
Optimized Cache Manager for High-Performance Data Retrieval

This module provides enhanced caching capabilities with:
- Multi-level caching (memory + Redis)
- Intelligent cache warming
- Batch operations
- Performance monitoring
- Smart invalidation strategies
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from collections import defaultdict
import json
import pickle

from app.cache.redis_cache import CacheManager, get_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0
    average_get_time: float = 0.0
    average_set_time: float = 0.0


class OptimizedCacheManager:
    """
    High-performance cache manager with multi-level caching and optimizations
    """
    
    def __init__(self, redis_cache: Optional[CacheManager] = None):
        self.redis_cache = redis_cache or CacheManager()
        self.memory_cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry)
        self.metrics = CacheMetrics()
        self.batch_operations: Dict[str, List[Tuple[str, Any, Optional[float]]]] = defaultdict(list)
        self.cache_warming_queue: List[str] = []
        
        # Performance settings
        self.memory_cache_size_limit = 1000  # Max items in memory cache
        self.batch_size = 50  # Batch operations size
        self.warming_concurrency = 10  # Concurrent cache warming
        
        logger.info("Initialized OptimizedCacheManager with multi-level caching")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with multi-level fallback"""
        start_time = time.time()
        self.metrics.total_requests += 1
        
        # Level 1: Memory cache (fastest)
        if key in self.memory_cache:
            value, expiry = self.memory_cache[key]
            if time.time() < expiry:
                self.metrics.hits += 1
                self.metrics.hit_rate = self.metrics.hits / self.metrics.total_requests
                self.metrics.average_get_time = (self.metrics.average_get_time + (time.time() - start_time)) / 2
                return value
            else:
                # Expired, remove from memory cache
                del self.memory_cache[key]
        
        # Level 2: Redis cache
        try:
            value = await self.redis_cache.get(key)
            if value is not None:
                # Store in memory cache for faster future access
                await self._store_in_memory(key, value, ttl=3600)  # 1 hour in memory
                self.metrics.hits += 1
                self.metrics.hit_rate = self.metrics.hits / self.metrics.total_requests
                self.metrics.average_get_time = (self.metrics.average_get_time + (time.time() - start_time)) / 2
                return value
        except Exception as e:
            logger.warning(f"Redis cache get failed for {key}: {e}")
        
        # Cache miss
        self.metrics.misses += 1
        self.metrics.hit_rate = self.metrics.hits / self.metrics.total_requests
        self.metrics.average_get_time = (self.metrics.average_get_time + (time.time() - start_time)) / 2
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set value in cache with multi-level storage"""
        start_time = time.time()
        self.metrics.sets += 1
        
        try:
            # Store in both memory and Redis
            await self._store_in_memory(key, value, ttl)
            await self.redis_cache.set(key, value, ttl)
            
            self.metrics.average_set_time = (self.metrics.average_set_time + (time.time() - start_time)) / 2
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed for {key}: {e}")
            return False
    
    async def _store_in_memory(self, key: str, value: Any, ttl: Optional[float] = None):
        """Store value in memory cache with size management"""
        # Clean up expired entries
        current_time = time.time()
        expired_keys = [
            k for k, (_, expiry) in self.memory_cache.items() 
            if current_time >= expiry
        ]
        for k in expired_keys:
            del self.memory_cache[k]
        
        # Manage cache size
        if len(self.memory_cache) >= self.memory_cache_size_limit:
            # Remove oldest entries (simple LRU approximation)
            oldest_keys = list(self.memory_cache.keys())[:len(self.memory_cache) // 2]
            for k in oldest_keys:
                del self.memory_cache[k]
        
        # Store new value
        expiry = current_time + (ttl or 3600)  # Default 1 hour
        self.memory_cache[key] = (value, expiry)
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values efficiently"""
        results = {}
        
        # Check memory cache first
        memory_hits = {}
        current_time = time.time()
        
        for key in keys:
            if key in self.memory_cache:
                value, expiry = self.memory_cache[key]
                if current_time < expiry:
                    memory_hits[key] = value
                    results[key] = value
        
        # Get remaining keys from Redis
        remaining_keys = [k for k in keys if k not in memory_hits]
        if remaining_keys:
            try:
                redis_results = await self.redis_cache.get_many(remaining_keys)
                results.update(redis_results)
                
                # Store Redis results in memory cache
                for key, value in redis_results.items():
                    await self._store_in_memory(key, value, ttl=3600)
                    
            except Exception as e:
                logger.warning(f"Redis batch get failed: {e}")
        
        return results
    
    async def set_many(self, items: Dict[str, Any], ttl: Optional[float] = None) -> bool:
        """Set multiple values efficiently"""
        try:
            # Store in memory cache
            for key, value in items.items():
                await self._store_in_memory(key, value, ttl)
            
            # Store in Redis
            await self.redis_cache.set_many(items, ttl)
            return True
            
        except Exception as e:
            logger.error(f"Batch set failed: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from all cache levels"""
        self.metrics.deletes += 1
        
        # Remove from memory cache
        if key in self.memory_cache:
            del self.memory_cache[key]
        
        # Remove from Redis
        try:
            return await self.redis_cache.delete(key)
        except Exception as e:
            logger.warning(f"Redis delete failed for {key}: {e}")
            return False
    
    async def warm_cache(self, keys: List[str], fetch_func, ttl: Optional[float] = None):
        """Warm cache with frequently accessed data"""
        logger.info(f"Warming cache with {len(keys)} keys")
        
        # Process in batches
        for i in range(0, len(keys), self.warming_concurrency):
            batch = keys[i:i + self.warming_concurrency]
            
            # Fetch data in parallel
            tasks = [fetch_func(key) for key in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Store successful results
            items_to_cache = {}
            for key, result in zip(batch, results):
                if not isinstance(result, Exception) and result is not None:
                    items_to_cache[key] = result
            
            if items_to_cache:
                await self.set_many(items_to_cache, ttl)
        
        logger.info(f"Cache warming completed for {len(keys)} keys")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        return {
            "hits": self.metrics.hits,
            "misses": self.metrics.misses,
            "hit_rate": f"{self.metrics.hit_rate:.1%}",
            "total_requests": self.metrics.total_requests,
            "sets": self.metrics.sets,
            "deletes": self.metrics.deletes,
            "average_get_time": f"{self.metrics.average_get_time:.3f}s",
            "average_set_time": f"{self.metrics.average_set_time:.3f}s",
            "memory_cache_size": len(self.memory_cache),
            "memory_cache_limit": self.memory_cache_size_limit
        }
    
    async def clear_memory_cache(self):
        """Clear memory cache"""
        self.memory_cache.clear()
        logger.info("Memory cache cleared")
    
    async def optimize_cache(self):
        """Optimize cache performance"""
        # Clean up expired entries
        current_time = time.time()
        expired_keys = [
            k for k, (_, expiry) in self.memory_cache.items() 
            if current_time >= expiry
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


# Global optimized cache manager instance
_optimized_cache_manager: Optional[OptimizedCacheManager] = None


async def get_optimized_cache_manager() -> OptimizedCacheManager:
    """Get the global optimized cache manager instance"""
    global _optimized_cache_manager
    
    if _optimized_cache_manager is None:
        redis_cache = await get_cache_manager()
        _optimized_cache_manager = OptimizedCacheManager(redis_cache)
    
    return _optimized_cache_manager


# Convenience functions
async def cache_get(key: str) -> Optional[Any]:
    """Get value from optimized cache"""
    cache = await get_optimized_cache_manager()
    return await cache.get(key)


async def cache_set(key: str, value: Any, ttl: Optional[float] = None) -> bool:
    """Set value in optimized cache"""
    cache = await get_optimized_cache_manager()
    return await cache.set(key, value, ttl)


async def cache_get_many(keys: List[str]) -> Dict[str, Any]:
    """Get multiple values from optimized cache"""
    cache = await get_optimized_cache_manager()
    return await cache.get_many(keys)


async def cache_set_many(items: Dict[str, Any], ttl: Optional[float] = None) -> bool:
    """Set multiple values in optimized cache"""
    cache = await get_optimized_cache_manager()
    return await cache.set_many(items, ttl)
