"""
Retry utilities for robust API error handling
"""
from __future__ import annotations

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, Type, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RetryError(Exception):
    """Raised when all retry attempts are exhausted"""
    pass

async def exponential_backoff_async(
    func: Callable[..., Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    *args,
    **kwargs
) -> Any:
    """
    Execute async function with exponential backoff retry logic
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        backoff_factor: Multiplier for delay on each retry
        jitter: Add random jitter to delays
        exceptions: Tuple of exceptions to catch and retry
        
    Returns:
        Result of successful function call
        
    Raises:
        RetryError: When all retries are exhausted
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            if attempt > 0:
                logger.info(f"Function {func.__name__} succeeded on attempt {attempt + 1}")
            return result
            
        except exceptions as e:
            last_exception = e
            
            if attempt == max_retries:
                logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts. Last error: {e}")
                break
                
            # Calculate delay with exponential backoff
            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            if jitter:
                delay *= (0.5 + random.random())  # Add 0-50% jitter
                
            logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}, retrying in {delay:.2f}s. Error: {e}")
            await asyncio.sleep(delay)
    
    raise RetryError(f"All retry attempts exhausted for {func.__name__}") from last_exception


def retry_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for async functions with exponential backoff retry
    
    Example:
        @retry_async(max_retries=3, base_delay=1.0, exceptions=(httpx.HTTPError, yfinance.YFinanceError))
        async def fetch_data():
            # Your API call here
            pass
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await exponential_backoff_async(
                func, max_retries, base_delay, max_delay, backoff_factor, jitter, exceptions,
                *args, **kwargs
            )
        return wrapper
    return decorator


def circuit_breaker_async(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception
):
    """
    Circuit breaker pattern for async functions
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time to wait before attempting recovery (seconds)
        expected_exception: Exception type to count as failure
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Circuit state
        failure_count = 0
        last_failure_time = None
        is_open = False
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal failure_count, last_failure_time, is_open
            
            # Check if circuit should be closed (recovery attempt)
            if is_open and last_failure_time:
                if asyncio.get_event_loop().time() - last_failure_time > recovery_timeout:
                    is_open = False
                    failure_count = 0
                    logger.info(f"Circuit breaker for {func.__name__} attempting recovery")
                else:
                    raise RetryError(f"Circuit breaker open for {func.__name__}")
            
            try:
                result = await func(*args, **kwargs)
                # Reset on success
                if failure_count > 0:
                    logger.info(f"Circuit breaker for {func.__name__} reset after success")
                    failure_count = 0
                    is_open = False
                return result
                
            except expected_exception as e:
                failure_count += 1
                last_failure_time = asyncio.get_event_loop().time()
                
                if failure_count >= failure_threshold:
                    is_open = True
                    logger.error(f"Circuit breaker opened for {func.__name__} after {failure_count} failures")
                
                raise e
                
        return wrapper
    return decorator
