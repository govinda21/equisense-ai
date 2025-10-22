"""
Optimized Bulk Stock Analysis System

This module provides high-performance bulk analysis capabilities for processing
multiple stocks efficiently with intelligent batching, caching, and parallel processing.

Features:
- Intelligent batching based on market type
- Parallel processing with controlled concurrency
- Shared data caching across stocks
- Performance monitoring and metrics
- Memory-efficient processing
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import json

from app.config import AppSettings
from app.graph.workflow import build_research_graph
from app.utils.async_utils import AsyncProcessor

logger = logging.getLogger(__name__)


@dataclass
class BulkAnalysisConfig:
    """Configuration for bulk analysis"""
    max_concurrent_stocks: int = 5
    batch_size: int = 10
    timeout_per_stock: float = 30.0
    cache_shared_data: bool = True
    enable_performance_monitoring: bool = True


@dataclass
class BulkAnalysisResult:
    """Result of bulk analysis"""
    successful_analyses: List[Dict[str, Any]]
    failed_analyses: List[Tuple[str, str]]  # (ticker, error)
    performance_metrics: Dict[str, Any]
    total_time: float
    success_rate: float


class BulkStockAnalyzer:
    """
    High-performance bulk stock analyzer with intelligent optimization
    """
    
    def __init__(self, config: Optional[BulkAnalysisConfig] = None):
        self.config = config or BulkAnalysisConfig()
        self.settings = AppSettings()
        self.workflow = build_research_graph(self.settings)
        self.shared_cache = {}  # Cache for shared data across stocks
        self.performance_metrics = {
            "total_analyses": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "average_time_per_stock": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
    
    async def analyze_bulk(
        self, 
        tickers: List[str], 
        market: str = "India"
    ) -> BulkAnalysisResult:
        """
        Analyze multiple stocks with optimized parallel processing
        
        Args:
            tickers: List of stock tickers to analyze
            market: Market type (India, US, etc.)
            
        Returns:
            BulkAnalysisResult with all analyses and performance metrics
        """
        start_time = time.time()
        logger.info(f"Starting bulk analysis for {len(tickers)} stocks")
        
        # Pre-process tickers and create batches
        batches = self._create_optimized_batches(tickers, market)
        
        # Process batches in parallel with controlled concurrency
        successful_analyses = []
        failed_analyses = []
        
        async with AsyncProcessor(max_workers=self.config.max_concurrent_stocks) as processor:
            batch_tasks = [
                self._process_batch(batch, market) 
                for batch in batches
            ]
            
            batch_results = await processor.gather_with_concurrency(
                *batch_tasks,
                return_exceptions=True,
                timeout=self.config.timeout_per_stock * len(batches)
            )
            
            # Process batch results
            for batch_result in batch_results:
                if isinstance(batch_result, Exception):
                    logger.error(f"Batch processing failed: {batch_result}")
                    continue
                
                batch_successful, batch_failed = batch_result
                successful_analyses.extend(batch_successful)
                failed_analyses.extend(batch_failed)
        
        # Calculate performance metrics
        total_time = time.time() - start_time
        success_rate = len(successful_analyses) / len(tickers) if tickers else 0.0
        
        self.performance_metrics.update({
            "total_analyses": len(tickers),
            "successful_analyses": len(successful_analyses),
            "failed_analyses": len(failed_analyses),
            "average_time_per_stock": total_time / len(tickers) if tickers else 0.0,
            "total_time": total_time
        })
        
        logger.info(f"Bulk analysis completed: {len(successful_analyses)}/{len(tickers)} successful "
                   f"in {total_time:.2f}s (avg: {self.performance_metrics['average_time_per_stock']:.2f}s/stock)")
        
        return BulkAnalysisResult(
            successful_analyses=successful_analyses,
            failed_analyses=failed_analyses,
            performance_metrics=self.performance_metrics,
            total_time=total_time,
            success_rate=success_rate
        )
    
    def _create_optimized_batches(self, tickers: List[str], market: str) -> List[List[str]]:
        """
        Create optimized batches based on market type and ticker characteristics
        """
        # Group by market type for better caching
        indian_tickers = [t for t in tickers if t.endswith(('.NS', '.BO'))]
        us_tickers = [t for t in tickers if not t.endswith(('.NS', '.BO'))]
        
        batches = []
        
        # Create batches for Indian stocks (smaller batches due to more complex data fetching)
        if indian_tickers:
            indian_batches = [
                indian_tickers[i:i + self.config.batch_size // 2]  # Smaller batches for Indian stocks
                for i in range(0, len(indian_tickers), self.config.batch_size // 2)
            ]
            batches.extend(indian_batches)
        
        # Create batches for US stocks (larger batches due to simpler data fetching)
        if us_tickers:
            us_batches = [
                us_tickers[i:i + self.config.batch_size]
                for i in range(0, len(us_tickers), self.config.batch_size)
            ]
            batches.extend(us_batches)
        
        logger.info(f"Created {len(batches)} optimized batches for {len(tickers)} tickers")
        return batches
    
    async def _process_batch(
        self, 
        batch_tickers: List[str], 
        market: str
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
        """
        Process a batch of tickers with shared data optimization
        """
        successful_analyses = []
        failed_analyses = []
        
        # Pre-fetch shared data for the batch (market data, sector data, etc.)
        if self.config.cache_shared_data:
            await self._prefetch_shared_data(batch_tickers, market)
        
        # Process each ticker in the batch
        for ticker in batch_tickers:
            try:
                start_time = time.time()
                
                # Use shared data if available
                analysis_result = await self._analyze_single_stock_optimized(ticker, market)
                
                analysis_time = time.time() - start_time
                logger.debug(f"Analyzed {ticker} in {analysis_time:.2f}s")
                
                successful_analyses.append(analysis_result)
                
            except Exception as e:
                logger.error(f"Failed to analyze {ticker}: {e}")
                failed_analyses.append((ticker, str(e)))
        
        return successful_analyses, failed_analyses
    
    async def _prefetch_shared_data(self, tickers: List[str], market: str):
        """
        Pre-fetch shared data that can be reused across multiple stocks
        """
        try:
            # Pre-fetch market-wide data (sector performance, macro indicators, etc.)
            if market == "India":
                # Pre-fetch Indian market data
                from app.tools.sector_rotation import SectorRotationAnalyzer
                sector_analyzer = SectorRotationAnalyzer()
                await sector_analyzer.analyze_sector_rotation(market)
                
                # Cache sector data for reuse
                self.shared_cache["sector_data"] = sector_analyzer.get_sector_performance()
            
            logger.debug(f"Prefetched shared data for {len(tickers)} tickers")
            
        except Exception as e:
            logger.warning(f"Failed to prefetch shared data: {e}")
    
    async def _analyze_single_stock_optimized(
        self, 
        ticker: str, 
        market: str
    ) -> Dict[str, Any]:
        """
        Analyze a single stock with optimizations for bulk processing
        """
        # Use timeout to prevent hanging
        analysis_result = await asyncio.wait_for(
            self.workflow.ainvoke({
                'tickers': [ticker],
                'market': market
            }),
            timeout=self.config.timeout_per_stock
        )
        
        # Extract the report for this ticker
        if 'final_output' in analysis_result and 'reports' in analysis_result['final_output']:
            reports = analysis_result['final_output']['reports']
            if reports:
                return reports[0]  # Single ticker analysis
        
        raise Exception(f"No analysis result found for {ticker}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self.performance_metrics.copy()
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self.performance_metrics = {
            "total_analyses": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "average_time_per_stock": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }


# Convenience functions for easy usage
async def analyze_stocks_bulk(
    tickers: List[str], 
    market: str = "India",
    config: Optional[BulkAnalysisConfig] = None
) -> BulkAnalysisResult:
    """
    Convenience function for bulk stock analysis
    
    Args:
        tickers: List of stock tickers
        market: Market type
        config: Optional configuration
        
    Returns:
        BulkAnalysisResult
    """
    analyzer = BulkStockAnalyzer(config)
    return await analyzer.analyze_bulk(tickers, market)


async def analyze_stocks_parallel(
    tickers: List[str], 
    market: str = "India",
    max_concurrent: int = 5
) -> List[Dict[str, Any]]:
    """
    Simple parallel analysis without batching (for smaller lists)
    
    Args:
        tickers: List of stock tickers
        market: Market type
        max_concurrent: Maximum concurrent analyses
        
    Returns:
        List of analysis results
    """
    config = BulkAnalysisConfig(
        max_concurrent_stocks=max_concurrent,
        batch_size=len(tickers),  # Process all in one batch
        timeout_per_stock=30.0
    )
    
    result = await analyze_stocks_bulk(tickers, market, config)
    return result.successful_analyses
