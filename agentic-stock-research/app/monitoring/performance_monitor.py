"""
Performance Monitoring and Metrics System

This module provides comprehensive performance monitoring for stock analysis
with real-time metrics, profiling, and optimization recommendations.
"""

import asyncio
import logging
import time
import psutil
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import json

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for analysis operations"""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System-level performance metrics"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_available: float
    disk_usage: float
    network_io: Dict[str, float]
    active_connections: int


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system
    """
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.system_metrics_history: deque = deque(maxlen=max_history)
        self.operation_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "avg_time": 0.0,
            "min_time": float('inf'),
            "max_time": 0.0,
            "success_rate": 0.0,
            "errors": 0
        })
        
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        
        logger.info("PerformanceMonitor initialized")
    
    def start_monitoring(self, interval: float = 5.0):
        """Start continuous system monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_system_metrics,
            args=(interval,),
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"Started system monitoring with {interval}s interval")
    
    def stop_monitoring(self):
        """Stop continuous system monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
        logger.info("Stopped system monitoring")
    
    def _monitor_system_metrics(self, interval: float):
        """Monitor system metrics in background thread"""
        while self.monitoring_active:
            try:
                metrics = self._collect_system_metrics()
                self.system_metrics_history.append(metrics)
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                time.sleep(interval)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        
        return SystemMetrics(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_available=memory.available / (1024**3),  # GB
            disk_usage=disk.percent,
            network_io={
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            },
            active_connections=len(psutil.net_connections())
        )
    
    @asynccontextmanager
    async def monitor_operation(self, operation_name: str, **metadata):
        """Context manager for monitoring async operations"""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / (1024**2)  # MB
        
        metrics = PerformanceMetrics(
            operation_name=operation_name,
            start_time=start_time,
            metadata=metadata
        )
        
        try:
            yield metrics
            metrics.success = True
        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            raise
        finally:
            metrics.end_time = time.time()
            metrics.duration = metrics.end_time - metrics.start_time
            metrics.memory_usage = psutil.Process().memory_info().rss / (1024**2) - start_memory
            metrics.cpu_usage = psutil.cpu_percent()
            
            # Store metrics
            self.metrics_history.append(metrics)
            self._update_operation_stats(metrics)
            
            logger.debug(f"Operation {operation_name} completed in {metrics.duration:.3f}s "
                        f"(memory: {metrics.memory_usage:.1f}MB)")
    
    def _update_operation_stats(self, metrics: PerformanceMetrics):
        """Update operation statistics"""
        stats = self.operation_stats[metrics.operation_name]
        stats["count"] += 1
        stats["total_time"] += metrics.duration
        
        if metrics.duration < stats["min_time"]:
            stats["min_time"] = metrics.duration
        if metrics.duration > stats["max_time"]:
            stats["max_time"] = metrics.duration
        
        stats["avg_time"] = stats["total_time"] / stats["count"]
        
        if not metrics.success:
            stats["errors"] += 1
        
        stats["success_rate"] = (stats["count"] - stats["errors"]) / stats["count"]
    
    def get_operation_stats(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for specific operation or all operations"""
        if operation_name:
            return self.operation_stats.get(operation_name, {})
        
        return dict(self.operation_stats)
    
    def get_system_metrics_summary(self) -> Dict[str, Any]:
        """Get system metrics summary"""
        if not self.system_metrics_history:
            return {}
        
        recent_metrics = list(self.system_metrics_history)[-10:]  # Last 10 measurements
        
        return {
            "cpu_percent": {
                "current": recent_metrics[-1].cpu_percent,
                "average": sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
                "max": max(m.cpu_percent for m in recent_metrics)
            },
            "memory_percent": {
                "current": recent_metrics[-1].memory_percent,
                "average": sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
                "max": max(m.memory_percent for m in recent_metrics)
            },
            "memory_available_gb": {
                "current": recent_metrics[-1].memory_available,
                "average": sum(m.memory_available for m in recent_metrics) / len(recent_metrics),
                "min": min(m.memory_available for m in recent_metrics)
            },
            "active_connections": recent_metrics[-1].active_connections
        }
    
    def get_detailed_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary with granular metrics"""
        return {
            "overview": {
                "total_operations": len(self.metrics_history),
                "error_rate": self._calculate_error_rate(),
                "average_operation_time": self._calculate_average_operation_time(),
                "system_health": self._calculate_system_health()
            },
            "operation_breakdown": self.get_operation_stats(),
            "system_metrics": self.get_system_metrics_summary(),
            "performance_trends": self._calculate_performance_trends(),
            "bottlenecks": self._identify_bottlenecks(),
            "recommendations": self._generate_recommendations(),
            "slowest_operations": self._get_slowest_operations(),
            "most_frequent_operations": self._get_most_frequent_operations(),
            "memory_usage": self._analyze_memory_usage(),
            "cpu_usage": self._analyze_cpu_usage()
        }
    
    def _get_slowest_operations(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get slowest operations by average time"""
        operations = []
        for op_name, stats in self.operation_stats.items():
            if stats["count"] > 0:
                operations.append({
                    "operation": op_name,
                    "avg_time": stats["avg_time"],
                    "max_time": stats["max_time"],
                    "count": stats["count"]
                })
        
        return sorted(operations, key=lambda x: x["avg_time"], reverse=True)[:limit]
    
    def _get_most_frequent_operations(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most frequently called operations"""
        operations = []
        for op_name, stats in self.operation_stats.items():
            operations.append({
                "operation": op_name,
                "count": stats["count"],
                "avg_time": stats["avg_time"],
                "total_time": stats["total_time"]
            })
        
        return sorted(operations, key=lambda x: x["count"], reverse=True)[:limit]
    
    def _calculate_average_operation_time(self) -> float:
        """Calculate average operation time across all operations"""
        if not self.metrics_history:
            return 0.0
        
        total_time = sum(m.duration for m in self.metrics_history if m.duration)
        return total_time / len(self.metrics_history)
    
    def _calculate_system_health(self) -> str:
        """Calculate overall system health score"""
        if not self.system_metrics_history:
            return "unknown"
        
        recent_metrics = list(self.system_metrics_history)[-5:]  # Last 5 measurements
        
        # Calculate health based on CPU, memory, and error rate
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        error_rate = self._calculate_error_rate()
        
        # Health scoring (0-100)
        cpu_score = max(0, 100 - avg_cpu)
        memory_score = max(0, 100 - avg_memory)
        error_score = max(0, 100 - (error_rate * 100))
        
        overall_score = (cpu_score + memory_score + error_score) / 3
        
        if overall_score >= 80:
            return "excellent"
        elif overall_score >= 60:
            return "good"
        elif overall_score >= 40:
            return "fair"
        else:
            return "poor"
    
    def _calculate_performance_trends(self) -> Dict[str, Any]:
        """Calculate performance trends over time"""
        if len(self.metrics_history) < 10:
            return {"trend": "insufficient_data", "change": 0.0}
        
        # Split metrics into two halves
        mid_point = len(self.metrics_history) // 2
        first_half = self.metrics_history[:mid_point]
        second_half = self.metrics_history[mid_point:]
        
        # Calculate average times
        first_avg = sum(m.duration for m in first_half if m.duration) / len(first_half)
        second_avg = sum(m.duration for m in second_half if m.duration) / len(second_half)
        
        # Calculate trend
        change = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
        
        if change > 10:
            trend = "degrading"
        elif change < -10:
            trend = "improving"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "change_percent": change,
            "first_half_avg": first_avg,
            "second_half_avg": second_avg
        }
    
    def _identify_bottlenecks(self) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks"""
        bottlenecks = []
        
        # Check for slow operations
        for op_name, stats in self.operation_stats.items():
            if stats["avg_time"] > 5.0:  # Operations taking more than 5 seconds
                bottlenecks.append({
                    "type": "slow_operation",
                    "operation": op_name,
                    "avg_time": stats["avg_time"],
                    "count": stats["count"],
                    "severity": "high" if stats["avg_time"] > 10.0 else "medium"
                })
        
        # Check for high error rates
        for op_name, stats in self.operation_stats.items():
            if stats["count"] > 0:
                error_rate = stats["errors"] / stats["count"]
                if error_rate > 0.1:  # More than 10% error rate
                    bottlenecks.append({
                        "type": "high_error_rate",
                        "operation": op_name,
                        "error_rate": error_rate,
                        "errors": stats["errors"],
                        "severity": "high" if error_rate > 0.3 else "medium"
                    })
        
        # Check system resources
        if self.system_metrics_history:
            recent_metrics = list(self.system_metrics_history)[-5:]
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            
            if avg_cpu > 80:
                bottlenecks.append({
                    "type": "high_cpu_usage",
                    "cpu_percent": avg_cpu,
                    "severity": "high" if avg_cpu > 90 else "medium"
                })
            
            if avg_memory > 80:
                bottlenecks.append({
                    "type": "high_memory_usage",
                    "memory_percent": avg_memory,
                    "severity": "high" if avg_memory > 90 else "medium"
                })
        
        return sorted(bottlenecks, key=lambda x: x.get("severity", "low"), reverse=True)
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance improvement recommendations"""
        recommendations = []
        
        # Analyze bottlenecks
        bottlenecks = self._identify_bottlenecks()
        
        for bottleneck in bottlenecks:
            if bottleneck["type"] == "slow_operation":
                recommendations.append(
                    f"Optimize {bottleneck['operation']} - currently taking {bottleneck['avg_time']:.2f}s on average"
                )
            elif bottleneck["type"] == "high_error_rate":
                recommendations.append(
                    f"Investigate errors in {bottleneck['operation']} - {bottleneck['error_rate']:.1%} error rate"
                )
            elif bottleneck["type"] == "high_cpu_usage":
                recommendations.append(
                    f"Reduce CPU usage - currently at {bottleneck['cpu_percent']:.1f}%"
                )
            elif bottleneck["type"] == "high_memory_usage":
                recommendations.append(
                    f"Optimize memory usage - currently at {bottleneck['memory_percent']:.1f}%"
                )
        
        # General recommendations based on trends
        trends = self._calculate_performance_trends()
        if trends["trend"] == "degrading":
            recommendations.append("Performance is degrading - consider optimization")
        elif trends["trend"] == "improving":
            recommendations.append("Performance is improving - continue current optimizations")
        
        # Cache recommendations
        if len(self.metrics_history) > 100:
            recommendations.append("Consider implementing more aggressive caching")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def _analyze_memory_usage(self) -> Dict[str, Any]:
        """Analyze memory usage patterns"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        memory_metrics = [m for m in self.metrics_history if m.memory_usage is not None]
        
        if not memory_metrics:
            return {"status": "no_memory_data"}
        
        memory_values = [m.memory_usage for m in memory_metrics]
        
        return {
            "status": "analyzed",
            "average_memory_per_operation": sum(memory_values) / len(memory_values),
            "max_memory_per_operation": max(memory_values),
            "min_memory_per_operation": min(memory_values),
            "operations_with_memory_data": len(memory_metrics),
            "memory_leak_risk": "high" if max(memory_values) > 100 else "low"
        }
    
    def _analyze_cpu_usage(self) -> Dict[str, Any]:
        """Analyze CPU usage patterns"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        cpu_metrics = [m for m in self.metrics_history if m.cpu_usage is not None]
        
        if not cpu_metrics:
            return {"status": "no_cpu_data"}
        
        cpu_values = [m.cpu_usage for m in cpu_metrics]
        
        return {
            "status": "analyzed",
            "average_cpu_per_operation": sum(cpu_values) / len(cpu_values),
            "max_cpu_per_operation": max(cpu_values),
            "min_cpu_per_operation": min(cpu_values),
            "operations_with_cpu_data": len(cpu_metrics),
            "cpu_intensive_operations": len([c for c in cpu_values if c > 50])
        }
    
    def _calculate_error_rate(self) -> float:
        """Calculate overall error rate"""
        total_operations = sum(stats["count"] for stats in self.operation_stats.values())
        total_errors = sum(stats["errors"] for stats in self.operation_stats.values())
        
        return total_errors / total_operations if total_operations > 0 else 0.0
    
    def export_metrics(self, filepath: str):
        """Export metrics to JSON file"""
        data = {
            "timestamp": time.time(),
            "summary": self.get_performance_summary(),
            "recent_metrics": [
                {
                    "operation_name": m.operation_name,
                    "duration": m.duration,
                    "success": m.success,
                    "memory_usage": m.memory_usage,
                    "metadata": m.metadata
                }
                for m in list(self.metrics_history)[-100:]  # Last 100 operations
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported metrics to {filepath}")


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance"""
    global _performance_monitor
    
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
        _performance_monitor.start_monitoring()
    
    return _performance_monitor


# Decorator for easy performance monitoring
def monitor_performance(operation_name: str, **metadata):
    """Decorator for monitoring function performance"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            async with monitor.monitor_operation(operation_name, **metadata):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                metrics = PerformanceMetrics(
                    operation_name=operation_name,
                    start_time=start_time,
                    end_time=time.time(),
                    duration=duration,
                    metadata=metadata
                )
                monitor.metrics_history.append(metrics)
                monitor._update_operation_stats(metrics)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Convenience functions
def get_performance_summary() -> Dict[str, Any]:
    """Get current performance summary"""
    monitor = get_performance_monitor()
    return monitor.get_performance_summary()


def export_performance_metrics(filepath: str):
    """Export performance metrics to file"""
    monitor = get_performance_monitor()
    monitor.export_metrics(filepath)
