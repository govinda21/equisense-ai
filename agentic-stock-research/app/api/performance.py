"""
Performance monitoring and optimization API endpoints
"""

import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.optimization.performance import get_performance_optimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/performance", tags=["performance"])


@router.get("/health")
async def health_check():
    """Health check for performance system"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "performance_monitoring": "active",
            "cache_optimization": "active",
            "memory_optimization": "active",
            "async_optimization": "active"
        }
    }


@router.get("/metrics")
async def get_performance_metrics():
    """Get current performance metrics"""
    try:
        optimizer = get_performance_optimizer()
        report = optimizer.get_performance_report()
        
        return {
            "status": "success",
            "data": report
        }
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize")
async def run_performance_optimization(background_tasks: BackgroundTasks):
    """Run performance optimization routines"""
    try:
        optimizer = get_performance_optimizer()
        
        # Run optimization in background
        background_tasks.add_task(optimizer.optimize_performance)
        
        return {
            "status": "success",
            "message": "Performance optimization started in background"
        }
        
    except Exception as e:
        logger.error(f"Error running performance optimization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache performance statistics"""
    try:
        optimizer = get_performance_optimizer()
        
        return {
            "status": "success",
            "data": {
                "hit_rate": optimizer.cache_optimizer.get_hit_rate(),
                "stats": optimizer.cache_optimizer.cache_stats
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/status")
async def get_memory_status():
    """Get current memory usage status"""
    try:
        optimizer = get_performance_optimizer()
        memory_status = optimizer.memory_optimizer.check_memory_usage()
        
        return {
            "status": "success",
            "data": memory_status
        }
        
    except Exception as e:
        logger.error(f"Error getting memory status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/cleanup")
async def cleanup_memory():
    """Perform memory cleanup"""
    try:
        optimizer = get_performance_optimizer()
        memory_usage = optimizer.memory_optimizer.cleanup_memory()
        
        return {
            "status": "success",
            "message": "Memory cleanup completed",
            "data": memory_usage
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/stats")
async def get_database_stats():
    """Get database performance statistics"""
    try:
        optimizer = get_performance_optimizer()
        
        return {
            "status": "success",
            "data": {
                "average_query_time": optimizer.db_optimizer.get_average_query_time(),
                "slow_query_rate": optimizer.db_optimizer.get_slow_query_rate(),
                "stats": optimizer.db_optimizer.query_stats
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
