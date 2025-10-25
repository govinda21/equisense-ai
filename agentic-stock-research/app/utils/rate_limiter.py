"""
Comprehensive Rate Limiting and Retry System for EquiSense AI

This module provides intelligent rate limiting, retry logic, and circuit breaker patterns
to handle API failures gracefully and prevent system overload.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import yfinance as yf
import pandas as pd
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_limit: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    window_size: int = 60  # seconds
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0


@dataclass
class APIConfig:
    """API-specific configuration"""
    name: str
    base_url: str
    rate_limit: RateLimitConfig
    timeout: int = 30
    retry_exceptions: List[Type[Exception]] = field(default_factory=lambda: [Exception])
    success_codes: List[int] = field(default_factory=lambda: [200, 201, 202])
    user_agent: str = "EquiSense AI Research Bot (research@equisense.ai)"


class RateLimiter:
    """Intelligent rate limiter with multiple strategies"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.request_times: List[float] = []
        self.tokens = config.burst_limit
        self.last_refill = time.time()
        self.semaphore = asyncio.Semaphore(config.burst_limit)
        
    async def acquire(self) -> bool:
        """Acquire permission to make a request"""
        await self.semaphore.acquire()
        
        if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return await self._token_bucket_acquire()
        elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return await self._fixed_window_acquire()
        elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return await self._sliding_window_acquire()
        else:
            return True
    
    async def _token_bucket_acquire(self) -> bool:
        """Token bucket rate limiting"""
        now = time.time()
        time_passed = now - self.last_refill
        
        # Refill tokens based on time passed
        tokens_to_add = time_passed * (self.config.requests_per_minute / 60.0)
        self.tokens = min(self.config.burst_limit, self.tokens + tokens_to_add)
        self.last_refill = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        
        # Calculate wait time
        wait_time = (1 - self.tokens) / (self.config.requests_per_minute / 60.0)
        await asyncio.sleep(wait_time)
        self.tokens = 0
        return True
    
    async def _fixed_window_acquire(self) -> bool:
        """Fixed window rate limiting"""
        now = time.time()
        window_start = now - self.config.window_size
        
        # Remove old requests
        self.request_times = [t for t in self.request_times if t > window_start]
        
        if len(self.request_times) < self.config.requests_per_minute:
            self.request_times.append(now)
            return True
        
        # Calculate wait time
        oldest_request = min(self.request_times)
        wait_time = oldest_request + self.config.window_size - now
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        self.request_times.append(time.time())
        return True
    
    async def _sliding_window_acquire(self) -> bool:
        """Sliding window rate limiting"""
        now = time.time()
        window_start = now - self.config.window_size
        
        # Remove old requests
        self.request_times = [t for t in self.request_times if t > window_start]
        
        if len(self.request_times) < self.config.requests_per_minute:
            self.request_times.append(now)
            return True
        
        # Calculate wait time for oldest request to expire
        oldest_request = min(self.request_times)
        wait_time = oldest_request + self.config.window_size - now
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        self.request_times.append(time.time())
        return True
    
    def release(self):
        """Release the semaphore"""
        self.semaphore.release()


class CircuitBreaker:
    """Circuit breaker pattern for handling cascading failures"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            
            raise e


class RetryManager:
    """Intelligent retry manager with exponential backoff"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        
    async def retry(self, func: Callable, *args, **kwargs):
        """Retry function with exponential backoff"""
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt == self.config.max_retries:
                    logger.error(f"Max retries ({self.config.max_retries}) exceeded for {func.__name__}")
                    break
                
                # Calculate delay with exponential backoff
                delay = min(
                    self.config.base_delay * (self.config.backoff_multiplier ** attempt),
                    self.config.max_delay
                )
                
                # Add jitter to prevent thundering herd
                jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)
                delay += jitter
                
                logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
        
        raise last_exception


class APIClient:
    """Unified API client with rate limiting, retry, and circuit breaker"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.rate_limiter = RateLimiter(config.rate_limit)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.rate_limit.max_retries,
            recovery_timeout=config.rate_limit.max_delay
        )
        self.retry_manager = RetryManager(config.rate_limit)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.config.user_agent}
            )
        return self.session
    
    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with rate limiting and retry"""
        async def _make_request():
            await self.rate_limiter.acquire()
            
            try:
                session = await self._get_session()
                async with session.request(method, url, **kwargs) as response:
                    if response.status in self.config.success_codes:
                        return await response.json()
                    else:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=f"HTTP {response.status}"
                        )
            finally:
                self.rate_limiter.release()
        
        return await self.circuit_breaker.call(
            self.retry_manager.retry,
            _make_request
        )


