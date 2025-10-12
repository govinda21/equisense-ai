"""
Comprehensive Backtesting Framework

Implements recommendation tracking, backtesting engine, and performance
metrics to validate and improve recommendation accuracy.

Features:
- Historical recommendation database
- Point-in-time backtesting
- Performance attribution analysis
- Continuous learning system
- Accuracy tracking and reporting
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import pandas as pd
import numpy as np
import yfinance as yf

from app.cache.redis_cache import get_cache_manager

logger = logging.getLogger(__name__)


class RecommendationAction(Enum):
    """Recommendation actions"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class EvaluationPeriod(Enum):
    """Evaluation periods for backtesting"""
    ONE_WEEK = 7
    ONE_MONTH = 30
    THREE_MONTHS = 90
    SIX_MONTHS = 180
    ONE_YEAR = 365


@dataclass
class Recommendation:
    """Historical recommendation data structure"""
    id: str
    ticker: str
    recommendation_date: datetime
    action: RecommendationAction
    rating: float  # 1-5 scale
    confidence: float  # 0-1 scale
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    time_horizon_days: int = 365
    reasoning: Optional[str] = None
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)
    market_price: float = 0.0
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    country: str = "US"


@dataclass
class BacktestResult:
    """Backtest result for a single recommendation"""
    recommendation_id: str
    ticker: str
    recommendation_date: datetime
    action: RecommendationAction
    initial_price: float
    final_price: float
    return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float
    max_drawdown_pct: float
    volatility_pct: float
    sharpe_ratio: float
    hit_target: bool = False
    hit_stop_loss: bool = False
    days_to_target: Optional[int] = None
    days_to_stop_loss: Optional[int] = None
    evaluation_period: int = 365


@dataclass
class PerformanceMetrics:
    """Aggregate performance metrics"""
    total_recommendations: int
    win_rate: float  # Percentage of profitable recommendations
    average_return: float
    median_return: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    alpha: float  # Excess return vs benchmark
    beta: float  # Market correlation
    information_ratio: float
    calmar_ratio: float
    sortino_ratio: float
    by_action: Dict[str, Dict[str, float]]  # Performance by recommendation action
    by_sector: Dict[str, Dict[str, float]]  # Performance by sector
    by_time_horizon: Dict[str, Dict[str, float]]  # Performance by time horizon


