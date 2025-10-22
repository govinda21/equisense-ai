"""
Indian Market Data Sources Integration
NSE/BSE filing feeds, shareholding patterns, and regulatory data
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import httpx
import pandas as pd
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class ShareholdingPattern:
    """Shareholding pattern data structure"""
    date: datetime
    promoter_holding_pct: float
    promoter_pledge_pct: float
    institutional_holding_pct: float
    public_holding_pct: float
    foreign_holding_pct: float


@dataclass
class CorporateAction:
    """Corporate action data structure"""
    date: datetime
    action_type: str  # "Dividend", "Bonus", "Split", "Rights"
    details: str
    ex_date: Optional[datetime] = None
    record_date: Optional[datetime] = None


@dataclass
class FinancialFiling:
    """Financial filing data structure"""
    filing_date: datetime
    period_end: datetime
    filing_type: str  # "Quarterly", "Annual", "Unaudited"
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    ebitda: Optional[float] = None
    total_assets: Optional[float] = None
    total_debt: Optional[float] = None
    cash_and_equivalents: Optional[float] = None


class IndianMarketDataProvider:
    """Provider for Indian market-specific data sources"""
    
    def __init__(self):
        # NSE/BSE API endpoints
        self.nse_base_url = "https://www.nseindia.com/api"
        self.bse_base_url = "https://api.bseindia.com"
        
        # Cache directory for storing downloaded files
        self.cache_dir = Path("cache/indian_market_data")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Risk-free rate source (RBI/CCIL)
        self.rbi_yield_url = "https://www.rbi.org.in/Scripts/api_ccil.aspx"
        
        # Enhanced headers for NSE India API (requires proper User-Agent and Referer)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.nseindia.com/",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        
        # Session for maintaining cookies
        self._session_cookies = None
        self._session_timestamp = None
    
    async def _init_nse_session(self, client: httpx.AsyncClient) -> dict:
        """
        Initialize NSE session by visiting homepage to get cookies
        NSE requires a valid session with cookies to access API endpoints
        """
        try:
            # Check if session is recent (< 30 minutes old) - increased from 5 minutes
            if (self._session_cookies and self._session_timestamp and 
                (datetime.now() - self._session_timestamp).seconds < 1800):
                logger.debug("Using cached NSE session cookies")
                return self._session_cookies
            
            logger.info("Initializing new NSE session...")
            
            # Visit NSE homepage to get cookies with retry logic
            for attempt in range(3):
                try:
                    homepage_response = await client.get(
                        "https://www.nseindia.com", 
                        headers=self.headers,
                        timeout=15.0
                    )
                    
                    if homepage_response.status_code == 200:
                        cookies = dict(homepage_response.cookies)
                        self._session_cookies = cookies
                        self._session_timestamp = datetime.now()
                        logger.info(f"NSE session initialized successfully with {len(cookies)} cookies")
                        return cookies
                    else:
                        logger.warning(f"NSE homepage returned {homepage_response.status_code} (attempt {attempt + 1})")
                        if attempt < 2:  # Don't sleep on last attempt
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        
                except Exception as e:
                    logger.warning(f"NSE session attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
            
            logger.error("Failed to initialize NSE session after 3 attempts")
            return {}
                
        except Exception as e:
            logger.error(f"NSE session initialization error: {e}")
            return {}
    
    async def get_shareholding_pattern(self, symbol: str, exchange: str = "NSE") -> List[ShareholdingPattern]:
        """
        Fetch shareholding pattern data using yfinance (no direct NSE API calls)
        """
        try:
            logger.info(f"Fetching shareholding pattern for {symbol} using yfinance")
            
            # Use yfinance for basic company info
            import yfinance as yf
            
            def _fetch_shareholding():
                ticker_symbol = f"{symbol}.NS" if exchange.upper() == "NSE" else f"{symbol}.BO"
                t = yf.Ticker(ticker_symbol)
                info = t.info or {}
                
                # Extract shareholding data from yfinance info
                patterns = []
                
                # Major holders data
                if 'majorHoldersBreakdown' in info:
                    breakdown = info['majorHoldersBreakdown']
                    patterns.append(ShareholdingPattern(
                        quarter=datetime.now().strftime("%Y-%m"),
                        promoter_holding=breakdown.get('insidersPercentHeld', 0) / 100,
                        fii_holding=breakdown.get('institutionsPercentHeld', 0) / 100,
                        dii_holding=0,  # Not available in yfinance
                        public_holding=breakdown.get('otherPercentHeld', 0) / 100,
                        total_shares=info.get('sharesOutstanding', 0)
                    ))
                
                return patterns
            
            result = await asyncio.to_thread(_fetch_shareholding)
            logger.info(f"Successfully fetched shareholding pattern for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch shareholding pattern for {symbol}: {e}")
            return []
    
    # DEPRECATED: Old NSE API methods - replaced with yfinance
    # async def _fetch_nse_shareholding(self, symbol: str) -> List[ShareholdingPattern]:
    #     """DEPRECATED: Use yfinance instead of direct NSE API calls"""
    #     logger.warning("_fetch_nse_shareholding is deprecated - use yfinance instead")
    #     return []
    
    def _parse_nse_shareholding_data(self, data: Dict[str, Any]) -> List[ShareholdingPattern]:
        """Parse NSE shareholding pattern response"""
        patterns = []
        
        try:
            # NSE typically returns data in a specific format
            # This is a simplified parser - actual implementation would handle NSE's specific format
            if "data" in data and isinstance(data["data"], list):
                for record in data["data"]:
                    try:
                        pattern = ShareholdingPattern(
                            date=datetime.strptime(record.get("date", ""), "%d-%m-%Y"),
                            promoter_holding_pct=float(record.get("promoter_holding", 0)),
                            promoter_pledge_pct=float(record.get("promoter_pledge", 0)),
                            institutional_holding_pct=float(record.get("institutional_holding", 0)),
                            public_holding_pct=float(record.get("public_holding", 0)),
                            foreign_holding_pct=float(record.get("foreign_holding", 0))
                        )
                        patterns.append(pattern)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Failed to parse shareholding record: {e}")
                        continue
            
        except Exception as e:
            logger.error(f"Failed to parse NSE shareholding data: {e}")
        
        return sorted(patterns, key=lambda x: x.date, reverse=True)
    
    async def _fetch_bse_shareholding(self, symbol: str) -> List[ShareholdingPattern]:
        """Fetch shareholding pattern from BSE"""
        try:
            # BSE implementation would be similar to NSE
            # This is a placeholder for BSE-specific logic
            logger.info(f"BSE shareholding fetch not yet implemented for {symbol}")
            return []
        except Exception as e:
            logger.error(f"BSE shareholding fetch failed for {symbol}: {e}")
            return []
    
    async def get_corporate_actions(self, symbol: str, exchange: str = "NSE") -> List[CorporateAction]:
        """Fetch corporate actions data using yfinance"""
        try:
            logger.info(f"Fetching corporate actions for {symbol} using yfinance")
            
            # Use yfinance for corporate actions
            import yfinance as yf
            
            def _fetch_corporate_actions():
                ticker_symbol = f"{symbol}.NS" if exchange.upper() == "NSE" else f"{symbol}.BO"
                t = yf.Ticker(ticker_symbol)
                
                actions = []
                
                # Get dividend data
                try:
                    dividends = t.dividends
                    if not dividends.empty:
                        for date, amount in dividends.tail(10).items():  # Last 10 dividends
                            actions.append(CorporateAction(
                                action_type="Dividend",
                                ex_date=date,
                                record_date=date,
                                payment_date=date,
                                amount=amount,
                                description=f"Dividend of ₹{amount:.2f} per share"
                            ))
                except Exception as e:
                    logger.debug(f"No dividend data available for {symbol}: {e}")
                
                # Get stock splits
                try:
                    splits = t.splits
                    if not splits.empty:
                        for date, ratio in splits.tail(5).items():  # Last 5 splits
                            actions.append(CorporateAction(
                                action_type="Stock Split",
                                ex_date=date,
                                record_date=date,
                                payment_date=date,
                                amount=ratio,
                                description=f"Stock split {ratio}:1"
                            ))
                except Exception as e:
                    logger.debug(f"No split data available for {symbol}: {e}")
                
                return actions
            
            result = await asyncio.to_thread(_fetch_corporate_actions)
            logger.info(f"Successfully fetched {len(result)} corporate actions for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch corporate actions for {symbol}: {e}")
            return []
    
    async def _fetch_nse_corporate_actions(self, symbol: str) -> List[CorporateAction]:
        """Fetch corporate actions from NSE"""
        try:
            url = f"{self.nse_base_url}/corporates-corporateActions"
            
            async with httpx.AsyncClient(timeout=30.0, headers=self.headers, follow_redirects=True) as client:
                # Initialize session first to get cookies
                cookies = await self._init_nse_session(client)
                
                params = {
                    "symbol": symbol.upper(),
                    "from_date": (datetime.now() - timedelta(days=365*2)).strftime("%d-%m-%Y"),
                    "to_date": datetime.now().strftime("%d-%m-%Y")
                }
                
                response = await client.get(url, params=params, cookies=cookies)
                
                if response.status_code == 401:
                    logger.warning(f"NSE authentication failed (401) for corporate actions - invalidating session")
                    self._session_cookies = None
                    return []
                elif response.status_code != 200:
                    logger.warning(f"NSE corporate actions request failed: {response.status_code} (cookies: {len(cookies)} present)")
                    return []
                
                data = response.json()
                return self._parse_corporate_actions(data)
                
        except Exception as e:
            logger.error(f"NSE corporate actions fetch failed for {symbol}: {e}")
            return []
    
    def _parse_corporate_actions(self, data: Dict[str, Any]) -> List[CorporateAction]:
        """Parse corporate actions data"""
        actions = []
        
        try:
            if "data" in data and isinstance(data["data"], list):
                for record in data["data"]:
                    try:
                        action = CorporateAction(
                            date=datetime.strptime(record.get("date", ""), "%d-%m-%Y"),
                            action_type=record.get("subject", ""),
                            details=record.get("details", ""),
                            ex_date=datetime.strptime(record.get("exDate", ""), "%d-%m-%Y") if record.get("exDate") else None,
                            record_date=datetime.strptime(record.get("recordDate", ""), "%d-%m-%Y") if record.get("recordDate") else None
                        )
                        actions.append(action)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Failed to parse corporate action record: {e}")
                        continue
        except Exception as e:
            logger.error(f"Failed to parse corporate actions data: {e}")
        
        return sorted(actions, key=lambda x: x.date, reverse=True)
    
    async def get_financial_filings(self, symbol: str, exchange: str = "NSE") -> List[FinancialFiling]:
        """Fetch financial filings data using yfinance"""
        try:
            logger.info(f"Fetching financial filings for {symbol} using yfinance")
            
            # Use yfinance for financial data
            import yfinance as yf
            
            def _fetch_financial_filings():
                ticker_symbol = f"{symbol}.NS" if exchange.upper() == "NSE" else f"{symbol}.BO"
                t = yf.Ticker(ticker_symbol)
                
                filings = []
                
                # Get quarterly financials
                try:
                    quarterly = t.quarterly_financials
                    if not quarterly.empty:
                        for date in quarterly.columns:
                            filing = FinancialFiling(
                                filing_type="Quarterly Results",
                                filing_date=date,
                                period_end=date,
                                revenue=quarterly.loc['Total Revenue', date] if 'Total Revenue' in quarterly.index else 0,
                                net_income=quarterly.loc['Net Income', date] if 'Net Income' in quarterly.index else 0,
                                eps=quarterly.loc['Basic EPS', date] if 'Basic EPS' in quarterly.index else 0,
                                filing_url="",  # Not available in yfinance
                                status="Filed"
                            )
                            filings.append(filing)
                except Exception as e:
                    logger.debug(f"No quarterly financials available for {symbol}: {e}")
                
                # Get annual financials
                try:
                    annual = t.financials
                    if not annual.empty:
                        for date in annual.columns:
                            filing = FinancialFiling(
                                filing_type="Annual Results",
                                filing_date=date,
                                period_end=date,
                                revenue=annual.loc['Total Revenue', date] if 'Total Revenue' in annual.index else 0,
                                net_income=annual.loc['Net Income', date] if 'Net Income' in annual.index else 0,
                                eps=annual.loc['Basic EPS', date] if 'Basic EPS' in annual.index else 0,
                                filing_url="",  # Not available in yfinance
                                status="Filed"
                            )
                            filings.append(filing)
                except Exception as e:
                    logger.debug(f"No annual financials available for {symbol}: {e}")
                
                return filings
            
            result = await asyncio.to_thread(_fetch_financial_filings)
            logger.info(f"Successfully fetched {len(result)} financial filings for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch financial filings for {symbol}: {e}")
            return []
    
    async def _fetch_nse_financial_filings(self, symbol: str) -> List[FinancialFiling]:
        """Fetch financial filings from NSE"""
        try:
            # NSE financial results endpoint
            url = f"{self.nse_base_url}/corporates-financial-results"
            
            async with httpx.AsyncClient(timeout=30.0, headers=self.headers, follow_redirects=True) as client:
                # Initialize session first to get cookies
                cookies = await self._init_nse_session(client)
                
                params = {
                    "symbol": symbol.upper(),
                    "period": "annual"  # or "quarterly"
                }
                
                response = await client.get(url, params=params, cookies=cookies)
                
                if response.status_code == 401:
                    logger.warning(f"NSE authentication failed (401) for financial filings - invalidating session")
                    self._session_cookies = None
                    return []
                elif response.status_code != 200:
                    logger.warning(f"NSE financial filings request failed: {response.status_code} (cookies: {len(cookies)} present)")
                    return []
                
                data = response.json()
                return self._parse_financial_filings(data)
                
        except Exception as e:
            logger.error(f"NSE financial filings fetch failed for {symbol}: {e}")
            return []
    
    def _parse_financial_filings(self, data: Dict[str, Any]) -> List[FinancialFiling]:
        """Parse financial filings data"""
        filings = []
        
        try:
            if "data" in data and isinstance(data["data"], list):
                for record in data["data"]:
                    try:
                        filing = FinancialFiling(
                            filing_date=datetime.strptime(record.get("filingDate", ""), "%d-%m-%Y"),
                            period_end=datetime.strptime(record.get("periodEnd", ""), "%d-%m-%Y"),
                            filing_type=record.get("filingType", ""),
                            revenue=self._safe_float(record.get("revenue")),
                            net_profit=self._safe_float(record.get("netProfit")),
                            ebitda=self._safe_float(record.get("ebitda")),
                            total_assets=self._safe_float(record.get("totalAssets")),
                            total_debt=self._safe_float(record.get("totalDebt")),
                            cash_and_equivalents=self._safe_float(record.get("cash"))
                        )
                        filings.append(filing)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Failed to parse financial filing record: {e}")
                        continue
        except Exception as e:
            logger.error(f"Failed to parse financial filings data: {e}")
        
        return sorted(filings, key=lambda x: x.filing_date, reverse=True)
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float"""
        try:
            if value is None or value == "":
                return None
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return None
    
    async def get_risk_free_rate(self) -> Optional[float]:
        """Fetch current 10-year G-Sec yield from RBI/CCIL"""
        try:
            # This would fetch from RBI's official yield data
            # For now, return a reasonable default
            return 0.07  # 7% - typical 10-year G-Sec yield
            
            # Actual implementation would be:
            # async with httpx.AsyncClient(timeout=30.0) as client:
            #     response = await client.get(self.rbi_yield_url)
            #     data = response.json()
            #     return self._parse_yield_data(data)
            
        except Exception as e:
            logger.error(f"Failed to fetch risk-free rate: {e}")
            return 0.07  # Default fallback
    
    async def get_market_risk_premium(self) -> float:
        """Get India equity risk premium"""
        # India ERP typically ranges from 5-8%
        # This could be dynamically calculated based on market conditions
        return 0.06  # 6% - reasonable estimate for India ERP
    
    async def get_comprehensive_company_data(self, symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Fetch comprehensive company data from all Indian sources
        """
        try:
            # Parallel fetch of all data types
            results = await asyncio.gather(
                self.get_shareholding_pattern(symbol, exchange),
                self.get_corporate_actions(symbol, exchange),
                self.get_financial_filings(symbol, exchange),
                self.get_risk_free_rate(),
                return_exceptions=True
            )
            
            shareholding_data = results[0] if not isinstance(results[0], Exception) else []
            corporate_actions = results[1] if not isinstance(results[1], Exception) else []
            financial_filings = results[2] if not isinstance(results[2], Exception) else []
            risk_free_rate = results[3] if not isinstance(results[3], Exception) else 0.07
            
            # Calculate derived metrics
            latest_shareholding = shareholding_data[0] if shareholding_data else None
            recent_actions = [a for a in corporate_actions if a.date >= datetime.now() - timedelta(days=365)]
            
            return {
                "symbol": symbol,
                "exchange": exchange,
                "data_timestamp": datetime.now().isoformat(),
                
                # Ownership structure
                "shareholding_pattern": {
                    "latest": latest_shareholding.__dict__ if latest_shareholding else None,
                    "history": [sp.__dict__ for sp in shareholding_data[:8]]  # Last 8 quarters
                },
                
                # Corporate actions
                "corporate_actions": {
                    "recent": [ca.__dict__ for ca in recent_actions],
                    "upcoming": [ca.__dict__ for ca in corporate_actions if ca.date > datetime.now()]
                },
                
                # Financial data
                "financial_filings": {
                    "latest": financial_filings[0].__dict__ if financial_filings else None,
                    "history": [ff.__dict__ for ff in financial_filings[:12]]  # Last 12 filings
                },
                
                # Market data
                "market_data": {
                    "risk_free_rate": risk_free_rate,
                    "market_risk_premium": await self.get_market_risk_premium(),
                },
                
                # Governance red flags
                "governance_alerts": self._identify_governance_alerts(shareholding_data, corporate_actions),
                
                # Data quality assessment
                "data_quality": {
                    "shareholding_coverage": len(shareholding_data),
                    "filing_coverage": len(financial_filings),
                    "last_update": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch comprehensive data for {symbol}: {e}")
            return {"error": str(e)}
    
    def _identify_governance_alerts(
        self, 
        shareholding_data: List[ShareholdingPattern], 
        corporate_actions: List[CorporateAction]
    ) -> List[Dict[str, Any]]:
        """Identify governance red flags from historical data"""
        alerts = []
        
        try:
            # Check for promoter pledge increases
            if len(shareholding_data) >= 2:
                current = shareholding_data[0]
                previous = shareholding_data[1]
                
                if current.promoter_pledge_pct > previous.promoter_pledge_pct + 5:  # >5% increase
                    alerts.append({
                        "type": "promoter_pledge_increase",
                        "severity": "high" if current.promoter_pledge_pct > 50 else "medium",
                        "description": f"Promoter pledge increased from {previous.promoter_pledge_pct:.1f}% to {current.promoter_pledge_pct:.1f}%",
                        "current_value": current.promoter_pledge_pct,
                        "previous_value": previous.promoter_pledge_pct
                    })
            
            # Check for excessive promoter pledge
            if shareholding_data:
                current_pledge = shareholding_data[0].promoter_pledge_pct
                if current_pledge > 75:
                    alerts.append({
                        "type": "excessive_promoter_pledge",
                        "severity": "critical",
                        "description": f"Very high promoter pledge at {current_pledge:.1f}%",
                        "current_value": current_pledge
                    })
                elif current_pledge > 50:
                    alerts.append({
                        "type": "high_promoter_pledge",
                        "severity": "high",
                        "description": f"High promoter pledge at {current_pledge:.1f}%",
                        "current_value": current_pledge
                    })
            
            # Check for frequent corporate actions (potential manipulation)
            recent_actions = [a for a in corporate_actions if a.date >= datetime.now() - timedelta(days=365)]
            if len(recent_actions) > 3:
                alerts.append({
                    "type": "frequent_corporate_actions",
                    "severity": "medium",
                    "description": f"{len(recent_actions)} corporate actions in the last year",
                    "current_value": len(recent_actions)
                })
                
        except Exception as e:
            logger.error(f"Failed to identify governance alerts: {e}")
        
        return alerts


# Convenience functions for integration
async def get_indian_market_data(symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
    """
    Get comprehensive Indian market data for a symbol
    
    Now uses multi-source federation (v2) for improved data quality and coverage.
    Falls back to legacy provider if v2 system fails.
    """
    try:
        # Try the new multi-source federation system first
        from app.tools.indian_market_data_v2 import fetch_indian_market_data
        
        # Normalize ticker format (add .NS or .BO suffix if missing)
        ticker = symbol
        if not ticker.endswith((".NS", ".BO")):
            ticker = f"{symbol}.{exchange[:2]}"  # NSE -> NS, BSE -> BO
        
        # Fetch from multi-source system
        logger.info(f"Fetching Indian market data using multi-source federation for {ticker}")
        federated_data = await fetch_indian_market_data(ticker)
        
        if federated_data and len(federated_data) > 0:
            logger.info(f"Successfully fetched {len(federated_data)} fields from multi-source federation")
            return federated_data
        else:
            logger.warning(f"Multi-source federation returned no data for {ticker}, falling back to legacy provider")
    
    except Exception as e:
        logger.warning(f"Multi-source federation failed for {symbol}: {e}, falling back to legacy provider")
    
    # Fallback to legacy provider
    logger.info(f"Using legacy Indian market data provider for {symbol}")
    provider = IndianMarketDataProvider()
    return await provider.get_comprehensive_company_data(symbol, exchange)


async def get_current_risk_free_rate() -> float:
    """Get current Indian risk-free rate (10-year G-Sec)"""
    provider = IndianMarketDataProvider()
    rate = await provider.get_risk_free_rate()
    return rate or 0.07  # Default fallback





