# Real-Time Data API Endpoints

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from app.tools.realtime_data import (
    get_realtime_provider, RealTimePrice, OptionsChain, CorporateAction
)
from app.auth.user_manager import get_current_user_optional, User

router = APIRouter(prefix="/realtime", tags=["real-time data"])
logger = logging.getLogger(__name__)

@router.get("/price/{ticker}")
async def get_real_time_price(ticker: str):
    """Get real-time price for a ticker"""
    try:
        provider = await get_realtime_provider()
        price_data = await provider.get_real_time_price(ticker)
        
        if not price_data:
            raise HTTPException(
                status_code=404,
                detail=f"Real-time price not available for {ticker}"
            )
        
        return {
            "ticker": price_data.ticker,
            "price": price_data.price,
            "change": price_data.change,
            "change_percent": price_data.change_percent,
            "volume": price_data.volume,
            "market_cap": price_data.market_cap,
            "timestamp": price_data.timestamp.isoformat(),
            "bid": price_data.bid,
            "ask": price_data.ask,
            "high_52w": price_data.high_52w,
            "low_52w": price_data.low_52w
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching real-time price for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch real-time price"
        )

@router.get("/prices")
async def get_multiple_prices(
    tickers: List[str] = Query(..., description="List of tickers to fetch prices for"),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get real-time prices for multiple tickers"""
    try:
        provider = await get_realtime_provider()
        results = {}
        
        for ticker in tickers:
            try:
                price_data = await provider.get_real_time_price(ticker)
                if price_data:
                    results[ticker] = {
                        "price": price_data.price,
                        "change": price_data.change,
                        "change_percent": price_data.change_percent,
                        "volume": price_data.volume,
                        "market_cap": price_data.market_cap,
                        "timestamp": price_data.timestamp.isoformat(),
                        "bid": price_data.bid,
                        "ask": price_data.ask,
                        "high_52w": price_data.high_52w,
                        "low_52w": price_data.low_52w
                    }
                else:
                    results[ticker] = {"error": "Price not available"}
            except Exception as e:
                logger.warning(f"Error fetching price for {ticker}: {e}")
                results[ticker] = {"error": str(e)}
        
        return {
            "prices": results,
            "timestamp": datetime.now().isoformat(),
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error fetching multiple prices: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch prices"
        )

@router.get("/options/{ticker}")
async def get_options_chain(
    ticker: str,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get options chain for a ticker"""
    try:
        provider = await get_realtime_provider()
        options_data = await provider.get_options_chain(ticker)
        
        if not options_data:
            raise HTTPException(
                status_code=404,
                detail=f"Options chain not available for {ticker}"
            )
        
        # Group by expiry date
        expiry_groups = {}
        for option in options_data:
            expiry_str = option.expiry_date.strftime("%Y-%m-%d")
            if expiry_str not in expiry_groups:
                expiry_groups[expiry_str] = []
            
            expiry_groups[expiry_str].append({
                "strike_price": option.strike_price,
                "call_oi": option.call_oi,
                "call_volume": option.call_volume,
                "call_iv": option.call_iv,
                "put_oi": option.put_oi,
                "put_volume": option.put_volume,
                "put_iv": option.put_iv,
                "timestamp": option.timestamp.isoformat()
            })
        
        return {
            "ticker": ticker,
            "expiry_dates": expiry_groups,
            "timestamp": datetime.now().isoformat(),
            "total_strikes": len(options_data)
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching options chain for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch options chain"
        )

@router.get("/corporate-actions/{ticker}")
async def get_corporate_actions(
    ticker: str,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get corporate actions for a ticker"""
    try:
        provider = await get_realtime_provider()
        actions_data = await provider.get_corporate_actions(ticker)
        
        if not actions_data:
            raise HTTPException(
                status_code=404,
                detail=f"Corporate actions not available for {ticker}"
            )
        
        # Filter upcoming actions (next 90 days)
        upcoming_actions = []
        current_date = datetime.now()
        
        for action in actions_data:
            if action.ex_date >= current_date and action.ex_date <= current_date + timedelta(days=90):
                upcoming_actions.append({
                    "action_type": action.action_type,
                    "ex_date": action.ex_date.isoformat(),
                    "record_date": action.record_date.isoformat(),
                    "value": action.value,
                    "ratio": action.ratio,
                    "description": action.description
                })
        
        return {
            "ticker": ticker,
            "upcoming_actions": upcoming_actions,
            "timestamp": datetime.now().isoformat(),
            "count": len(upcoming_actions)
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching corporate actions for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch corporate actions"
        )

@router.get("/market-status")
async def get_market_status():
    """Get current market status"""
    try:
        provider = await get_realtime_provider()
        status_data = await provider.get_market_status()
        
        return {
            "market_status": status_data.get("market_status", "UNKNOWN"),
            "last_update": status_data.get("last_update"),
            "nse_status": status_data.get("nse_status", "UNKNOWN"),
            "bse_status": status_data.get("bse_status", "UNKNOWN"),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching market status: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch market status"
        )

@router.get("/market-overview")
async def get_market_overview():
    """Get market overview with key indices"""
    try:
        provider = await get_realtime_provider()
        
        # Key Indian indices - Using correct Yahoo Finance symbols
        key_indices = [
            "^NSEI",  # NIFTY50
            "^NSEBANK",  # NIFTYBANK
            "^CNXIT",  # NIFTYIT
            "^CNXAUTO",  # NIFTYAUTO
            "^CNXFMCG",  # NIFTYFMCG
            "^CNXPHARMA",  # NIFTYPHARMA
            "^CNXENERGY",  # NIFTYENERGY
            "^CNXMETAL",  # NIFTYMETAL
            "^CNXREALTY",  # NIFTYREALTY
        ]
        
        overview_data = {}
        for index in key_indices:
            try:
                price_data = await provider.get_real_time_price(index)
                if price_data:
                    overview_data[index] = {
                        "price": price_data.price,
                        "change": price_data.change,
                        "change_percent": price_data.change_percent,
                        "volume": price_data.volume
                    }
            except Exception as e:
                logger.warning(f"Error fetching {index}: {e}")
                overview_data[index] = {"error": "Data not available"}
        
        # Get market status
        market_status = await provider.get_market_status()
        
        return {
            "market_status": market_status.get("market_status", "UNKNOWN"),
            "indices": overview_data,
            "timestamp": datetime.now().isoformat(),
            "count": len(overview_data)
        }
        
    except Exception as e:
        logger.error(f"Error fetching market overview: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch market overview"
        )

@router.get("/sector-performance")
async def get_sector_performance(
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get sector performance data"""
    try:
        provider = await get_realtime_provider()
        
        # Sector indices - Using correct Yahoo Finance symbols
        sectors = {
            "Banking": "^NSEBANK",
            "IT": "^CNXIT", 
            "Auto": "^CNXAUTO",
            "FMCG": "^CNXFMCG",
            "Pharma": "^CNXPHARMA",
            "Energy": "^CNXENERGY",
            "Metal": "^CNXMETAL",
            "Realty": "^CNXREALTY",
            # Note: PSU and Media indices not available on Yahoo Finance
        }
        
        sector_data = {}
        for sector_name, sector_ticker in sectors.items():
            try:
                price_data = await provider.get_real_time_price(sector_ticker)
                if price_data:
                    sector_data[sector_name] = {
                        "ticker": sector_ticker,
                        "price": price_data.price,
                        "change": price_data.change,
                        "change_percent": price_data.change_percent,
                        "volume": price_data.volume
                    }
            except Exception as e:
                logger.warning(f"Error fetching {sector_name}: {e}")
                sector_data[sector_name] = {"error": "Data not available"}
        
        # Sort by performance
        sorted_sectors = sorted(
            sector_data.items(),
            key=lambda x: x[1].get("change_percent", 0) if isinstance(x[1], dict) and "change_percent" in x[1] else -999,
            reverse=True
        )
        
        return {
            "sectors": dict(sorted_sectors),
            "timestamp": datetime.now().isoformat(),
            "count": len(sector_data)
        }
        
    except Exception as e:
        logger.error(f"Error fetching sector performance: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch sector performance"
        )
