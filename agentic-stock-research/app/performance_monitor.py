"""
Performance Monitoring and Metrics Collection

Tracks:
- API response times
- Database query performance
- Cache hit/miss rates
- Memory and CPU usage
- Error rates and types
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available - system metrics will be limited")

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics tracked"""
    RESPONSE_TIME = "response_time"
    DATABASE_QUERY = "database_query"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    API_CALL = "api_call"
    ERROR = "error"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"


@dataclass
class Metric:
    """Individual metric data point"""
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceStats:
    """Aggregated performance statistics"""
    metric_type: MetricType
    count: int
    total: float
    avg: float
    min: float
    max: float
    p50: float
    p95: float
    p99: float
    period_start: datetime
    period_end: datetime


def _pct(values: List[float], percentile: float) -> float:
    """Return the value at the given percentile from a sorted list (0.0–1.0 scale)."""
    idx = int(len(values) * percentile)
    return values[idx] if idx < len(values) else 0


class PerformanceMonitor:
    """
    Performance monitoring and metrics collection

    Thread-safe metric collection with automatic aggregation and reporting
    """

    def __init__(
        self,
        retention_period: int = 3600,  # 1 hour
        max_metrics: int = 10000,
        aggregation_interval: int = 60,  # 1 minute
    ):
        """
        Initialize performance monitor

        Args:
            retention_period: How long to retain metrics (seconds)
            max_metrics: Maximum number of metrics to store
            aggregation_interval: How often to aggregate metrics (seconds)
        """
        self.retention_period = retention_period
        self.max_metrics = max_metrics
        self.aggregation_interval = aggregation_interval

        # Metric storage (thread-safe via asyncio)
        self.metrics: Dict[MetricType, deque] = defaultdict(lambda: deque(maxlen=max_metrics))

        # Aggregated stats
        self.aggregated_stats: Dict[MetricType, PerformanceStats] = {}

        # Error tracking
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.last_aggregation = datetime.now()

        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._aggregation_task: Optional[asyncio.Task] = None

        logger.info(f"Performance monitor initialized with {retention_period}s retention")

    async def start(self):
        """Start background monitoring tasks"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._aggregation_task = asyncio.create_task(self._aggregation_loop())
        logger.info("Performance monitoring started")

    async def stop(self):
        """Stop background monitoring tasks"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._aggregation_task:
            self._aggregation_task.cancel()
        logger.info("Performance monitoring stopped")

    def record(
        self,
        metric_type: MetricType,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ):
        """
        Record a metric

        Args:
            metric_type: Type of metric
            value: Metric value
            tags: Optional tags for filtering/grouping
        """
        self.metrics[metric_type].append(Metric(metric_type=metric_type, value=value, tags=tags or {}))

    def record_response_time(self, endpoint: str, duration: float):
        """Record API response time"""
        self.record(MetricType.RESPONSE_TIME, duration, tags={"endpoint": endpoint})

    def record_database_query(self, query_type: str, duration: float):
        """Record database query time"""
        self.record(MetricType.DATABASE_QUERY, duration, tags={"query_type": query_type})

    def record_cache_hit(self, cache_key: str):
        """Record cache hit"""
        self.record(MetricType.CACHE_HIT, 1.0, tags={"cache_key": cache_key})

    def record_cache_miss(self, cache_key: str):
        """Record cache miss"""
        self.record(MetricType.CACHE_MISS, 1.0, tags={"cache_key": cache_key})

    def record_api_call(self, api_name: str, duration: float):
        """Record external API call"""
        self.record(MetricType.API_CALL, duration, tags={"api_name": api_name})

    def record_error(self, error_type: str, error_message: str):
        """Record an error"""
        self.error_counts[error_type] += 1
        self.record(MetricType.ERROR, 1.0, tags={"error_type": error_type, "error_message": error_message[:100]})

    async def _cleanup_loop(self):
        """Background task to clean up old metrics"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                # Remove metrics older than retention period
                cutoff_time = datetime.now() - timedelta(seconds=self.retention_period)
                for metric_list in self.metrics.values():
                    while metric_list and metric_list[0].timestamp < cutoff_time:
                        metric_list.popleft()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _aggregation_loop(self):
        """Background task to aggregate metrics"""
        while True:
            try:
                await asyncio.sleep(self.aggregation_interval)
                await self._aggregate_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")

    async def _aggregate_metrics(self):
        """Aggregate metrics for current period"""
        now = datetime.now()

        for metric_type, metric_list in self.metrics.items():
            if not metric_list:
                continue

            # Convert to list for aggregation
            values = sorted(m.value for m in metric_list)
            count = len(values)
            total = sum(values)

            self.aggregated_stats[metric_type] = PerformanceStats(
                metric_type=metric_type,
                count=count,
                total=total,
                avg=total / count if count > 0 else 0,
                min=values[0],
                max=values[-1],
                p50=_pct(values, 0.50),
                p95=_pct(values, 0.95),
                p99=_pct(values, 0.99),
                period_start=self.last_aggregation,
                period_end=now,
            )

        self.last_aggregation = now

        # Log summary
        logger.info(
            f"Performance metrics aggregated: "
            f"{len(self.aggregated_stats)} metric types, "
            f"{sum(s.count for s in self.aggregated_stats.values())} total measurements"
        )

    def get_stats(self, metric_type: Optional[MetricType] = None) -> Dict[str, Any]:
        """Get aggregated statistics"""
        if metric_type:
            stats = self.aggregated_stats.get(metric_type)
            if stats:
                return self._stats_to_dict(stats)
            return {}

        # Return all stats
        return {
            mt.value: self._stats_to_dict(stats)
            for mt, stats in self.aggregated_stats.items()
        }

    def _stats_to_dict(self, stats: PerformanceStats) -> Dict[str, Any]:
        """Convert stats to dictionary"""
        return {
            "count": stats.count,
            "total": stats.total,
            "avg": round(stats.avg, 3),
            "min": round(stats.min, 3),
            "max": round(stats.max, 3),
            "p50": round(stats.p50, 3),
            "p95": round(stats.p95, 3),
            "p99": round(stats.p99, 3),
            "period_start": stats.period_start.isoformat(),
            "period_end": stats.period_end.isoformat(),
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache hit/miss statistics"""
        hits = self.aggregated_stats.get(MetricType.CACHE_HIT)
        misses = self.aggregated_stats.get(MetricType.CACHE_MISS)

        hit_count = hits.count if hits else 0
        miss_count = misses.count if misses else 0
        total = hit_count + miss_count

        hit_rate = (hit_count / total * 100) if total > 0 else 0

        return {
            "hits": hit_count,
            "misses": miss_count,
            "total": total,
            "hit_rate": round(hit_rate, 2),
        }

    def get_error_stats(self) -> Dict[str, int]:
        """Get error counts by type"""
        return dict(self.error_counts)

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system resource usage"""
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}

        try:
            process = psutil.Process()

            # Memory usage
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # CPU usage
            cpu_percent = process.cpu_percent(interval=0.1)

            # System-wide metrics
            sys_cpu = psutil.cpu_percent(interval=0.1)
            sys_memory = psutil.virtual_memory()

            return {
                "process": {
                    "memory_mb": round(memory_info.rss / 1024 / 1024, 2),
                    "memory_percent": round(memory_percent, 2),
                    "cpu_percent": round(cpu_percent, 2),
                },
                "system": {
                    "cpu_percent": round(sys_cpu, 2),
                    "memory_available_mb": round(sys_memory.available / 1024 / 1024, 2),
                    "memory_percent": round(sys_memory.percent, 2),
                },
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {"error": str(e)}

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        response_time_stats = self.aggregated_stats.get(MetricType.RESPONSE_TIME)
        error_stats = self.aggregated_stats.get(MetricType.ERROR)

        # Determine health based on metrics
        health_score = 100.0
        issues = []

        # Check response times
        if response_time_stats:
            if response_time_stats.p95 > 5000:  # 5 seconds
                health_score -= 30
                issues.append("High response times (P95 > 5s)")
            elif response_time_stats.p95 > 2000:  # 2 seconds
                health_score -= 15
                issues.append("Elevated response times (P95 > 2s)")

        # Check error rate
        if error_stats and response_time_stats:
            error_rate = error_stats.count / max(response_time_stats.count, 1)
            if error_rate > 0.05:  # 5% error rate
                health_score -= 40
                issues.append(f"High error rate ({error_rate:.1%})")
            elif error_rate > 0.01:  # 1% error rate
                health_score -= 20
                issues.append(f"Elevated error rate ({error_rate:.1%})")

        # Check system resources
        system_metrics = self.get_system_metrics()
        if "process" in system_metrics:
            if system_metrics["process"]["memory_percent"] > 80:
                health_score -= 20
                issues.append("High memory usage")
            if system_metrics["process"]["cpu_percent"] > 80:
                health_score -= 15
                issues.append("High CPU usage")

        # Determine status
        if health_score >= 90:
            status = "healthy"
        elif health_score >= 70:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "health_score": max(0, round(health_score, 1)),
            "issues": issues,
            "timestamp": datetime.now().isoformat(),
        }


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


async def start_performance_monitoring():
    """Start global performance monitoring"""
    monitor = get_performance_monitor()
    await monitor.start()


async def stop_performance_monitoring():
    """Stop global performance monitoring"""
    monitor = get_performance_monitor()
    await monitor.stop()