# Global API clients for different services
class APIClientManager:
    """Manages API clients for different services"""
    
    def __init__(self):
        self.clients: Dict[str, APIClient] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize API clients for different services"""
        
        # Yahoo Finance client
        yahoo_config = APIConfig(
            name="yahoo_finance",
            base_url="https://query1.finance.yahoo.com",
            rate_limit=RateLimitConfig(
                requests_per_minute=30,  # Conservative limit
                requests_per_hour=1000,
                burst_limit=5,
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                max_retries=3,
                base_delay=2.0,
                max_delay=30.0
            ),
            timeout=30,
            retry_exceptions=[aiohttp.ClientError, Exception],
            user_agent="EquiSense AI Research Bot (research@equisense.ai)"
        )
        self.clients["yahoo_finance"] = APIClient(yahoo_config)
        
        # MoneyControl client - More conservative settings
        moneycontrol_config = APIConfig(
            name="moneycontrol",
            base_url="https://www.moneycontrol.com",
            rate_limit=RateLimitConfig(
                requests_per_minute=5,  # Very conservative - reduced from 10
                requests_per_hour=50,   # Reduced from 200
                burst_limit=1,          # Reduced from 2
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                max_retries=1,         # Reduced from 2
                base_delay=10.0,       # Increased from 5.0
                max_delay=120.0        # Increased from 60.0
            ),
            timeout=30,
            retry_exceptions=[aiohttp.ClientError, Exception],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.clients["moneycontrol"] = APIClient(moneycontrol_config)
        
        # SEC Edgar client
        sec_config = APIConfig(
            name="sec_edgar",
            base_url="https://www.sec.gov",
            rate_limit=RateLimitConfig(
                requests_per_minute=10,  # SEC limit
                requests_per_hour=1000,
                burst_limit=10,
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                max_retries=3,
                base_delay=1.0,
                max_delay=30.0
            ),
            timeout=30,
            retry_exceptions=[aiohttp.ClientError, Exception],
            user_agent="EquiSense AI research@equisense.ai"
        )
        self.clients["sec_edgar"] = APIClient(sec_config)
        
        # BSE API client
        bse_config = APIConfig(
            name="bse_api",
            base_url="https://api.bseindia.com",
            rate_limit=RateLimitConfig(
                requests_per_minute=20,
                requests_per_hour=500,
                burst_limit=5,
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                max_retries=3,
                base_delay=2.0,
                max_delay=30.0
            ),
            timeout=30,
            retry_exceptions=[aiohttp.ClientError, Exception],
            user_agent="EquiSense AI Research Bot (research@equisense.ai)"
        )
        self.clients["bse_api"] = APIClient(bse_config)
    
    def get_client(self, service: str) -> APIClient:
        """Get API client for specific service"""
        if service not in self.clients:
            raise ValueError(f"Unknown service: {service}")
        return self.clients[service]
    
    async def close_all(self):
        """Close all API clients"""
        for client in self.clients.values():
            await client.close()


# Global instance
_api_manager = APIClientManager()


def get_api_client(service: str) -> APIClient:
    """Get API client for specific service"""
    return _api_manager.get_client(service)


async def close_all_clients():
    """Close all API clients"""
    await _api_manager.close_all()


# Decorator for rate-limited functions
def rate_limited(service: str):
    """Decorator to add rate limiting to functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            client = get_api_client(service)
            return await client.circuit_breaker.call(
                client.retry_manager.retry,
                func,
                *args,
                **kwargs
            )
        return wrapper
    return decorator


# Enhanced Yahoo Finance wrapper
class YahooFinanceClient:
    """Enhanced Yahoo Finance client with rate limiting"""
    
    def __init__(self):
        self.client = get_api_client("yahoo_finance")
        self.cache = {}  # Simple in-memory cache
        
    async def download(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """Download stock data with rate limiting and fallback for Indian stocks"""
        cache_key = f"{ticker}_{period}_{interval}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Simple rate limiting for yfinance calls
        await self.client.rate_limiter.acquire()
        try:
            # Use yfinance in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
            )
            
            # If we got data, cache and return it
            if not data.empty:
                self.cache[cache_key] = data
                return data
            
            # For Indian stocks (.NS), try alternative symbol formats
            if ticker.endswith('.NS'):
                logger.warning(f"No price data found for {ticker}, trying alternative formats")
                
                # Try without .NS suffix
                alt_ticker = ticker.replace('.NS', '')
                try:
                    data_alt = await loop.run_in_executor(
                        None,
                        lambda: yf.download(alt_ticker, period=period, interval=interval, progress=False, auto_adjust=True)
                    )
                    if not data_alt.empty:
                        logger.info(f"Found price data for {alt_ticker} (alternative format)")
                        self.cache[cache_key] = data_alt
                        return data_alt
                except Exception as e:
                    logger.debug(f"Alternative format {alt_ticker} also failed: {e}")
                
                # Try BSE format (.BO)
                bse_ticker = alt_ticker + '.BO'
                try:
                    data_bse = await loop.run_in_executor(
                        None,
                        lambda: yf.download(bse_ticker, period=period, interval=interval, progress=False, auto_adjust=True)
                    )
                    if not data_bse.empty:
                        logger.info(f"Found price data for {bse_ticker} (BSE format)")
                        self.cache[cache_key] = data_bse
                        return data_bse
                except Exception as e:
                    logger.debug(f"BSE format {bse_ticker} also failed: {e}")
            
            logger.warning(f"No data returned for {ticker} from any format")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Failed to download data for {ticker}: {e}")
            return pd.DataFrame()
        finally:
            self.client.rate_limiter.release()
    
    async def get_info(self, ticker: str) -> Dict[str, Any]:
        """Get stock info with rate limiting and fallback for Indian stocks"""
        # Simple rate limiting for yfinance calls
        await self.client.rate_limiter.acquire()
        try:
            loop = asyncio.get_event_loop()
            
            # Try the original ticker first
            stock = await loop.run_in_executor(None, lambda: yf.Ticker(ticker))
            info = await loop.run_in_executor(None, lambda: stock.info)
            
            # If we got data, return it
            if info and len(info) > 5:  # Basic validation - should have more than 5 fields
                return info
            
            # For Indian stocks (.NS), try alternative symbol formats
            if ticker.endswith('.NS'):
                logger.warning(f"No data found for {ticker}, trying alternative formats")
                
                # Try without .NS suffix
                alt_ticker = ticker.replace('.NS', '')
                try:
                    stock_alt = await loop.run_in_executor(None, lambda: yf.Ticker(alt_ticker))
                    info_alt = await loop.run_in_executor(None, lambda: stock_alt.info)
                    if info_alt and len(info_alt) > 5:
                        logger.info(f"Found data for {alt_ticker} (alternative format)")
                        return info_alt
                except Exception as e:
                    logger.debug(f"Alternative format {alt_ticker} also failed: {e}")
                
                # Try BSE format (.BO)
                bse_ticker = alt_ticker + '.BO'
                try:
                    stock_bse = await loop.run_in_executor(None, lambda: yf.Ticker(bse_ticker))
                    info_bse = await loop.run_in_executor(None, lambda: stock_bse.info)
                    if info_bse and len(info_bse) > 5:
                        logger.info(f"Found data for {bse_ticker} (BSE format)")
                        return info_bse
                except Exception as e:
                    logger.debug(f"BSE format {bse_ticker} also failed: {e}")
            
            # Return whatever we got (even if empty)
            return info or {}
            
        except Exception as e:
            logger.error(f"Failed to fetch info for {ticker}: {e}")
            return {}
        finally:
            self.client.rate_limiter.release()


# Global Yahoo Finance client
_yahoo_client = YahooFinanceClient()


def get_yahoo_client() -> YahooFinanceClient:
    """Get Yahoo Finance client"""
    return _yahoo_client


# Enhanced bulk processing with concurrency control
class BulkProcessor:
    """Process multiple requests with controlled concurrency"""
    
    def __init__(self, max_concurrent: int = 5, delay_between_batches: float = 1.0):
        self.max_concurrent = max_concurrent
        self.delay_between_batches = delay_between_batches
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(self, items: List[Any], processor: Callable) -> List[Any]:
        """Process items in controlled batches"""
        results = []
        
        for i in range(0, len(items), self.max_concurrent):
            batch = items[i:i + self.max_concurrent]
            
            async def process_item(item):
                async with self.semaphore:
                    return await processor(item)
            
            batch_results = await asyncio.gather(
                *[process_item(item) for item in batch],
                return_exceptions=True
            )
            
            results.extend(batch_results)
            
            # Delay between batches to respect rate limits
            if i + self.max_concurrent < len(items):
                await asyncio.sleep(self.delay_between_batches)
        
        return results


# Global bulk processor
_bulk_processor = BulkProcessor(max_concurrent=3, delay_between_batches=2.0)


def get_bulk_processor() -> BulkProcessor:
    """Get bulk processor instance"""
    return _bulk_processor
