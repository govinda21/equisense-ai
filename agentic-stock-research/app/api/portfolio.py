"""
Portfolio Management API Endpoints

RESTful API for portfolio and watchlist management functionality.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.db.portfolio_manager import (
    get_portfolio_manager,
    PortfolioManager,
    PortfolioType,
    Portfolio,
    Watchlist
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


# Pydantic models for API requests/responses
class CreatePortfolioRequest(BaseModel):
    name: str = Field(..., description="Portfolio name")
    portfolio_type: PortfolioType = Field(..., description="Portfolio type")
    description: Optional[str] = Field(None, description="Portfolio description")


class AddPositionRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker")
    quantity: float = Field(..., gt=0, description="Number of shares")
    avg_cost: float = Field(..., gt=0, description="Average cost per share")


class CreateWatchlistRequest(BaseModel):
    name: str = Field(..., description="Watchlist name")
    description: Optional[str] = Field(None, description="Watchlist description")


class AddTickerRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker to add")


class PortfolioResponse(BaseModel):
    id: str
    name: str
    portfolio_type: PortfolioType
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    positions_count: int
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None


class WatchlistResponse(BaseModel):
    id: str
    name: str
    tickers_count: int
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None


# Dependency to get portfolio manager
def get_portfolio_mgr() -> PortfolioManager:
    return get_portfolio_manager()


# Portfolio endpoints
@router.post("/portfolios", response_model=PortfolioResponse)
async def create_portfolio(
    request: CreatePortfolioRequest,
    user_id: str = Query(..., description="User ID"),
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Create a new portfolio"""
    try:
        portfolio = await portfolio_mgr.create_portfolio(
            user_id=user_id,
            name=request.name,
            portfolio_type=request.portfolio_type,
            description=request.description
        )
        
        return PortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            portfolio_type=portfolio.portfolio_type,
            total_value=portfolio.total_value,
            total_cost=portfolio.total_cost,
            total_pnl=portfolio.total_pnl,
            total_pnl_pct=portfolio.total_pnl_pct,
            positions_count=len(portfolio.positions),
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
            description=portfolio.description
        )
    
    except Exception as e:
        logger.error(f"Error creating portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios", response_model=List[PortfolioResponse])
