"""
Backtesting API Endpoints

RESTful API for backtesting and performance analysis functionality.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.backtesting.engine import (
    get_recommendation_tracker,
    get_backtest_engine,
    get_learning_system,
    RecommendationTracker,
    BacktestEngine,
    ContinuousLearningSystem,
    RecommendationAction,
    EvaluationPeriod
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backtesting", tags=["backtesting"])


# Pydantic models for API requests/responses
class RecordRecommendationRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker")
    action: RecommendationAction = Field(..., description="Recommendation action")
    rating: float = Field(..., ge=1.0, le=5.0, description="Rating (1-5 scale)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence (0-1 scale)")
    target_price: Optional[float] = Field(None, description="Target price")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    time_horizon_days: int = Field(365, description="Time horizon in days")
    reasoning: Optional[str] = Field(None, description="Reasoning for recommendation")
    sector: Optional[str] = Field(None, description="Sector")
    country: str = Field("US", description="Country")


class BacktestRequest(BaseModel):
    ticker: Optional[str] = Field(None, description="Filter by ticker")
    start_date: Optional[datetime] = Field(None, description="Start date for recommendations")
    end_date: Optional[datetime] = Field(None, description="End date for recommendations")
    action: Optional[RecommendationAction] = Field(None, description="Filter by action")
    evaluation_periods: List[EvaluationPeriod] = Field(
        default=[EvaluationPeriod.ONE_MONTH, EvaluationPeriod.THREE_MONTHS, EvaluationPeriod.ONE_YEAR],
        description="Evaluation periods"
    )
    benchmark_ticker: str = Field("SPY", description="Benchmark ticker")


class RecommendationResponse(BaseModel):
    id: str
    ticker: str
    recommendation_date: datetime
    action: RecommendationAction
    rating: float
    confidence: float
    target_price: Optional[float]
    stop_loss: Optional[float]
    time_horizon_days: int
    reasoning: Optional[str]
    market_price: float
    sector: Optional[str]
    country: str


class BacktestResultResponse(BaseModel):
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
    hit_target: bool
    hit_stop_loss: bool
    days_to_target: Optional[int]
    days_to_stop_loss: Optional[int]
    evaluation_period: int


# Dependency to get services
def get_tracker() -> RecommendationTracker:
    return get_recommendation_tracker()

def get_engine() -> BacktestEngine:
    return get_backtest_engine()

def get_learning() -> ContinuousLearningSystem:
    return get_learning_system()


# Recommendation tracking endpoints
@router.post("/recommendations", response_model=Dict[str, str])
async def record_recommendation(
    request: RecordRecommendationRequest,
    tracker: RecommendationTracker = Depends(get_tracker)
):
    """Record a new recommendation for backtesting"""
    try:
        recommendation_id = await tracker.record_recommendation(
            ticker=request.ticker,
            action=request.action,
            rating=request.rating,
            confidence=request.confidence,
            target_price=request.target_price,
            stop_loss=request.stop_loss,
            time_horizon_days=request.time_horizon_days,
            reasoning=request.reasoning,
            sector=request.sector,
            country=request.country
        )
        
        return {
            "recommendation_id": recommendation_id,
            "message": "Recommendation recorded successfully"
        }
    
    except Exception as e:
        logger.error(f"Error recording recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    action: Optional[RecommendationAction] = Query(None, description="Filter by action"),
    limit: int = Query(100, description="Maximum number of recommendations to return"),
    tracker: RecommendationTracker = Depends(get_tracker)
):
    """Get recommendations with optional filters"""
    try:
        recommendations = await tracker.get_recommendations(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            action=action
        )
        
        # Limit results
        recommendations = recommendations[:limit]
        
        return [
            RecommendationResponse(
                id=r.id,
                ticker=r.ticker,
                recommendation_date=r.recommendation_date,
                action=r.action,
                rating=r.rating,
                confidence=r.confidence,
                target_price=r.target_price,
                stop_loss=r.stop_loss,
                time_horizon_days=r.time_horizon_days,
                reasoning=r.reasoning,
                market_price=r.market_price,
                sector=r.sector,
                country=r.country
            )
            for r in recommendations
        ]
    
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: str,
    tracker: RecommendationTracker = Depends(get_tracker)
):
    """Get a specific recommendation by ID"""
    try:
        recommendations = await tracker.get_recommendations()
        recommendation = next((r for r in recommendations if r.id == recommendation_id), None)
        
        if not recommendation:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return RecommendationResponse(
            id=recommendation.id,
            ticker=recommendation.ticker,
            recommendation_date=recommendation.recommendation_date,
            action=recommendation.action,
            rating=recommendation.rating,
            confidence=recommendation.confidence,
            target_price=recommendation.target_price,
            stop_loss=recommendation.stop_loss,
            time_horizon_days=recommendation.time_horizon_days,
            reasoning=recommendation.reasoning,
            market_price=recommendation.market_price,
            sector=recommendation.sector,
            country=recommendation.country
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Backtesting endpoints
@router.post("/backtest", response_model=Dict[str, Any])
async def run_backtest(
    request: BacktestRequest,
    tracker: RecommendationTracker = Depends(get_tracker),
    engine: BacktestEngine = Depends(get_engine)
):
    """Run backtest on recommendations"""
    try:
        # Get recommendations based on filters
        recommendations = await tracker.get_recommendations(
            ticker=request.ticker,
            start_date=request.start_date,
            end_date=request.end_date,
            action=request.action
        )
        
        if not recommendations:
            raise HTTPException(status_code=400, detail="No recommendations found matching criteria")
        
        # Run backtest
        results = await engine.run_backtest(
            recommendations=recommendations,
            evaluation_periods=request.evaluation_periods,
            benchmark_ticker=request.benchmark_ticker
        )
        
        return results
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest/{ticker}", response_model=Dict[str, Any])
async def get_ticker_backtest(
    ticker: str,
    days_back: int = Query(365, description="Number of days to look back"),
    evaluation_periods: List[EvaluationPeriod] = Query(
        default=[EvaluationPeriod.ONE_MONTH, EvaluationPeriod.THREE_MONTHS, EvaluationPeriod.ONE_YEAR],
        description="Evaluation periods"
    ),
    benchmark_ticker: str = Query("SPY", description="Benchmark ticker"),
    tracker: RecommendationTracker = Depends(get_tracker),
    engine: BacktestEngine = Depends(get_engine)
):
    """Get backtest results for a specific ticker"""
    try:
        # Get recommendations for ticker
        start_date = datetime.now() - timedelta(days=days_back)
        recommendations = await tracker.get_recommendations(
            ticker=ticker,
            start_date=start_date
        )
        
        if not recommendations:
            return {
                "ticker": ticker,
                "message": "No recommendations found for this ticker",
                "recommendations_count": 0
            }
        
        # Run backtest
        results = await engine.run_backtest(
            recommendations=recommendations,
            evaluation_periods=evaluation_periods,
            benchmark_ticker=benchmark_ticker
        )
        
        return results
    
    except Exception as e:
        logger.error(f"Error getting ticker backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Performance analysis endpoints
@router.get("/performance/summary", response_model=Dict[str, Any])
async def get_performance_summary(
    days_back: int = Query(365, description="Number of days to look back"),
    tracker: RecommendationTracker = Depends(get_tracker),
    engine: BacktestEngine = Depends(get_engine)
):
    """Get overall performance summary"""
    try:
        # Get recent recommendations
        start_date = datetime.now() - timedelta(days=days_back)
        recommendations = await tracker.get_recommendations(start_date=start_date)
        
        if not recommendations:
            return {
                "message": "No recommendations found in the specified period",
                "recommendations_count": 0
            }
        
        # Run backtest
        results = await engine.run_backtest(
            recommendations=recommendations,
            evaluation_periods=[EvaluationPeriod.ONE_MONTH, EvaluationPeriod.THREE_MONTHS, EvaluationPeriod.ONE_YEAR]
        )
        
        return {
            "performance_summary": results.get("aggregate_metrics", {}),
            "insights": results.get("insights", []),
            "recommendations_analyzed": len(recommendations),
            "analysis_period": f"{days_back} days",
            "analysis_date": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/by-action", response_model=Dict[str, Any])
async def get_performance_by_action(
    days_back: int = Query(365, description="Number of days to look back"),
    tracker: RecommendationTracker = Depends(get_tracker),
    engine: BacktestEngine = Depends(get_engine)
):
    """Get performance breakdown by recommendation action"""
    try:
        # Get recent recommendations
        start_date = datetime.now() - timedelta(days=days_back)
        recommendations = await tracker.get_recommendations(start_date=start_date)
        
        if not recommendations:
            return {
                "message": "No recommendations found in the specified period",
                "by_action": {}
            }
        
        # Run backtest
        results = await engine.run_backtest(
            recommendations=recommendations,
            evaluation_periods=[EvaluationPeriod.ONE_MONTH, EvaluationPeriod.THREE_MONTHS]
        )
        
        return {
            "by_action": results.get("aggregate_metrics", {}).get("by_action", {}),
            "recommendations_analyzed": len(recommendations),
            "analysis_period": f"{days_back} days"
        }
    
    except Exception as e:
        logger.error(f"Error getting performance by action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/by-sector", response_model=Dict[str, Any])
async def get_performance_by_sector(
    days_back: int = Query(365, description="Number of days to look back"),
    tracker: RecommendationTracker = Depends(get_tracker),
    engine: BacktestEngine = Depends(get_engine)
):
    """Get performance breakdown by sector"""
    try:
        # Get recent recommendations
        start_date = datetime.now() - timedelta(days=days_back)
        recommendations = await tracker.get_recommendations(start_date=start_date)
        
        if not recommendations:
            return {
                "message": "No recommendations found in the specified period",
                "by_sector": {}
            }
        
        # Run backtest
        results = await engine.run_backtest(
            recommendations=recommendations,
            evaluation_periods=[EvaluationPeriod.ONE_MONTH, EvaluationPeriod.THREE_MONTHS]
        )
        
        return {
            "by_sector": results.get("aggregate_metrics", {}).get("by_sector", {}),
            "recommendations_analyzed": len(recommendations),
            "analysis_period": f"{days_back} days"
        }
    
    except Exception as e:
        logger.error(f"Error getting performance by sector: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Continuous learning endpoints
@router.post("/learning/update-weights", response_model=Dict[str, Any])
async def update_model_weights(
    lookback_days: int = Query(90, description="Number of days to look back for analysis"),
    learning_system: ContinuousLearningSystem = Depends(get_learning)
):
    """Update model weights based on recent performance"""
    try:
        results = await learning_system.update_model_weights(lookback_days)
        return results
    
    except Exception as e:
        logger.error(f"Error updating model weights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/current-weights", response_model=Dict[str, Any])
async def get_current_weights(
    learning_system: ContinuousLearningSystem = Depends(get_learning)
):
    """Get current model weights"""
    try:
        # This would typically come from cache or database
        # For now, return default weights
        return {
            "weights": {
                "confidence_weight": 0.3,
                "rating_weight": 0.3,
                "technical_weight": 0.2,
                "fundamental_weight": 0.2
            },
            "last_updated": datetime.now().isoformat(),
            "message": "Default weights - use update-weights endpoint to get current weights"
        }
    
    except Exception as e:
        logger.error(f"Error getting current weights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Utility endpoints
@router.get("/stats", response_model=Dict[str, Any])
async def get_backtesting_stats(
    tracker: RecommendationTracker = Depends(get_tracker)
):
    """Get backtesting statistics"""
    try:
        # Get all recommendations
        all_recommendations = await tracker.get_recommendations()
        
        # Calculate stats
        total_recommendations = len(all_recommendations)
        
        # Stats by action
        action_stats = {}
        for action in RecommendationAction:
            action_count = len([r for r in all_recommendations if r.action == action])
            action_stats[action.value] = action_count
        
        # Stats by ticker
        ticker_stats = {}
        for recommendation in all_recommendations:
            ticker = recommendation.ticker
            if ticker not in ticker_stats:
                ticker_stats[ticker] = 0
            ticker_stats[ticker] += 1
        
        # Top tickers
        top_tickers = sorted(ticker_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Date range
        if all_recommendations:
            dates = [r.recommendation_date for r in all_recommendations]
            earliest_date = min(dates)
            latest_date = max(dates)
        else:
            earliest_date = None
            latest_date = None
        
        return {
            "total_recommendations": total_recommendations,
            "by_action": action_stats,
            "top_tickers": top_tickers,
            "date_range": {
                "earliest": earliest_date.isoformat() if earliest_date else None,
                "latest": latest_date.isoformat() if latest_date else None
            },
            "last_updated": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting backtesting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "recommendation_tracker": "active",
            "backtest_engine": "active",
            "learning_system": "active"
        }
    }
