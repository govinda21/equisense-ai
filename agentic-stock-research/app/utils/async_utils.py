"""
Async processing utilities for performance optimization
"""
from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, Union
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

class AsyncProcessor:
    """
    High-performance async processing with concurrency control
    """
    
    def __init__(self, max_workers: int = 10, semaphore_limit: int = 50):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(semaphore_limit)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
    
    async def gather_with_concurrency(
        self,
        *awaitables: Awaitable[T],
        return_exceptions: bool = False,
        timeout: Optional[float] = None
    ) -> List[Union[T, Exception]]:
        """
        Gather awaitables with concurrency control and timeout
        
        Args:
            *awaitables: Async functions to execute
            return_exceptions: Whether to return exceptions instead of raising
            timeout: Timeout for the entire operation
            
        Returns:
            List of results or exceptions
        """
        if not awaitables:
            return []
        
        async def _controlled_awaitable(awaitable: Awaitable[T]) -> Union[T, Exception]:
            async with self.semaphore:
                try:
                    if timeout:
                        return await asyncio.wait_for(awaitable, timeout=timeout / len(awaitables))
                    return await awaitable
                except Exception as e:
                    if return_exceptions:
                        return e
                    raise
        
        start_time = time.time()
        controlled_awaitables = [_controlled_awaitable(aw) for aw in awaitables]
        
        try:
            if timeout:
                results = await asyncio.wait_for(
                    asyncio.gather(*controlled_awaitables, return_exceptions=return_exceptions),
                    timeout=timeout
                )
            else:
                results = await asyncio.gather(*controlled_awaitables, return_exceptions=return_exceptions)
                
            duration = time.time() - start_time
            logger.debug(f"Processed {len(awaitables)} tasks in {duration:.2f}s")
            
            return results
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout after {timeout}s processing {len(awaitables)} tasks")
            raise
    
    async def process_in_batches(
        self,
        items: List[Any],
        processor: Callable[[Any], Awaitable[T]],
        batch_size: int = 5,
        delay_between_batches: float = 0.1
    ) -> List[T]:
        """
        Process items in batches to avoid overwhelming APIs
        
        Args:
            items: Items to process
            processor: Async function to process each item
            batch_size: Number of items per batch
            delay_between_batches: Delay between batches in seconds
            
        Returns:
            List of processed results
        """
        if not items:
            return []
        
        results = []
        total_batches = (len(items) + batch_size - 1) // batch_size
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)")
            
            batch_awaitables = [processor(item) for item in batch]
            batch_results = await self.gather_with_concurrency(
                *batch_awaitables,
                return_exceptions=True
            )
            
            # Filter out exceptions and log them
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.warning(f"Failed to process item {batch[j]}: {result}")
                else:
                    results.append(result)
            
            # Delay between batches (except for the last one)
            if batch_num < total_batches and delay_between_batches > 0:
                await asyncio.sleep(delay_between_batches)
        
        logger.info(f"Successfully processed {len(results)}/{len(items)} items")
        return results
    
    async def run_in_executor(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Run a synchronous function in the thread pool executor
        
        Args:
            func: Synchronous function to run
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)


class PerformanceMonitor:
    """
    Monitor and log performance metrics
    """
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
    
    def record_timing(self, operation: str, duration: float):
        """Record timing for an operation"""
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(duration)
    
    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for an operation"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}
        
        times = self.metrics[operation]
        return {
            "count": len(times),
            "total": sum(times),
            "average": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
            "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0]
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all operations"""
        return {op: self.get_stats(op) for op in self.metrics}


# Performance monitoring decorator
def monitor_performance(operation_name: str):
    """
    Decorator to monitor async function performance
    
    Example:
        @monitor_performance("data_fetch")
        async def fetch_data():
            pass
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log performance
                logger.debug(f"{operation_name} completed in {duration:.3f}s")
                
                # Record in global monitor if available
                if hasattr(wrapper, '_performance_monitor'):
                    wrapper._performance_monitor.record_timing(operation_name, duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.warning(f"{operation_name} failed after {duration:.3f}s: {e}")
                raise
        
        return wrapper
    return decorator


# Global performance monitor
_performance_monitor = PerformanceMonitor()

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor"""
    return _performance_monitor


# Utility functions for common async patterns
async def timeout_after(seconds: float, coro: Awaitable[T], default: T = None) -> T:
    """
    Run coroutine with timeout, returning default on timeout
    
    Args:
        seconds: Timeout in seconds
        coro: Coroutine to run
        default: Default value to return on timeout
        
    Returns:
        Coroutine result or default value
    """
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {seconds}s")
        return default


async def retry_with_backoff(
    coro_func: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> T:
    """
    Retry coroutine with exponential backoff
    
    Args:
        coro_func: Function that returns a coroutine
        max_retries: Maximum number of retries
        base_delay: Initial delay between retries
        backoff_factor: Multiplier for delay on each retry
        exceptions: Exceptions to catch and retry
        
    Returns:
        Coroutine result
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except exceptions as e:
            last_exception = e
            if attempt == max_retries:
                break
            
            delay = base_delay * (backoff_factor ** attempt)
            logger.debug(f"Retry {attempt + 1}/{max_retries} after {delay:.2f}s delay")
            await asyncio.sleep(delay)
    
    raise last_exception


async def race_with_timeout(
    coros: List[Awaitable[T]],
    timeout: float
) -> List[Optional[T]]:
    """
    Race multiple coroutines with a global timeout
    
    Args:
        coros: List of coroutines to race
        timeout: Global timeout in seconds
        
    Returns:
        List of results (None for timed out coroutines)
    """
    if not coros:
        return []
    
    results = [None] * len(coros)
    
    async def _run_with_index(index: int, coro: Awaitable[T]):
        try:
            results[index] = await coro
        except Exception as e:
            logger.warning(f"Coroutine {index} failed: {e}")
            results[index] = None
    
    tasks = [_run_with_index(i, coro) for i, coro in enumerate(coros)]
    
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Some operations timed out after {timeout}s")
    
    return results