async def get_user_portfolios(
    user_id: str = Query(..., description="User ID"),
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Get all portfolios for a user"""
    try:
        portfolios = await portfolio_mgr.get_user_portfolios(user_id)
        
        return [
            PortfolioResponse(
                id=p.id,
                name=p.name,
                portfolio_type=p.portfolio_type,
                total_value=p.total_value,
                total_cost=p.total_cost,
                total_pnl=p.total_pnl,
                total_pnl_pct=p.total_pnl_pct,
                positions_count=len(p.positions),
                created_at=p.created_at,
                updated_at=p.updated_at,
                description=p.description
            )
            for p in portfolios
        ]
    
    except Exception as e:
        logger.error(f"Error getting user portfolios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios/{portfolio_id}", response_model=Dict[str, Any])
async def get_portfolio_details(
    portfolio_id: str,
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Get detailed portfolio information with current prices"""
    try:
        portfolio = await portfolio_mgr.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        # Update with current prices
        updated_portfolio = await portfolio_mgr.update_portfolio_prices(portfolio_id)
        
        return {
            "id": updated_portfolio.id,
            "name": updated_portfolio.name,
            "portfolio_type": updated_portfolio.portfolio_type.value,
            "total_value": updated_portfolio.total_value,
            "total_cost": updated_portfolio.total_cost,
            "total_pnl": updated_portfolio.total_pnl,
            "total_pnl_pct": updated_portfolio.total_pnl_pct,
            "currency": updated_portfolio.currency,
            "positions": [
                {
                    "ticker": p.ticker,
                    "quantity": p.quantity,
                    "avg_cost": p.avg_cost,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": p.unrealized_pnl_pct,
                    "weight": p.weight,
                    "last_updated": p.last_updated.isoformat()
                }
                for p in updated_portfolio.positions
            ],
            "created_at": updated_portfolio.created_at.isoformat(),
            "updated_at": updated_portfolio.updated_at.isoformat(),
            "description": updated_portfolio.description
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolios/{portfolio_id}/positions")
async def add_position(
    portfolio_id: str,
    request: AddPositionRequest,
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Add a position to a portfolio"""
    try:
        portfolio = await portfolio_mgr.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        portfolio.add_position(
            ticker=request.ticker,
            quantity=request.quantity,
            avg_cost=request.avg_cost
        )
        
        # Update with current prices
        updated_portfolio = await portfolio_mgr.update_portfolio_prices(portfolio_id)
        
        return {"message": "Position added successfully", "portfolio_id": portfolio_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/portfolios/{portfolio_id}/positions/{ticker}")
async def remove_position(
    portfolio_id: str,
    ticker: str,
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Remove a position from a portfolio"""
    try:
        portfolio = await portfolio_mgr.get_portfolio(portfolio_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        portfolio.remove_position(ticker)
        
        # Update with current prices
        updated_portfolio = await portfolio_mgr.update_portfolio_prices(portfolio_id)
        
        return {"message": "Position removed successfully", "portfolio_id": portfolio_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolios/{portfolio_id}/performance")
async def get_portfolio_performance(
    portfolio_id: str,
    days: int = Query(30, description="Performance period in days"),
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Get portfolio performance metrics"""
    try:
        performance = await portfolio_mgr.get_portfolio_performance(portfolio_id, days)
        return performance
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting portfolio performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Watchlist endpoints
@router.post("/watchlists", response_model=WatchlistResponse)
async def create_watchlist(
    request: CreateWatchlistRequest,
    user_id: str = Query(..., description="User ID"),
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Create a new watchlist"""
    try:
        watchlist = await portfolio_mgr.create_watchlist(
            user_id=user_id,
            name=request.name,
            description=request.description
        )
        
        return WatchlistResponse(
            id=watchlist.id,
            name=watchlist.name,
            tickers_count=len(watchlist.tickers),
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at,
            description=watchlist.description
        )
    
    except Exception as e:
        logger.error(f"Error creating watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/watchlists", response_model=List[WatchlistResponse])
async def get_user_watchlists(
    user_id: str = Query(..., description="User ID"),
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Get all watchlists for a user"""
    try:
        watchlists = await portfolio_mgr.get_user_watchlists(user_id)
        
        return [
            WatchlistResponse(
                id=w.id,
                name=w.name,
                tickers_count=len(w.tickers),
                created_at=w.created_at,
                updated_at=w.updated_at,
                description=w.description
            )
            for w in watchlists
        ]
    
    except Exception as e:
        logger.error(f"Error getting user watchlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/watchlists/{watchlist_id}")
async def get_watchlist_details(
    watchlist_id: str,
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Get detailed watchlist information with current prices"""
    try:
        watchlist = await portfolio_mgr.get_watchlist(watchlist_id)
        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        
        # Update with current prices
        watchlist_data = await portfolio_mgr.update_watchlist_prices(watchlist_id)
        
        return watchlist_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting watchlist details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watchlists/{watchlist_id}/tickers")
async def add_ticker_to_watchlist(
    watchlist_id: str,
    request: AddTickerRequest,
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Add a ticker to a watchlist"""
    try:
        watchlist = await portfolio_mgr.get_watchlist(watchlist_id)
        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        
        watchlist.add_ticker(request.ticker)
        
        # Cache updated watchlist
        await portfolio_mgr._cache_watchlist(watchlist)
        
        return {"message": "Ticker added successfully", "watchlist_id": watchlist_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding ticker to watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/watchlists/{watchlist_id}/tickers/{ticker}")
async def remove_ticker_from_watchlist(
    watchlist_id: str,
    ticker: str,
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Remove a ticker from a watchlist"""
    try:
        watchlist = await portfolio_mgr.get_watchlist(watchlist_id)
        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        
        watchlist.remove_ticker(ticker)
        
        # Cache updated watchlist
        await portfolio_mgr._cache_watchlist(watchlist)
        
        return {"message": "Ticker removed successfully", "watchlist_id": watchlist_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing ticker from watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Utility endpoints
@router.get("/prices")
async def get_current_prices(
    tickers: str = Query(..., description="Comma-separated list of tickers"),
    portfolio_mgr: PortfolioManager = Depends(get_portfolio_mgr)
):
    """Get current prices for multiple tickers"""
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        price_data = await portfolio_mgr._fetch_current_prices(ticker_list)
        
        return {
            "prices": price_data,
            "timestamp": datetime.now().isoformat(),
            "tickers_requested": len(ticker_list),
            "tickers_found": len(price_data)
        }
    
    except Exception as e:
        logger.error(f"Error getting current prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
