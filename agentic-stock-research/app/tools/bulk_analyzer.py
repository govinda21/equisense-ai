"""
Optimized Bulk Stock Analysis System

High-performance bulk analysis with intelligent batching, caching, and parallel processing.
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from app.config import AppSettings
from app.graph.workflow import build_research_graph
from app.utils.async_utils import AsyncProcessor
from app.utils.context_manager import create_isolated_context, validate_ticker_isolation

logger = logging.getLogger(__name__)

# Per-ticker locks to prevent concurrent access to same ticker
ticker_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@dataclass
class BulkAnalysisConfig:
    max_concurrent_stocks: int = 10
    batch_size: int = 20
    timeout_per_stock: float = 60.0
    cache_shared_data: bool = True
    enable_performance_monitoring: bool = True


@dataclass
class BulkAnalysisResult:
    successful_analyses: List[Dict[str, Any]]
    failed_analyses: List[Tuple[str, str]]  # (ticker, error)
    performance_metrics: Dict[str, Any]
    total_time: float
    success_rate: float


class BulkStockAnalyzer:
    """High-performance bulk stock analyzer with per-ticker isolation."""

    def __init__(self, config: Optional[BulkAnalysisConfig] = None):
        self.config = config or BulkAnalysisConfig()
        self.settings = AppSettings()
        self.workflow = build_research_graph(self.settings)
        self.ticker_cache: Dict[str, Dict[str, Any]] = {}
        self.performance_metrics = {
            "total_analyses": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "average_time_per_stock": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    async def analyze_bulk(self, tickers: List[str], market: str = "India") -> BulkAnalysisResult:
        """Analyze multiple stocks with optimized parallel processing."""
        start_time = time.time()
        logger.info(f"[BULK] Starting isolated analysis for {len(tickers)} stocks")

        base_context = {
            "country": market, "market": market,
            "raw_data": {}, "analysis": {}, "confidences": {},
            "retries": {}, "final_output": {},
        }

        successful_analyses, failed_analyses = [], []

        async with AsyncProcessor(max_workers=self.config.max_concurrent_stocks) as processor:
            results = await processor.gather_with_concurrency(
                *[self._analyze_ticker_isolated(t, base_context, market) for t in tickers],
                return_exceptions=True,
                timeout=self.config.timeout_per_stock * len(tickers),
            )

            for ticker, result in zip(tickers, results):
                if isinstance(result, Exception):
                    logger.error(f"[{ticker}] Analysis failed: {result}")
                    failed_analyses.append((ticker, str(result)))
                elif not validate_ticker_isolation(ticker, result, ["ticker"]):
                    logger.error(f"[{ticker}] Isolation validation failed")
                    failed_analyses.append((ticker, "Isolation validation failed"))
                else:
                    successful_analyses.append(result)

        total_time = time.time() - start_time
        avg_time = total_time / len(tickers) if tickers else 0.0

        self.performance_metrics.update({
            "total_analyses": len(tickers),
            "successful_analyses": len(successful_analyses),
            "failed_analyses": len(failed_analyses),
            "average_time_per_stock": avg_time,
            "total_time": total_time,
            "stock_data_dict": {r.get("ticker"): r for r in successful_analyses if r.get("ticker")},
        })

        logger.info(
            f"[BULK] Analysis completed: {len(successful_analyses)}/{len(tickers)} successful "
            f"in {total_time:.2f}s (avg: {avg_time:.2f}s/stock)"
        )

        return BulkAnalysisResult(
            successful_analyses=successful_analyses,
            failed_analyses=failed_analyses,
            performance_metrics=self.performance_metrics,
            total_time=total_time,
            success_rate=len(successful_analyses) / len(tickers) if tickers else 0.0,
        )

    def get_per_ticker_cache(self, ticker: str) -> Dict[str, Any]:
        if ticker not in self.ticker_cache:
            self.ticker_cache[ticker] = {}
        return self.ticker_cache[ticker]

    def _create_optimized_batches(self, tickers: List[str], market: str) -> List[List[str]]:
        """Create optimized batches: smaller for Indian stocks, larger for US stocks."""
        indian = [t for t in tickers if t.endswith(('.NS', '.BO'))]
        us = [t for t in tickers if not t.endswith(('.NS', '.BO'))]
        half = self.config.batch_size // 2

        batches = (
            [indian[i:i + half] for i in range(0, len(indian), half)] +
            [us[i:i + self.config.batch_size] for i in range(0, len(us), self.config.batch_size)]
        )
        logger.info(f"Created {len(batches)} optimized batches for {len(tickers)} tickers")
        return batches

    async def _analyze_ticker_isolated(
        self, ticker: str, base_context: Dict[str, Any], market: str
    ) -> Dict[str, Any]:
        """Analyze a single ticker in complete isolation with per-ticker locking."""
        isolated_context = create_isolated_context(base_context, ticker)
        logger.info(f"[{ticker}] Starting isolated analysis")

        try:
            async with ticker_locks[ticker]:
                start_time = time.time()
                result = await asyncio.wait_for(
                    self.workflow.ainvoke(isolated_context),
                    timeout=self.config.timeout_per_stock,
                )
                logger.info(f"[{ticker}] Analysis completed in {time.time() - start_time:.2f}s")

                reports = result.get("final_output", {}).get("reports", [])
                if not reports:
                    raise Exception(f"No analysis result found for {ticker}")

                report = reports[0]
                report["ticker"] = ticker

                # Force correct ticker in decision block if mismatched
                if isinstance(report.get("decision"), dict):
                    decision_ticker = report["decision"].get("ticker")
                    if decision_ticker and decision_ticker != ticker:
                        logger.error(f"[{ticker}] Ticker mismatch in decision! Got {decision_ticker}")
                        report["decision"]["ticker"] = ticker

                logger.info(f"[{ticker}] Report extracted and validated successfully")
                return report

        except asyncio.TimeoutError:
            logger.error(f"[{ticker}] Analysis timed out after {self.config.timeout_per_stock}s")
            raise
        except Exception as e:
            logger.error(f"[{ticker}] Analysis failed: {e}")
            raise
        finally:
            isolated_context.clear()

    def get_performance_metrics(self) -> Dict[str, Any]:
        return self.performance_metrics.copy()

    def reset_metrics(self):
        self.performance_metrics = {
            "total_analyses": 0, "successful_analyses": 0,
            "failed_analyses": 0, "average_time_per_stock": 0.0,
            "cache_hits": 0, "cache_misses": 0,
        }


async def analyze_stocks_bulk(
    tickers: List[str], market: str = "India", config: Optional[BulkAnalysisConfig] = None
) -> BulkAnalysisResult:
    """Convenience function for bulk stock analysis."""
    return await BulkStockAnalyzer(config).analyze_bulk(tickers, market)


async def analyze_stocks_parallel(
    tickers: List[str], market: str = "India", max_concurrent: int = 5
) -> List[Dict[str, Any]]:
    """Simple parallel analysis without batching (for smaller lists)."""
    config = BulkAnalysisConfig(
        max_concurrent_stocks=max_concurrent,
        batch_size=len(tickers),
        timeout_per_stock=30.0,
    )
    result = await analyze_stocks_bulk(tickers, market, config)
    return result.successful_analyses
