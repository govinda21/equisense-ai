"""
Performance optimization utilities for EquiSense AI
Implements caching, database optimization, and performance monitoring
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from functools import wraps

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available. System monitoring will be limited.")

import gc

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring"""
    request_count: int = 0
    total_response_time: float = 0.0
    average_response_time: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    cache_hit_rate: float = 0.0
    error_count: int = 0
    last_updated: datetime = None


class PerformanceMonitor:
    """Performance monitoring and optimization"""
    
    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.start_time = time.time()
        
    def update_metrics(self):
        """Update current performance metrics"""
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            self.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            self.metrics.cpu_usage_percent = process.cpu_percent()
        else:
            # Fallback values when psutil is not available
            self.metrics.memory_usage_mb = 0.0
            self.metrics.cpu_usage_percent = 0.0
            
        self.metrics.last_updated = datetime.now()
        
    def get_uptime(self) -> float:
        """Get application uptime in seconds"""
        return time.time() - self.start_time
        
    def get_health_score(self) -> float:
        """Calculate overall health score (0-100)"""
        score = 100.0
        
        # Deduct points for high memory usage
        if self.metrics.memory_usage_mb > 1000:  # > 1GB
            score -= min(20, (self.metrics.memory_usage_mb - 1000) / 50)
            
        # Deduct points for high CPU usage
        if self.metrics.cpu_usage_percent > 80:
            score -= min(20, (self.metrics.cpu_usage_percent - 80) / 2)
            
        # Deduct points for slow response times
        if self.metrics.average_response_time > 2.0:  # > 2 seconds
            score -= min(20, (self.metrics.average_response_time - 2.0) * 10)
            
        # Deduct points for high error rate
        if self.metrics.request_count > 0:
            error_rate = self.metrics.error_count / self.metrics.request_count
            if error_rate > 0.05:  # > 5% error rate
                score -= min(20, error_rate * 400)
                
        return max(0, score)


def performance_timer(func: Callable) -> Callable:
    """Decorator to measure function execution time"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
            
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
            
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


class CacheOptimizer:
    """Cache optimization utilities"""
    
    def __init__(self):
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
        
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.cache_stats["hits"] + self.cache_stats["misses"]
        if total == 0:
            return 0.0
        return self.cache_stats["hits"] / total
        
    def record_hit(self):
        """Record a cache hit"""
        self.cache_stats["hits"] += 1
        
    def record_miss(self):
        """Record a cache miss"""
        self.cache_stats["misses"] += 1
        
    def record_set(self):
        """Record a cache set operation"""
        self.cache_stats["sets"] += 1
        
    def record_delete(self):
        """Record a cache delete operation"""
        self.cache_stats["deletes"] += 1


class DatabaseOptimizer:
    """Database optimization utilities"""
    
    def __init__(self):
        self.query_stats = {
            "total_queries": 0,
            "slow_queries": 0,
            "failed_queries": 0,
            "total_query_time": 0.0
        }
        
    def record_query(self, execution_time: float, success: bool = True):
        """Record database query statistics"""
        self.query_stats["total_queries"] += 1
        self.query_stats["total_query_time"] += execution_time
        
        if execution_time > 1.0:  # Slow query threshold
            self.query_stats["slow_queries"] += 1
            
        if not success:
            self.query_stats["failed_queries"] += 1
            
    def get_average_query_time(self) -> float:
        """Get average query execution time"""
        if self.query_stats["total_queries"] == 0:
            return 0.0
        return self.query_stats["total_query_time"] / self.query_stats["total_queries"]
        
    def get_slow_query_rate(self) -> float:
        """Get slow query rate"""
        if self.query_stats["total_queries"] == 0:
            return 0.0
        return self.query_stats["slow_queries"] / self.query_stats["total_queries"]


class MemoryOptimizer:
    """Memory optimization utilities"""
    
    def __init__(self):
        self.memory_threshold_mb = 500  # 500MB threshold
        
    def check_memory_usage(self) -> Dict[str, Any]:
        """Check current memory usage"""
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
                "percent": process.memory_percent(),
                "available_mb": psutil.virtual_memory().available / 1024 / 1024
            }
        else:
            return {
                "rss_mb": 0.0,
                "vms_mb": 0.0,
                "percent": 0.0,
                "available_mb": 0.0
            }
        
    def cleanup_memory(self):
        """Perform memory cleanup"""
        logger.info("Performing memory cleanup...")
        
        # Force garbage collection
        collected = gc.collect()
        logger.info(f"Garbage collection freed {collected} objects")
        
        # Get memory usage after cleanup
        memory_usage = self.check_memory_usage()
        logger.info(f"Memory usage after cleanup: {memory_usage['rss_mb']:.1f}MB")
        
        return memory_usage


class AsyncOptimizer:
    """Async operation optimization"""
    
    def __init__(self):
        self.max_concurrent_requests = 100
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
    async def limit_concurrency(self, coro):
        """Limit concurrent operations"""
        async with self.semaphore:
            return await coro
            
    async def batch_process(self, items: List[Any], batch_size: int = 10, 
                          processor: Callable = None) -> List[Any]:
        """Process items in batches"""
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            if processor:
                batch_results = await asyncio.gather(*[
                    processor(item) for item in batch
                ], return_exceptions=True)
            else:
                batch_results = batch
                
            results.extend(batch_results)
            
        return results


class PerformanceOptimizer:
    """Main performance optimization manager"""
    
    def __init__(self):
        self.monitor = PerformanceMonitor()
        self.cache_optimizer = CacheOptimizer()
        self.db_optimizer = DatabaseOptimizer()
        self.memory_optimizer = MemoryOptimizer()
        self.async_optimizer = AsyncOptimizer()
        
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        self.monitor.update_metrics()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": self.monitor.get_uptime(),
            "health_score": self.monitor.get_health_score(),
            "metrics": {
                "memory_usage_mb": self.monitor.metrics.memory_usage_mb,
                "cpu_usage_percent": self.monitor.metrics.cpu_usage_percent,
                "average_response_time": self.monitor.metrics.average_response_time,
                "request_count": self.monitor.metrics.request_count,
                "error_count": self.monitor.metrics.error_count
            },
            "cache_performance": {
                "hit_rate": self.cache_optimizer.get_hit_rate(),
                "stats": self.cache_optimizer.cache_stats
            },
            "database_performance": {
                "average_query_time": self.db_optimizer.get_average_query_time(),
                "slow_query_rate": self.db_optimizer.get_slow_query_rate(),
                "stats": self.db_optimizer.query_stats
            },
            "memory_status": self.memory_optimizer.check_memory_usage()
        }
        
    async def optimize_performance(self):
        """Run performance optimization routines"""
        logger.info("Starting performance optimization...")
        
        # Check memory usage
        memory_usage = self.memory_optimizer.check_memory_usage()
        if memory_usage["rss_mb"] > self.memory_optimizer.memory_threshold_mb:
            logger.warning(f"High memory usage: {memory_usage['rss_mb']:.1f}MB")
            self.memory_optimizer.cleanup_memory()
            
        # Update metrics
        self.monitor.update_metrics()
        
        # Log performance report
        report = self.get_performance_report()
        logger.info(f"Performance report: Health score {report['health_score']:.1f}/100")
        
        return report


# Global performance optimizer instance
_performance_optimizer = None

def get_performance_optimizer() -> PerformanceOptimizer:
    """Get the global performance optimizer instance"""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer
