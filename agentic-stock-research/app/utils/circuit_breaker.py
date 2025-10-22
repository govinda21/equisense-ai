"""
Circuit Breaker Pattern Implementation for Resilient Service Calls

This module provides circuit breaker functionality to prevent cascading failures
and improve system resilience when external services are down or slow.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Callable, Any, TypeVar, Awaitable
from dataclasses import dataclass
from enum import Enum
import functools

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5          # Number of failures before opening
    recovery_timeout: float = 60.0      # Seconds before trying half-open
    success_threshold: int = 3          # Successes needed to close from half-open
    timeout: float = 30.0               # Request timeout
    expected_exception: type = Exception  # Exception type to catch


class CircuitBreaker:
    """
    Circuit breaker implementation for resilient service calls
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.last_success_time = 0.0
        
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "circuit_open_count": 0,
            "circuit_half_open_count": 0,
            "circuit_closed_count": 0
        }
        
        logger.info(f"CircuitBreaker '{name}' initialized")
    
    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenException: When circuit is open
            TimeoutError: When request times out
            Exception: Original function exception
        """
        self.stats["total_calls"] += 1
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.stats["circuit_half_open_count"] += 1
                logger.info(f"CircuitBreaker '{self.name}' moved to HALF_OPEN")
            else:
                self.stats["circuit_open_count"] += 1
                raise CircuitBreakerOpenException(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            # Execute function with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            # Record success
            self._record_success()
            return result
            
        except asyncio.TimeoutError:
            self._record_failure()
            logger.warning(f"CircuitBreaker '{self.name}': Timeout after {self.config.timeout}s")
            raise
            
        except self.config.expected_exception as e:
            self._record_failure()
            logger.warning(f"CircuitBreaker '{self.name}': Service error - {e}")
            raise
            
        except Exception as e:
            # Unexpected exception - don't count as circuit breaker failure
            logger.error(f"CircuitBreaker '{self.name}': Unexpected error - {e}")
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset"""
        return time.time() - self.last_failure_time >= self.config.recovery_timeout
    
    def _record_success(self):
        """Record successful call"""
        self.last_success_time = time.time()
        self.success_count += 1
        self.stats["successful_calls"] += 1
        
        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.stats["circuit_closed_count"] += 1
                logger.info(f"CircuitBreaker '{self.name}' moved to CLOSED")
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _record_failure(self):
        """Record failed call"""
        self.last_failure_time = time.time()
        self.failure_count += 1
        self.stats["failed_calls"] += 1
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.stats["circuit_open_count"] += 1
                logger.warning(f"CircuitBreaker '{self.name}' moved to OPEN after {self.failure_count} failures")
        elif self.state == CircuitState.HALF_OPEN:
            # Move back to open on failure
            self.state = CircuitState.OPEN
            self.stats["circuit_open_count"] += 1
            logger.warning(f"CircuitBreaker '{self.name}' moved back to OPEN from HALF_OPEN")
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self.state
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        success_rate = (self.stats["successful_calls"] / self.stats["total_calls"] * 100) if self.stats["total_calls"] > 0 else 0
        
        return {
            **self.stats,
            "current_state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "success_rate": f"{success_rate:.1f}%",
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            }
        }
    
    def reset(self):
        """Manually reset circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"CircuitBreaker '{self.name}' manually reset")


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_config = CircuitBreakerConfig()
    
    def get_circuit_breaker(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config or self.default_config)
        
        return self.circuit_breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {
            name: cb.get_stats() 
            for name, cb in self.circuit_breakers.items()
        }
    
    def reset_all(self):
        """Reset all circuit breakers"""
        for cb in self.circuit_breakers.values():
            cb.reset()
        logger.info("All circuit breakers reset")


# Global circuit breaker manager
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager"""
    global _circuit_breaker_manager
    
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    
    return _circuit_breaker_manager


def circuit_breaker(
    name: str, 
    config: Optional[CircuitBreakerConfig] = None
):
    """
    Decorator for circuit breaker protection
    
    Usage:
        @circuit_breaker("api_service")
        async def call_api():
            # API call code
            pass
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            manager = get_circuit_breaker_manager()
            cb = manager.get_circuit_breaker(name, config)
            return await cb.call(func, *args, **kwargs)
        
        return wrapper
    
    return decorator


# Convenience functions
async def call_with_circuit_breaker(
    name: str, 
    func: Callable[..., Awaitable[T]], 
    *args, 
    config: Optional[CircuitBreakerConfig] = None,
    **kwargs
) -> T:
    """Call function with circuit breaker protection"""
    manager = get_circuit_breaker_manager()
    cb = manager.get_circuit_breaker(name, config)
    return await cb.call(func, *args, **kwargs)


def get_circuit_breaker_stats(name: str) -> Optional[Dict[str, Any]]:
    """Get statistics for specific circuit breaker"""
    manager = get_circuit_breaker_manager()
    if name in manager.circuit_breakers:
        return manager.circuit_breakers[name].get_stats()
    return None


def get_all_circuit_breaker_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all circuit breakers"""
    manager = get_circuit_breaker_manager()
    return manager.get_all_stats()


def reset_circuit_breaker(name: str):
    """Reset specific circuit breaker"""
    manager = get_circuit_breaker_manager()
    if name in manager.circuit_breakers:
        manager.circuit_breakers[name].reset()


def reset_all_circuit_breakers():
    """Reset all circuit breakers"""
    manager = get_circuit_breaker_manager()
    manager.reset_all()