class RecommendationTracker:
    """Tracks historical recommendations and their outcomes"""
    
    def __init__(self):
        self.cache = get_cache_manager()
        self.recommendations: Dict[str, Recommendation] = {}
    
    async def record_recommendation(
        self,
        ticker: str,
        action: RecommendationAction,
        rating: float,
        confidence: float,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        time_horizon_days: int = 365,
        reasoning: Optional[str] = None,
        analysis_metadata: Optional[Dict[str, Any]] = None,
        market_price: Optional[float] = None,
        sector: Optional[str] = None,
        country: str = "US"
    ) -> str:
        """
        Record a new recommendation
        
        Returns:
            Recommendation ID
        """
        # Generate unique ID
        recommendation_id = f"{ticker}_{int(datetime.now().timestamp())}_{action.value}"
        
        # Get current market price if not provided
        if market_price is None:
            market_price = await self._get_current_price(ticker)
        
        # Create recommendation
        recommendation = Recommendation(
            id=recommendation_id,
            ticker=ticker,
            recommendation_date=datetime.now(),
            action=action,
            rating=rating,
            confidence=confidence,
            target_price=target_price,
            stop_loss=stop_loss,
            time_horizon_days=time_horizon_days,
            reasoning=reasoning,
            analysis_metadata=analysis_metadata or {},
            market_price=market_price,
            sector=sector,
            country=country
        )
        
        # Store recommendation
        self.recommendations[recommendation_id] = recommendation
        
        # Cache recommendation
        await self._cache_recommendation(recommendation)
        
        logger.info(f"Recorded recommendation {recommendation_id} for {ticker}: {action.value}")
        
        return recommendation_id
    
    async def get_recommendations(
        self,
        ticker: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[RecommendationAction] = None
    ) -> List[Recommendation]:
        """Get recommendations with optional filters"""
        recommendations = list(self.recommendations.values())
        
        # Apply filters
        if ticker:
            recommendations = [r for r in recommendations if r.ticker == ticker]
        
        if start_date:
            recommendations = [r for r in recommendations if r.recommendation_date >= start_date]
        
        if end_date:
            recommendations = [r for r in recommendations if r.recommendation_date <= end_date]
        
        if action:
            recommendations = [r for r in recommendations if r.action == action]
        
        # Sort by date (most recent first)
        recommendations.sort(key=lambda x: x.recommendation_date, reverse=True)
        
        return recommendations
    
    async def _get_current_price(self, ticker: str) -> float:
        """Get current market price for a ticker"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return info.get('currentPrice') or info.get('regularMarketPrice') or 0.0
        except Exception as e:
            logger.warning(f"Error getting current price for {ticker}: {e}")
            return 0.0
    
    async def _cache_recommendation(self, recommendation: Recommendation):
        """Cache recommendation data"""
        cache_key = f"recommendation:{recommendation.id}"
        await self.cache.set(cache_key, recommendation.__dict__, ttl=86400 * 30)  # 30 days
        
        # Also cache by ticker for quick lookup
        ticker_key = f"recommendations:{recommendation.ticker}"
        ticker_recommendations = await self.cache.get(ticker_key) or []
        ticker_recommendations.append(recommendation.id)
        await self.cache.set(ticker_key, ticker_recommendations, ttl=86400 * 30)


class BacktestEngine:
    """Backtesting engine for recommendation validation"""
    
    def __init__(self):
        self.cache = get_cache_manager()
        self.tracker = RecommendationTracker()
    
    async def run_backtest(
        self,
        recommendations: List[Recommendation],
        evaluation_periods: List[EvaluationPeriod] = None,
        benchmark_ticker: str = "SPY"
    ) -> Dict[str, Any]:
        """
        Run backtest on a list of recommendations
        
        Args:
            recommendations: List of recommendations to backtest
            evaluation_periods: Periods to evaluate (default: all periods)
            benchmark_ticker: Benchmark for comparison (default: SPY)
            
        Returns:
            Comprehensive backtest results
        """
        if not recommendations:
            return {"error": "No recommendations provided"}
        
        if evaluation_periods is None:
            evaluation_periods = list(EvaluationPeriod)
        
        try:
            # Get benchmark data
            benchmark_data = await self._get_benchmark_data(benchmark_ticker)
            
            # Run backtest for each evaluation period
            results = {}
            for period in evaluation_periods:
                period_results = await self._run_period_backtest(
                    recommendations, period, benchmark_data
                )
                results[period.name] = period_results
            
            # Calculate aggregate metrics
            aggregate_metrics = self._calculate_aggregate_metrics(results)
            
            # Generate insights
            insights = self._generate_backtest_insights(results, aggregate_metrics)
            
            return {
                "backtest_results": results,
                "aggregate_metrics": aggregate_metrics,
                "insights": insights,
                "benchmark_ticker": benchmark_ticker,
                "total_recommendations": len(recommendations),
                "evaluation_periods": [p.name for p in evaluation_periods],
                "backtest_date": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error running backtest: {e}")
            return {"error": str(e)}
    
    async def _get_benchmark_data(self, benchmark_ticker: str) -> pd.DataFrame:
        """Get benchmark price data"""
        try:
            # Get 2 years of data to ensure we have enough history
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)
            
            stock = yf.Ticker(benchmark_ticker)
            hist = stock.history(start=start_date, end=end_date)
            
            return hist[['Close']].rename(columns={'Close': 'price'})
        
        except Exception as e:
            logger.error(f"Error getting benchmark data for {benchmark_ticker}: {e}")
            return pd.DataFrame()
    
    async def _run_period_backtest(
        self,
        recommendations: List[Recommendation],
        evaluation_period: EvaluationPeriod,
        benchmark_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Run backtest for a specific evaluation period"""
        period_days = evaluation_period.value
        backtest_results = []
        
        for recommendation in recommendations:
            try:
                # Get price data for the ticker
                ticker_data = await self._get_ticker_data(
                    recommendation.ticker,
                    recommendation.recommendation_date,
                    period_days
                )
                
                if ticker_data.empty:
                    continue
                
                # Calculate returns
                initial_price = ticker_data.iloc[0]['price']
                final_price = ticker_data.iloc[-1]['price']
                return_pct = (final_price - initial_price) / initial_price
                
                # Calculate benchmark return for the same period
                benchmark_return_pct = self._calculate_benchmark_return(
                    benchmark_data,
                    recommendation.recommendation_date,
                    period_days
                )
                
                # Calculate excess return
                excess_return_pct = return_pct - benchmark_return_pct
                
                # Calculate additional metrics
                max_drawdown_pct = self._calculate_max_drawdown(ticker_data)
                volatility_pct = self._calculate_volatility(ticker_data)
                sharpe_ratio = self._calculate_sharpe_ratio(ticker_data)
                
                # Check if target/stop loss was hit
                hit_target, days_to_target = self._check_target_hit(
                    ticker_data, recommendation.target_price
                )
                hit_stop_loss, days_to_stop_loss = self._check_stop_loss_hit(
                    ticker_data, recommendation.stop_loss
                )
                
                # Create backtest result
                result = BacktestResult(
                    recommendation_id=recommendation.id,
                    ticker=recommendation.ticker,
                    recommendation_date=recommendation.recommendation_date,
                    action=recommendation.action,
                    initial_price=initial_price,
                    final_price=final_price,
                    return_pct=return_pct,
                    benchmark_return_pct=benchmark_return_pct,
                    excess_return_pct=excess_return_pct,
                    max_drawdown_pct=max_drawdown_pct,
                    volatility_pct=volatility_pct,
                    sharpe_ratio=sharpe_ratio,
                    hit_target=hit_target,
                    hit_stop_loss=hit_stop_loss,
                    days_to_target=days_to_target,
                    days_to_stop_loss=days_to_stop_loss,
                    evaluation_period=period_days
                )
                
                backtest_results.append(result)
            
            except Exception as e:
                logger.warning(f"Error backtesting recommendation {recommendation.id}: {e}")
                continue
        
        # Calculate period-specific metrics
        period_metrics = self._calculate_period_metrics(backtest_results)
        
        return {
            "period_days": period_days,
            "results": [r.__dict__ for r in backtest_results],
            "metrics": period_metrics,
            "total_recommendations": len(backtest_results)
        }
    
    async def _get_ticker_data(
        self,
        ticker: str,
        start_date: datetime,
        days: int
    ) -> pd.DataFrame:
        """Get price data for a ticker over a specific period"""
        try:
            end_date = start_date + timedelta(days=days)
            
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                return pd.DataFrame()
            
            return hist[['Close']].rename(columns={'Close': 'price'})
        
        except Exception as e:
            logger.warning(f"Error getting ticker data for {ticker}: {e}")
            return pd.DataFrame()
    
    def _calculate_benchmark_return(
        self,
        benchmark_data: pd.DataFrame,
        start_date: datetime,
        days: int
    ) -> float:
        """Calculate benchmark return for a specific period"""
        try:
            end_date = start_date + timedelta(days=days)
            
            # Find closest dates in benchmark data
            start_idx = benchmark_data.index.get_indexer([start_date], method='nearest')[0]
            end_idx = benchmark_data.index.get_indexer([end_date], method='nearest')[0]
            
            if start_idx == -1 or end_idx == -1:
                return 0.0
            
            start_price = benchmark_data.iloc[start_idx]['price']
            end_price = benchmark_data.iloc[end_idx]['price']
            
            return (end_price - start_price) / start_price
        
        except Exception as e:
            logger.warning(f"Error calculating benchmark return: {e}")
            return 0.0
    
    def _calculate_max_drawdown(self, price_data: pd.DataFrame) -> float:
        """Calculate maximum drawdown"""
        try:
            prices = price_data['price'].values
            peak = np.maximum.accumulate(prices)
            drawdown = (prices - peak) / peak
            return np.min(drawdown)
        except Exception:
            return 0.0
    
    def _calculate_volatility(self, price_data: pd.DataFrame) -> float:
        """Calculate annualized volatility"""
        try:
            returns = price_data['price'].pct_change().dropna()
            return returns.std() * np.sqrt(252)  # Annualized
        except Exception:
            return 0.0
    
    def _calculate_sharpe_ratio(self, price_data: pd.DataFrame, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        try:
            returns = price_data['price'].pct_change().dropna()
            excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
            return excess_returns.mean() / excess_returns.std() * np.sqrt(252)
        except Exception:
            return 0.0
    
    def _check_target_hit(
        self,
        price_data: pd.DataFrame,
        target_price: Optional[float]
    ) -> Tuple[bool, Optional[int]]:
        """Check if target price was hit and when"""
        if target_price is None:
            return False, None
        
        try:
            for i, (date, row) in enumerate(price_data.iterrows()):
                if row['price'] >= target_price:
                    return True, i
            return False, None
        except Exception:
            return False, None
    
    def _check_stop_loss_hit(
        self,
        price_data: pd.DataFrame,
        stop_loss: Optional[float]
    ) -> Tuple[bool, Optional[int]]:
        """Check if stop loss was hit and when"""
        if stop_loss is None:
            return False, None
        
        try:
            for i, (date, row) in enumerate(price_data.iterrows()):
                if row['price'] <= stop_loss:
                    return True, i
            return False, None
        except Exception:
            return False, None
    
    def _calculate_period_metrics(self, results: List[BacktestResult]) -> Dict[str, float]:
        """Calculate metrics for a specific period"""
        if not results:
            return {}
        
        returns = [r.return_pct for r in results]
        excess_returns = [r.excess_return_pct for r in results]
        
        # Basic metrics
        win_rate = sum(1 for r in returns if r > 0) / len(returns)
        average_return = np.mean(returns)
        median_return = np.median(returns)
        
        # Risk metrics
        volatility = np.std(returns)
        max_drawdown = min([r.max_drawdown_pct for r in results])
        
        # Risk-adjusted metrics
        sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) > 0 else 0
        alpha = np.mean(excess_returns)
        
        return {
            "win_rate": win_rate,
            "average_return": average_return,
            "median_return": median_return,
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "alpha": alpha,
            "total_recommendations": len(results)
        }
    
    def _calculate_aggregate_metrics(self, results: Dict[str, Any]) -> PerformanceMetrics:
        """Calculate aggregate performance metrics across all periods"""
        # Flatten all results
        all_results = []
        for period_results in results.values():
            all_results.extend(period_results.get("results", []))
        
        if not all_results:
            return PerformanceMetrics(
                total_recommendations=0,
                win_rate=0.0,
                average_return=0.0,
                median_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                volatility=0.0,
                alpha=0.0,
                beta=0.0,
                information_ratio=0.0,
                calmar_ratio=0.0,
                sortino_ratio=0.0,
                by_action={},
                by_sector={},
                by_time_horizon={}
            )
        
        # Convert to BacktestResult objects
        backtest_results = [BacktestResult(**r) for r in all_results]
        
        # Calculate overall metrics
        returns = [r.return_pct for r in backtest_results]
        excess_returns = [r.excess_return_pct for r in backtest_results]
        
        win_rate = sum(1 for r in returns if r > 0) / len(returns)
        average_return = np.mean(returns)
        median_return = np.median(returns)
        volatility = np.std(returns)
        max_drawdown = min([r.max_drawdown_pct for r in backtest_results])
        
        # Risk-adjusted metrics
        sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) > 0 else 0
        alpha = np.mean(excess_returns)
        beta = 1.0  # Simplified - would need market data for proper calculation
        
        # Additional metrics
        information_ratio = alpha / volatility if volatility > 0 else 0
        calmar_ratio = average_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = [r for r in returns if r < 0]
        downside_deviation = np.std(downside_returns) if downside_returns else 0
        sortino_ratio = average_return / downside_deviation if downside_deviation > 0 else 0
        
        # Performance by action
        by_action = {}
        for action in RecommendationAction:
            action_results = [r for r in backtest_results if r.action == action]
            if action_results:
                action_returns = [r.return_pct for r in action_results]
                by_action[action.value] = {
                    "count": len(action_results),
                    "win_rate": sum(1 for r in action_returns if r > 0) / len(action_returns),
                    "average_return": np.mean(action_returns),
                    "median_return": np.median(action_returns)
                }
        
        # Performance by sector (simplified)
        by_sector = {}
        sectors = set(r.ticker for r in backtest_results)  # Simplified - would need actual sector data
        for sector in sectors:
            sector_results = [r for r in backtest_results if r.ticker == sector]  # Simplified
            if sector_results:
                sector_returns = [r.return_pct for r in sector_results]
                by_sector[sector] = {
                    "count": len(sector_results),
                    "win_rate": sum(1 for r in sector_returns if r > 0) / len(sector_returns),
                    "average_return": np.mean(sector_returns)
                }
        
        # Performance by time horizon
        by_time_horizon = {}
        for period in EvaluationPeriod:
            period_results = [r for r in backtest_results if r.evaluation_period == period.value]
            if period_results:
                period_returns = [r.return_pct for r in period_results]
                by_time_horizon[period.name] = {
                    "count": len(period_results),
                    "win_rate": sum(1 for r in period_returns if r > 0) / len(period_returns),
                    "average_return": np.mean(period_returns)
                }
        
        return PerformanceMetrics(
            total_recommendations=len(backtest_results),
            win_rate=win_rate,
            average_return=average_return,
            median_return=median_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            volatility=volatility,
            alpha=alpha,
            beta=beta,
            information_ratio=information_ratio,
            calmar_ratio=calmar_ratio,
            sortino_ratio=sortino_ratio,
            by_action=by_action,
            by_sector=by_sector,
            by_time_horizon=by_time_horizon
        )
    
    def _generate_backtest_insights(
        self,
        results: Dict[str, Any],
        metrics: PerformanceMetrics
    ) -> List[str]:
        """Generate insights from backtest results"""
        insights = []
        
        # Overall performance
        if metrics.win_rate > 0.6:
            insights.append(f"Strong overall performance with {metrics.win_rate:.1%} win rate.")
        elif metrics.win_rate < 0.4:
            insights.append(f"Poor overall performance with {metrics.win_rate:.1%} win rate.")
        else:
            insights.append(f"Moderate performance with {metrics.win_rate:.1%} win rate.")
        
        # Risk-adjusted returns
        if metrics.sharpe_ratio > 1.0:
            insights.append(f"Excellent risk-adjusted returns with Sharpe ratio of {metrics.sharpe_ratio:.2f}.")
        elif metrics.sharpe_ratio < 0.5:
            insights.append(f"Poor risk-adjusted returns with Sharpe ratio of {metrics.sharpe_ratio:.2f}.")
        
        # Alpha generation
        if metrics.alpha > 0.05:
            insights.append(f"Strong alpha generation of {metrics.alpha:.1%} vs benchmark.")
        elif metrics.alpha < -0.05:
            insights.append(f"Negative alpha of {metrics.alpha:.1%} vs benchmark.")
        
        # Best performing actions
        if metrics.by_action:
            best_action = max(metrics.by_action.items(), key=lambda x: x[1]["average_return"])
            insights.append(f"Best performing recommendation type: {best_action[0]} with {best_action[1]['average_return']:.1%} average return.")
        
        # Time horizon analysis
        if metrics.by_time_horizon:
            best_horizon = max(metrics.by_time_horizon.items(), key=lambda x: x[1]["average_return"])
            insights.append(f"Best performing time horizon: {best_horizon[0]} with {best_horizon[1]['average_return']:.1%} average return.")
        
        return insights


