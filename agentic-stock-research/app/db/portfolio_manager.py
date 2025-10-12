"""
Portfolio & Dashboard Management System

Implements comprehensive portfolio tracking, watchlist management, and
performance analytics to match Fiscal.ai dashboard capabilities.

Features:
- Multi-portfolio support
- Real-time price tracking
- Performance analytics
- Custom dashboard builder
- Alert system integration
- Export capabilities
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

import yfinance as yf
import pandas as pd
import numpy as np

from app.cache.redis_cache import get_cache_manager

logger = logging.getLogger(__name__)


class PortfolioType(Enum):
    """Portfolio types"""
    WATCHLIST = "watchlist"
    VIRTUAL_PORTFOLIO = "virtual_portfolio"
    ACTUAL_PORTFOLIO = "actual_portfolio"


@dataclass
class PortfolioPosition:
    """Individual position in a portfolio"""
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    weight: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def update_price(self, new_price: float):
        """Update position with new price"""
        self.current_price = new_price
        self.market_value = self.quantity * new_price
        self.unrealized_pnl = self.market_value - (self.quantity * self.avg_cost)
        self.unrealized_pnl_pct = (self.unrealized_pnl / (self.quantity * self.avg_cost)) * 100
        self.last_updated = datetime.now()


@dataclass
class Portfolio:
    """Portfolio data structure"""
    id: str
    name: str
    user_id: str
    portfolio_type: PortfolioType
    positions: List[PortfolioPosition] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    total_value: float = 0.0
    total_cost: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    currency: str = "USD"
    description: Optional[str] = None
    
    def add_position(self, ticker: str, quantity: float, avg_cost: float):
        """Add a new position to the portfolio"""
        # Check if position already exists
        existing = next((p for p in self.positions if p.ticker == ticker), None)
        if existing:
            # Update existing position
            total_cost = (existing.quantity * existing.avg_cost) + (quantity * avg_cost)
            total_quantity = existing.quantity + quantity
            existing.avg_cost = total_cost / total_quantity
            existing.quantity = total_quantity
        else:
            # Add new position
            position = PortfolioPosition(
                ticker=ticker,
                quantity=quantity,
                avg_cost=avg_cost
            )
            self.positions.append(position)
        
        self.updated_at = datetime.now()
    
    def remove_position(self, ticker: str):
        """Remove a position from the portfolio"""
        self.positions = [p for p in self.positions if p.ticker != ticker]
        self.updated_at = datetime.now()
    
    def update_positions(self, price_data: Dict[str, float]):
        """Update all positions with current prices"""
        for position in self.positions:
            if position.ticker in price_data:
                position.update_price(price_data[position.ticker])
        
        self._recalculate_totals()
        self.updated_at = datetime.now()
    
    def _recalculate_totals(self):
        """Recalculate portfolio totals"""
        self.total_value = sum(p.market_value for p in self.positions)
        self.total_cost = sum(p.quantity * p.avg_cost for p in self.positions)
        self.total_pnl = self.total_value - self.total_cost
        self.total_pnl_pct = (self.total_pnl / self.total_cost) * 100 if self.total_cost > 0 else 0.0
        
        # Update position weights
        for position in self.positions:
            position.weight = (position.market_value / self.total_value) * 100 if self.total_value > 0 else 0.0


@dataclass
class Watchlist:
    """Watchlist data structure"""
    id: str
    name: str
    user_id: str
    tickers: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    description: Optional[str] = None
    
    def add_ticker(self, ticker: str):
        """Add ticker to watchlist"""
        if ticker not in self.tickers:
            self.tickers.append(ticker)
            self.updated_at = datetime.now()
    
    def remove_ticker(self, ticker: str):
        """Remove ticker from watchlist"""
        if ticker in self.tickers:
            self.tickers.remove(ticker)
            self.updated_at = datetime.now()


class PortfolioManager:
    """Main portfolio management system"""
    
    def __init__(self):
        self.cache = get_cache_manager()
        self.portfolios: Dict[str, Portfolio] = {}
        self.watchlists: Dict[str, Watchlist] = {}
    
    async def create_portfolio(
        self,
        user_id: str,
        name: str,
        portfolio_type: PortfolioType,
        description: Optional[str] = None
    ) -> Portfolio:
        """Create a new portfolio"""
        portfolio_id = f"{user_id}_{name}_{int(datetime.now().timestamp())}"
        
        portfolio = Portfolio(
            id=portfolio_id,
            name=name,
            user_id=user_id,
            portfolio_type=portfolio_type,
            description=description
        )
        
        self.portfolios[portfolio_id] = portfolio
        
        # Cache portfolio
        await self._cache_portfolio(portfolio)
        
        logger.info(f"Created portfolio {portfolio_id} for user {user_id}")
        return portfolio
    
    async def create_watchlist(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None
    ) -> Watchlist:
        """Create a new watchlist"""
        watchlist_id = f"{user_id}_{name}_{int(datetime.now().timestamp())}"
        
        watchlist = Watchlist(
            id=watchlist_id,
            name=name,
            user_id=user_id,
            description=description
        )
        
        self.watchlists[watchlist_id] = watchlist
        
        # Cache watchlist
        await self._cache_watchlist(watchlist)
        
        logger.info(f"Created watchlist {watchlist_id} for user {user_id}")
        return watchlist
    
    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Get portfolio by ID"""
        # Check cache first
        cached_portfolio = await self._get_cached_portfolio(portfolio_id)
        if cached_portfolio:
            return cached_portfolio
        
        # Check in-memory
        return self.portfolios.get(portfolio_id)
    
    async def get_watchlist(self, watchlist_id: str) -> Optional[Watchlist]:
        """Get watchlist by ID"""
        # Check cache first
        cached_watchlist = await self._get_cached_watchlist(watchlist_id)
        if cached_watchlist:
            return cached_watchlist
        
        # Check in-memory
        return self.watchlists.get(watchlist_id)
    
    async def get_user_portfolios(self, user_id: str) -> List[Portfolio]:
        """Get all portfolios for a user"""
        user_portfolios = []
        
        # Check in-memory portfolios
        for portfolio in self.portfolios.values():
            if portfolio.user_id == user_id:
                user_portfolios.append(portfolio)
        
        # Check cache for additional portfolios
        cache_key = f"user_portfolios:{user_id}"
        cached_ids = await self.cache.get(cache_key)
        if cached_ids:
            for portfolio_id in cached_ids:
                if portfolio_id not in [p.id for p in user_portfolios]:
                    cached_portfolio = await self._get_cached_portfolio(portfolio_id)
                    if cached_portfolio:
                        user_portfolios.append(cached_portfolio)
        
        return user_portfolios
    
    async def get_user_watchlists(self, user_id: str) -> List[Watchlist]:
        """Get all watchlists for a user"""
        user_watchlists = []
        
        # Check in-memory watchlists
        for watchlist in self.watchlists.values():
            if watchlist.user_id == user_id:
                user_watchlists.append(watchlist)
        
        # Check cache for additional watchlists
        cache_key = f"user_watchlists:{user_id}"
        cached_ids = await self.cache.get(cache_key)
        if cached_ids:
            for watchlist_id in cached_ids:
                if watchlist_id not in [w.id for w in user_watchlists]:
                    cached_watchlist = await self._get_cached_watchlist(watchlist_id)
                    if cached_watchlist:
                        user_watchlists.append(cached_watchlist)
        
        return user_watchlists
    
    async def update_portfolio_prices(self, portfolio_id: str) -> Portfolio:
        """Update portfolio with current market prices"""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Get current prices for all tickers
        tickers = [p.ticker for p in portfolio.positions]
        price_data = await self._fetch_current_prices(tickers)
        
        # Update portfolio positions
        portfolio.update_positions(price_data)
        
        # Cache updated portfolio
        await self._cache_portfolio(portfolio)
        
        logger.info(f"Updated prices for portfolio {portfolio_id}")
        return portfolio
    
    async def update_watchlist_prices(self, watchlist_id: str) -> Dict[str, Any]:
        """Update watchlist with current market prices"""
        watchlist = await self.get_watchlist(watchlist_id)
        if not watchlist:
            raise ValueError(f"Watchlist {watchlist_id} not found")
        
        # Get current prices for all tickers
        price_data = await self._fetch_current_prices(watchlist.tickers)
        
        # Calculate price changes
        watchlist_data = {
            "id": watchlist_id,
            "name": watchlist.name,
            "tickers": [],
            "last_updated": datetime.now().isoformat()
        }
        
        for ticker in watchlist.tickers:
            if ticker in price_data:
                ticker_data = {
                    "ticker": ticker,
                    "current_price": price_data[ticker],
                    "last_updated": datetime.now().isoformat()
                }
                watchlist_data["tickers"].append(ticker_data)
        
        # Cache watchlist data
        await self.cache.set(f"watchlist_data:{watchlist_id}", watchlist_data, ttl=300)  # 5 minutes
        
        logger.info(f"Updated prices for watchlist {watchlist_id}")
        return watchlist_data
    
    async def get_portfolio_performance(
        self,
        portfolio_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get portfolio performance metrics"""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Update with current prices
        await self.update_portfolio_prices(portfolio_id)
        
        # Calculate performance metrics
        performance = {
            "portfolio_id": portfolio_id,
            "name": portfolio.name,
            "total_value": portfolio.total_value,
            "total_cost": portfolio.total_cost,
            "total_pnl": portfolio.total_pnl,
            "total_pnl_pct": portfolio.total_pnl_pct,
            "positions": [],
            "sector_allocation": {},
            "risk_metrics": {},
            "performance_period": f"{days} days",
            "last_updated": portfolio.updated_at.isoformat()
        }
        
        # Position-level performance
        for position in portfolio.positions:
            position_data = {
                "ticker": position.ticker,
                "quantity": position.quantity,
                "avg_cost": position.avg_cost,
                "current_price": position.current_price,
                "market_value": position.market_value,
                "unrealized_pnl": position.unrealized_pnl,
                "unrealized_pnl_pct": position.unrealized_pnl_pct,
                "weight": position.weight
            }
            performance["positions"].append(position_data)
        
        # Calculate sector allocation (simplified)
        performance["sector_allocation"] = await self._calculate_sector_allocation(portfolio)
        
        # Calculate risk metrics
        performance["risk_metrics"] = await self._calculate_risk_metrics(portfolio)
        
        return performance
    
    async def _fetch_current_prices(self, tickers: List[str]) -> Dict[str, float]:
        """Fetch current prices for tickers"""
        if not tickers:
            return {}
        
        price_data = {}
        
        try:
            # Use yfinance to get current prices
            for ticker in tickers:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                    
                    if current_price:
                        price_data[ticker] = float(current_price)
                    else:
                        logger.warning(f"Could not get price for {ticker}")
                
                except Exception as e:
                    logger.warning(f"Error fetching price for {ticker}: {e}")
                    continue
            
            logger.info(f"Fetched prices for {len(price_data)}/{len(tickers)} tickers")
            
        except Exception as e:
            logger.error(f"Error fetching current prices: {e}")
        
        return price_data
    
    async def _calculate_sector_allocation(self, portfolio: Portfolio) -> Dict[str, float]:
        """Calculate sector allocation for portfolio"""
        # Simplified sector allocation - in production, this would use
        # a proper sector mapping service
        sector_allocation = {}
        
        for position in portfolio.positions:
            # Simple sector mapping based on ticker patterns
            sector = self._get_ticker_sector(position.ticker)
            if sector not in sector_allocation:
                sector_allocation[sector] = 0.0
            sector_allocation[sector] += position.weight
        
        return sector_allocation
    
    def _get_ticker_sector(self, ticker: str) -> str:
        """Get sector for a ticker (simplified mapping)"""
        ticker_upper = ticker.upper()
        
        # Indian stocks
        if ticker.endswith('.NS') or ticker.endswith('.BO'):
            if any(bank in ticker_upper for bank in ['BANK', 'HDFC', 'ICICI', 'SBI']):
                return "Financial Services"
            elif any(tech in ticker_upper for tech in ['TCS', 'INFY', 'WIPRO', 'HCL']):
                return "Information Technology"
            elif any(energy in ticker_upper for energy in ['RELIANCE', 'ONGC', 'IOC']):
                return "Energy"
            else:
                return "Other"
        
        # US stocks
        else:
            if any(bank in ticker_upper for bank in ['JPM', 'BAC', 'WFC', 'C']):
                return "Financial Services"
            elif any(tech in ticker_upper for tech in ['AAPL', 'MSFT', 'GOOGL', 'AMZN']):
                return "Technology"
            elif any(energy in ticker_upper for energy in ['XOM', 'CVX', 'COP']):
                return "Energy"
            else:
                return "Other"
    
    async def _calculate_risk_metrics(self, portfolio: Portfolio) -> Dict[str, float]:
        """Calculate risk metrics for portfolio"""
        # Simplified risk metrics calculation
        risk_metrics = {
            "concentration_risk": 0.0,
            "sector_concentration": 0.0,
            "estimated_beta": 1.0,
            "estimated_volatility": 0.15
        }
        
        if not portfolio.positions:
            return risk_metrics
        
        # Calculate concentration risk (max position weight)
        max_weight = max(p.weight for p in portfolio.positions)
        risk_metrics["concentration_risk"] = max_weight
        
        # Calculate sector concentration (max sector weight)
        sector_allocation = await self._calculate_sector_allocation(portfolio)
        if sector_allocation:
            max_sector_weight = max(sector_allocation.values())
            risk_metrics["sector_concentration"] = max_sector_weight
        
        return risk_metrics
    
    async def _cache_portfolio(self, portfolio: Portfolio):
        """Cache portfolio data"""
        cache_key = f"portfolio:{portfolio.id}"
        await self.cache.set(cache_key, portfolio.__dict__, ttl=3600)  # 1 hour
        
        # Update user portfolios list
        user_cache_key = f"user_portfolios:{portfolio.user_id}"
        user_portfolios = await self.cache.get(user_cache_key) or []
        if portfolio.id not in user_portfolios:
            user_portfolios.append(portfolio.id)
            await self.cache.set(user_cache_key, user_portfolios, ttl=86400)  # 24 hours
    
    async def _cache_watchlist(self, watchlist: Watchlist):
        """Cache watchlist data"""
        cache_key = f"watchlist:{watchlist.id}"
        await self.cache.set(cache_key, watchlist.__dict__, ttl=3600)  # 1 hour
        
        # Update user watchlists list
        user_cache_key = f"user_watchlists:{watchlist.user_id}"
        user_watchlists = await self.cache.get(user_cache_key) or []
        if watchlist.id not in user_watchlists:
            user_watchlists.append(watchlist.id)
            await self.cache.set(user_cache_key, user_watchlists, ttl=86400)  # 24 hours
    
    async def _get_cached_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Get portfolio from cache"""
        cache_key = f"portfolio:{portfolio_id}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return Portfolio(**cached_data)
        return None
    
    async def _get_cached_watchlist(self, watchlist_id: str) -> Optional[Watchlist]:
        """Get watchlist from cache"""
        cache_key = f"watchlist:{watchlist_id}"
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return Watchlist(**cached_data)
        return None


# Global portfolio manager instance
_portfolio_manager = None

def get_portfolio_manager() -> PortfolioManager:
    """Get global portfolio manager instance"""
    global _portfolio_manager
    if _portfolio_manager is None:
        _portfolio_manager = PortfolioManager()
    return _portfolio_manager