class ContinuousLearningSystem:
    """Continuous learning system for model improvement"""
    
    def __init__(self):
        self.cache = get_cache_manager()
        self.tracker = RecommendationTracker()
        self.backtest_engine = BacktestEngine()
    
    async def update_model_weights(self, lookback_days: int = 90) -> Dict[str, Any]:
        """
        Update model weights based on recent performance
        
        Args:
            lookback_days: Number of days to look back for analysis
            
        Returns:
            Updated weights and performance metrics
        """
        try:
            # Get recent recommendations
            start_date = datetime.now() - timedelta(days=lookback_days)
            recent_recommendations = await self.tracker.get_recommendations(
                start_date=start_date
            )
            
            if len(recent_recommendations) < 10:
                return {
                    "error": "Insufficient data for weight update",
                    "recommendations_count": len(recent_recommendations)
                }
            
            # Run backtest on recent recommendations
            backtest_results = await self.backtest_engine.run_backtest(
                recent_recommendations,
                evaluation_periods=[EvaluationPeriod.ONE_MONTH, EvaluationPeriod.THREE_MONTHS]
            )
            
            # Analyze performance by analysis components
            component_performance = await self._analyze_component_performance(
                recent_recommendations, backtest_results
            )
            
            # Calculate new weights
            new_weights = self._calculate_new_weights(component_performance)
            
            # Store updated weights
            await self._store_updated_weights(new_weights)
            
            return {
                "updated_weights": new_weights,
                "component_performance": component_performance,
                "backtest_summary": backtest_results.get("aggregate_metrics", {}),
                "recommendations_analyzed": len(recent_recommendations),
                "update_date": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error updating model weights: {e}")
            return {"error": str(e)}
    
    async def _analyze_component_performance(
        self,
        recommendations: List[Recommendation],
        backtest_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze performance by analysis components"""
        component_performance = {}
        
        # Analyze by confidence levels
        confidence_buckets = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0)]
        
        for low, high in confidence_buckets:
            bucket_recommendations = [
                r for r in recommendations
                if low <= r.confidence < high
            ]
            
            if bucket_recommendations:
                # Calculate performance for this bucket
                bucket_returns = []
                for rec in bucket_recommendations:
                    # Find corresponding backtest result
                    for period_results in backtest_results.get("backtest_results", {}).values():
                        for result in period_results.get("results", []):
                            if result["recommendation_id"] == rec.id:
                                bucket_returns.append(result["return_pct"])
                                break
                
                if bucket_returns:
                    component_performance[f"confidence_{low}_{high}"] = {
                        "count": len(bucket_returns),
                        "average_return": np.mean(bucket_returns),
                        "win_rate": sum(1 for r in bucket_returns if r > 0) / len(bucket_returns)
                    }
        
        # Analyze by rating levels
        rating_buckets = [(1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0)]
        
        for low, high in rating_buckets:
            bucket_recommendations = [
                r for r in recommendations
                if low <= r.rating < high
            ]
            
            if bucket_recommendations:
                bucket_returns = []
                for rec in bucket_recommendations:
                    for period_results in backtest_results.get("backtest_results", {}).values():
                        for result in period_results.get("results", []):
                            if result["recommendation_id"] == rec.id:
                                bucket_returns.append(result["return_pct"])
                                break
                
                if bucket_returns:
                    component_performance[f"rating_{low}_{high}"] = {
                        "count": len(bucket_returns),
                        "average_return": np.mean(bucket_returns),
                        "win_rate": sum(1 for r in bucket_returns if r > 0) / len(bucket_returns)
                    }
        
        return component_performance
    
    def _calculate_new_weights(self, component_performance: Dict[str, Any]) -> Dict[str, float]:
        """Calculate new weights based on component performance"""
        # Default weights
        new_weights = {
            "confidence_weight": 0.3,
            "rating_weight": 0.3,
            "technical_weight": 0.2,
            "fundamental_weight": 0.2
        }
        
        # Adjust weights based on performance
        for component, performance in component_performance.items():
            if "confidence" in component:
                # Higher confidence should correlate with better performance
                if performance["average_return"] > 0.05:
                    new_weights["confidence_weight"] = min(0.5, new_weights["confidence_weight"] + 0.1)
                elif performance["average_return"] < -0.05:
                    new_weights["confidence_weight"] = max(0.1, new_weights["confidence_weight"] - 0.1)
            
            elif "rating" in component:
                # Higher ratings should correlate with better performance
                if performance["average_return"] > 0.05:
                    new_weights["rating_weight"] = min(0.5, new_weights["rating_weight"] + 0.1)
                elif performance["average_return"] < -0.05:
                    new_weights["rating_weight"] = max(0.1, new_weights["rating_weight"] - 0.1)
        
        # Normalize weights
        total_weight = sum(new_weights.values())
        new_weights = {k: v / total_weight for k, v in new_weights.items()}
        
        return new_weights
    
    async def _store_updated_weights(self, weights: Dict[str, float]):
        """Store updated weights in cache"""
        cache_key = "model_weights"
        await self.cache.set(cache_key, weights, ttl=86400 * 7)  # 7 days
        
        # Also store with timestamp
        timestamped_key = f"model_weights_{datetime.now().strftime('%Y%m%d')}"
        await self.cache.set(timestamped_key, weights, ttl=86400 * 30)  # 30 days


# Global instances
_recommendation_tracker = None
_backtest_engine = None
_learning_system = None

def get_recommendation_tracker() -> RecommendationTracker:
    """Get global recommendation tracker instance"""
    global _recommendation_tracker
    if _recommendation_tracker is None:
        _recommendation_tracker = RecommendationTracker()
    return _recommendation_tracker

def get_backtest_engine() -> BacktestEngine:
    """Get global backtest engine instance"""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine()
    return _backtest_engine

def get_learning_system() -> ContinuousLearningSystem:
    """Get global learning system instance"""
    global _learning_system
    if _learning_system is None:
        _learning_system = ContinuousLearningSystem()
    return _learning_system
