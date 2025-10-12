"""
Insider Trading & Ownership Tracking System

Implements comprehensive insider trading and ownership analysis to match
Fiscal.ai capabilities and provide unique insights into smart money moves.

Features:
- SEC Form 4 integration (US stocks)
- Indian insider trading data (BSE/NSE)
- 13F institutional holdings tracking
- Sentiment scoring and alerts
- Smart money flow analysis
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

import aiohttp
from bs4 import BeautifulSoup
import yfinance as yf

from app.cache.redis_cache import get_cache_manager
from app.tools.llm_orchestrator import get_llm_orchestrator, TaskType, TaskComplexity

logger = logging.getLogger(__name__)


class TransactionType(Enum):
    """Types of insider transactions"""
    BUY = "buy"
    SELL = "sell"
    GRANT = "grant"
    EXERCISE = "exercise"
    FORFEIT = "forfeit"
    TRANSFER = "transfer"


class OwnerType(Enum):
    """Types of owners"""
    INSIDER = "insider"
    INSTITUTION = "institution"
    PROMOTER = "promoter"
    PUBLIC = "public"


@dataclass
class InsiderTransaction:
    """Insider transaction data structure"""
    ticker: str
    owner_name: str
    owner_title: str
    transaction_date: datetime
    transaction_type: TransactionType
    shares: int
    price_per_share: float
    total_value: float
    remaining_shares: int
    filing_date: datetime
    filing_url: str
    is_10b5_1: bool = False  # Scheduled vs opportunistic
    transaction_id: Optional[str] = None


@dataclass
class InstitutionalHolding:
    """Institutional holding data structure"""
    ticker: str
    institution_name: str
    shares_held: int
    market_value: float
    percentage_of_portfolio: float
    percentage_of_shares_outstanding: float
    filing_date: datetime
    quarter: str
    is_new_position: bool = False
    is_increased_position: bool = False
    is_decreased_position: bool = False


@dataclass
class OwnershipAnalysis:
    """Ownership analysis results"""
    ticker: str
    analysis_date: datetime
    
    # Insider Analysis
    insider_sentiment: float  # -1 to 1
    insider_activity_score: float  # 0 to 1
    recent_insider_transactions: List[InsiderTransaction]
    insider_net_buying: float  # Net buying in last 90 days
    
    # Institutional Analysis
    institutional_sentiment: float  # -1 to 1
    smart_money_flow: float  # -1 to 1
    top_institutional_holders: List[InstitutionalHolding]
    institutional_net_buying: float
    
    # Ownership Structure
    ownership_concentration: float  # 0 to 1
    promoter_holding_pct: float
    institutional_holding_pct: float
    public_holding_pct: float
    
    # Key Insights
    key_insights: List[str]
    risk_factors: List[str]
    confidence_score: float
    
    # Metadata
    data_sources: List[str]
    last_updated: datetime


class SECInsiderTracker:
    """SEC Form 4 insider trading tracker"""
    
    def __init__(self):
        self.base_url = "https://www.sec.gov"
        self.cache = get_cache_manager()
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'EquiSense AI (contact@equisense.ai)',
                    'Accept': 'application/json'
                }
            )
        return self.session
    
    async def get_insider_transactions(
        self,
        ticker: str,
        days_back: int = 90
    ) -> List[InsiderTransaction]:
        """
        Get recent insider transactions for a ticker
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            days_back: Number of days to look back
            
        Returns:
            List of insider transactions
        """
        cache_key = f"sec_insider_transactions:{ticker}:{days_back}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved SEC insider transactions from cache for {ticker}")
            return [InsiderTransaction(**tx) for tx in cached_result]
        
        try:
            # Get CIK for ticker
            cik = await self._get_cik_for_ticker(ticker)
            if not cik:
                logger.warning(f"Could not find CIK for ticker {ticker}")
                return []
            
            # Get recent Form 4 filings
            transactions = await self._fetch_form4_filings(cik, ticker, days_back)
            
            # Cache results for 4 hours
            await self.cache.set(cache_key, [tx.__dict__ for tx in transactions], ttl=14400)
            
            logger.info(f"Retrieved {len(transactions)} SEC insider transactions for {ticker}")
            return transactions
        
        except Exception as e:
            logger.error(f"Error fetching SEC insider transactions for {ticker}: {e}")
            return []
    
    async def _get_cik_for_ticker(self, ticker: str) -> Optional[str]:
        """Get CIK (Central Index Key) for a ticker"""
        cache_key = f"ticker_cik:{ticker}"
        
        # Check cache first
        cached_cik = await self.cache.get(cache_key)
        if cached_cik:
            return cached_cik
        
        try:
            session = await self._get_session()
            
            # SEC company tickers API
            url = f"{self.base_url}/files/company_tickers.json"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Find CIK for ticker
                    for company in data.get("data", []):
                        if company[0].upper() == ticker.upper():
                            cik = str(company[2]).zfill(10)  # Pad with zeros
                            
                            # Cache CIK for 24 hours
                            await self.cache.set(cache_key, cik, ttl=86400)
                            
                            return cik
            
            return None
        
        except Exception as e:
            logger.warning(f"Error getting CIK for {ticker}: {e}")
            return None
    
    async def _fetch_form4_filings(
        self,
        cik: str,
        ticker: str,
        days_back: int
    ) -> List[InsiderTransaction]:
        """Fetch Form 4 filings for a CIK"""
        transactions = []
        
        try:
            session = await self._get_session()
            
            # SEC filings API
            url = f"{self.base_url}/data/Archives/edgar/data/{cik}/"
            
            # Get recent filings
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # This is a simplified implementation
            # In production, you'd use the SEC's more sophisticated API endpoints
            
            # For now, return empty list - would need proper SEC API integration
            logger.info(f"Form 4 filing fetch for {ticker} (CIK: {cik}) - requires SEC API integration")
            
            return transactions
        
        except Exception as e:
            logger.error(f"Error fetching Form 4 filings: {e}")
            return transactions


class IndianInsiderTracker:
    """Indian insider trading tracker (BSE/NSE)"""
    
    def __init__(self):
        self.bse_url = "https://www.bseindia.com"
        self.nse_url = "https://www.nseindia.com"
        self.cache = get_cache_manager()
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
            )
        return self.session
    
    async def get_insider_transactions(
        self,
        ticker: str,
        days_back: int = 90
    ) -> List[InsiderTransaction]:
        """
        Get recent insider transactions for an Indian ticker
        
        Args:
            ticker: Stock ticker (e.g., 'RELIANCE')
            days_back: Number of days to look back
            
        Returns:
            List of insider transactions
        """
        cache_key = f"indian_insider_transactions:{ticker}:{days_back}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved Indian insider transactions from cache for {ticker}")
            return [InsiderTransaction(**tx) for tx in cached_result]
        
        try:
            # Get transactions from both BSE and NSE
            bse_transactions = await self._fetch_bse_insider_data(ticker, days_back)
            nse_transactions = await self._fetch_nse_insider_data(ticker, days_back)
            
            # Combine and deduplicate
            all_transactions = bse_transactions + nse_transactions
            unique_transactions = self._deduplicate_transactions(all_transactions)
            
            # Cache results for 4 hours
            await self.cache.set(cache_key, [tx.__dict__ for tx in unique_transactions], ttl=14400)
            
            logger.info(f"Retrieved {len(unique_transactions)} Indian insider transactions for {ticker}")
            return unique_transactions
        
        except Exception as e:
            logger.error(f"Error fetching Indian insider transactions for {ticker}: {e}")
            return []
    
    async def _fetch_bse_insider_data(
        self,
        ticker: str,
        days_back: int
    ) -> List[InsiderTransaction]:
        """Fetch insider data from BSE"""
        transactions = []
        
        try:
            session = await self._get_session()
            
            # BSE insider trading URL
            url = f"{self.bse_url}/corporate/List_Scrips.aspx"
            
            # Rate limiting
            await asyncio.sleep(1.0)
            
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"BSE returned {response.status} for insider data")
                    return transactions
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract insider trading data
                # This is a simplified implementation - actual BSE structure may vary
                insider_rows = soup.find_all('tr', class_='TTRow')
                
                for row in insider_rows[:20]:  # Limit to recent transactions
                    try:
                        cells = row.find_all('td')
                        if len(cells) >= 6:
                            transaction_date_str = cells[0].get_text(strip=True)
                            owner_name = cells[1].get_text(strip=True)
                            transaction_type_str = cells[2].get_text(strip=True)
                            shares_str = cells[3].get_text(strip=True)
                            price_str = cells[4].get_text(strip=True)
                            
                            # Parse transaction details
                            transaction_date = self._parse_date(transaction_date_str)
                            if not transaction_date or (datetime.now() - transaction_date).days > days_back:
                                continue
                            
                            transaction_type = self._parse_transaction_type(transaction_type_str)
                            shares = self._parse_number(shares_str)
                            price = self._parse_number(price_str)
                            
                            if shares and price:
                                transaction = InsiderTransaction(
                                    ticker=ticker,
                                    owner_name=owner_name,
                                    owner_title="Insider",
                                    transaction_date=transaction_date,
                                    transaction_type=transaction_type,
                                    shares=shares,
                                    price_per_share=price,
                                    total_value=shares * price,
                                    remaining_shares=0,  # Not available from BSE
                                    filing_date=transaction_date,
                                    filing_url=f"{self.bse_url}/corporate/",
                                    is_10b5_1=False
                                )
                                transactions.append(transaction)
                    
                    except Exception as e:
                        logger.warning(f"Error parsing BSE insider row: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Error fetching BSE insider data: {e}")
        
        return transactions
    
    async def _fetch_nse_insider_data(
        self,
        ticker: str,
        days_back: int
    ) -> List[InsiderTransaction]:
        """Fetch insider data from NSE"""
        transactions = []
        
        try:
            session = await self._get_session()
            
            # NSE insider trading URL
            url = f"{self.nse_url}/corporates/corporateHome.html"
            
            # Rate limiting
            await asyncio.sleep(1.0)
            
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"NSE returned {response.status} for insider data")
                    return transactions
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract insider trading data
                # This is a simplified implementation - actual NSE structure may vary
                insider_rows = soup.find_all('tr', class_='TTRow')
                
                for row in insider_rows[:20]:  # Limit to recent transactions
                    try:
                        cells = row.find_all('td')
                        if len(cells) >= 6:
                            transaction_date_str = cells[0].get_text(strip=True)
                            owner_name = cells[1].get_text(strip=True)
                            transaction_type_str = cells[2].get_text(strip=True)
                            shares_str = cells[3].get_text(strip=True)
                            price_str = cells[4].get_text(strip=True)
                            
                            # Parse transaction details
                            transaction_date = self._parse_date(transaction_date_str)
                            if not transaction_date or (datetime.now() - transaction_date).days > days_back:
                                continue
                            
                            transaction_type = self._parse_transaction_type(transaction_type_str)
                            shares = self._parse_number(shares_str)
                            price = self._parse_number(price_str)
                            
                            if shares and price:
                                transaction = InsiderTransaction(
                                    ticker=ticker,
                                    owner_name=owner_name,
                                    owner_title="Insider",
                                    transaction_date=transaction_date,
                                    transaction_type=transaction_type,
                                    shares=shares,
                                    price_per_share=price,
                                    total_value=shares * price,
                                    remaining_shares=0,  # Not available from NSE
                                    filing_date=transaction_date,
                                    filing_url=f"{self.nse_url}/corporates/",
                                    is_10b5_1=False
                                )
                                transactions.append(transaction)
                    
                    except Exception as e:
                        logger.warning(f"Error parsing NSE insider row: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Error fetching NSE insider data: {e}")
        
        return transactions
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various formats"""
        try:
            formats = [
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%Y-%m-%d",
                "%d %b %Y",
                "%d %B %Y"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            return None
        except Exception:
            return None
    
    def _parse_transaction_type(self, type_str: str) -> TransactionType:
        """Parse transaction type from string"""
        type_lower = type_str.lower()
        
        if any(word in type_lower for word in ['buy', 'purchase', 'acquire']):
            return TransactionType.BUY
        elif any(word in type_lower for word in ['sell', 'dispose', 'disposal']):
            return TransactionType.SELL
        elif any(word in type_lower for word in ['grant', 'award']):
            return TransactionType.GRANT
        elif any(word in type_lower for word in ['exercise']):
            return TransactionType.EXERCISE
        else:
            return TransactionType.TRANSFER
    
    def _parse_number(self, num_str: str) -> Optional[int]:
        """Parse number from string"""
        try:
            # Remove commas and other characters
            cleaned = re.sub(r'[^\d.]', '', num_str)
            return int(float(cleaned)) if cleaned else None
        except Exception:
            return None
    
    def _deduplicate_transactions(self, transactions: List[InsiderTransaction]) -> List[InsiderTransaction]:
        """Remove duplicate transactions"""
        seen = set()
        unique_transactions = []
        
        for transaction in transactions:
            # Create a key based on owner, date, and shares
            key = (transaction.owner_name, transaction.transaction_date.date(), transaction.shares)
            
            if key not in seen:
                seen.add(key)
                unique_transactions.append(transaction)
        
        # Sort by transaction date (most recent first)
        unique_transactions.sort(key=lambda x: x.transaction_date, reverse=True)
        
        return unique_transactions


class InstitutionalTracker:
    """13F institutional holdings tracker"""
    
    def __init__(self):
        self.base_url = "https://www.sec.gov"
        self.cache = get_cache_manager()
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'EquiSense AI (contact@equisense.ai)',
                    'Accept': 'application/json'
                }
            )
        return self.session
    
    async def get_institutional_holdings(
        self,
        ticker: str,
        quarters_back: int = 4
    ) -> List[InstitutionalHolding]:
        """
        Get institutional holdings for a ticker
        
        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            quarters_back: Number of quarters to look back
            
        Returns:
            List of institutional holdings
        """
        cache_key = f"institutional_holdings:{ticker}:{quarters_back}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved institutional holdings from cache for {ticker}")
            return [InstitutionalHolding(**holding) for holding in cached_result]
        
        try:
            # Get CIK for ticker
            cik = await self._get_cik_for_ticker(ticker)
            if not cik:
                logger.warning(f"Could not find CIK for ticker {ticker}")
                return []
            
            # Get 13F holdings
            holdings = await self._fetch_13f_holdings(cik, ticker, quarters_back)
            
            # Cache results for 6 hours
            await self.cache.set(cache_key, [h.__dict__ for h in holdings], ttl=21600)
            
            logger.info(f"Retrieved {len(holdings)} institutional holdings for {ticker}")
            return holdings
        
        except Exception as e:
            logger.error(f"Error fetching institutional holdings for {ticker}: {e}")
            return []
    
    async def _get_cik_for_ticker(self, ticker: str) -> Optional[str]:
        """Get CIK for a ticker (reuse from SECInsiderTracker)"""
        cache_key = f"ticker_cik:{ticker}"
        
        # Check cache first
        cached_cik = await self.cache.get(cache_key)
        if cached_cik:
            return cached_cik
        
        try:
            session = await self._get_session()
            
            # SEC company tickers API
            url = f"{self.base_url}/files/company_tickers.json"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Find CIK for ticker
                    for company in data.get("data", []):
                        if company[0].upper() == ticker.upper():
                            cik = str(company[2]).zfill(10)  # Pad with zeros
                            
                            # Cache CIK for 24 hours
                            await self.cache.set(cache_key, cik, ttl=86400)
                            
                            return cik
            
            return None
        
        except Exception as e:
            logger.warning(f"Error getting CIK for {ticker}: {e}")
            return None
    
    async def _fetch_13f_holdings(
        self,
        cik: str,
        ticker: str,
        quarters_back: int
    ) -> List[InstitutionalHolding]:
        """Fetch 13F holdings for a CIK"""
        holdings = []
        
        try:
            # This is a simplified implementation
            # In production, you'd use the SEC's 13F API or third-party services
            
            logger.info(f"13F holdings fetch for {ticker} (CIK: {cik}) - requires SEC 13F API integration")
            
            return holdings
        
        except Exception as e:
            logger.error(f"Error fetching 13F holdings: {e}")
            return holdings


class InsiderTracker:
    """Main insider trading and ownership analysis system"""
    
    def __init__(self):
        self.sec_tracker = SECInsiderTracker()
        self.indian_tracker = IndianInsiderTracker()
        self.institutional_tracker = InstitutionalTracker()
        self.cache = get_cache_manager()
        self.llm_orchestrator = get_llm_orchestrator()
    
    async def analyze_ownership(
        self,
        ticker: str,
        days_back: int = 90,
        quarters_back: int = 4
    ) -> OwnershipAnalysis:
        """
        Analyze ownership and insider activity for a ticker
        
        Args:
            ticker: Stock ticker symbol
            days_back: Number of days to look back for insider transactions
            quarters_back: Number of quarters to look back for institutional holdings
            
        Returns:
            Comprehensive ownership analysis
        """
        cache_key = f"ownership_analysis:{ticker}:{days_back}:{quarters_back}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved ownership analysis from cache for {ticker}")
            return OwnershipAnalysis(**cached_result)
        
        try:
            # Determine market (US vs Indian)
            is_indian_stock = ticker.endswith(('.NS', '.BO'))
            clean_ticker = ticker.replace('.NS', '').replace('.BO', '')
            
            # Get insider transactions
            if is_indian_stock:
                insider_transactions = await self.indian_tracker.get_insider_transactions(
                    clean_ticker, days_back
                )
            else:
                insider_transactions = await self.sec_tracker.get_insider_transactions(
                    clean_ticker, days_back
                )
            
            # Get institutional holdings (US only for now)
            institutional_holdings = []
            if not is_indian_stock:
                institutional_holdings = await self.institutional_tracker.get_institutional_holdings(
                    clean_ticker, quarters_back
                )
            
            # Analyze insider sentiment
            insider_analysis = self._analyze_insider_sentiment(insider_transactions)
            
            # Analyze institutional sentiment
            institutional_analysis = self._analyze_institutional_sentiment(institutional_holdings)
            
            # Get ownership structure
            ownership_structure = await self._get_ownership_structure(ticker)
            
            # Generate insights
            insights = await self._generate_insights(
                insider_transactions, institutional_holdings, ownership_structure
            )
            
            # Create analysis
            analysis = OwnershipAnalysis(
                ticker=ticker,
                analysis_date=datetime.now(),
                insider_sentiment=insider_analysis["sentiment"],
                insider_activity_score=insider_analysis["activity_score"],
                recent_insider_transactions=insider_transactions[:10],  # Top 10
                insider_net_buying=insider_analysis["net_buying"],
                institutional_sentiment=institutional_analysis["sentiment"],
                smart_money_flow=institutional_analysis["smart_money_flow"],
                top_institutional_holders=institutional_holdings[:10],  # Top 10
                institutional_net_buying=institutional_analysis["net_buying"],
                ownership_concentration=ownership_structure.get("concentration", 0.0),
                promoter_holding_pct=ownership_structure.get("promoter_pct", 0.0),
                institutional_holding_pct=ownership_structure.get("institutional_pct", 0.0),
                public_holding_pct=ownership_structure.get("public_pct", 0.0),
                key_insights=insights["insights"],
                risk_factors=insights["risks"],
                confidence_score=insights["confidence"],
                data_sources=["SEC", "BSE", "NSE"] if is_indian_stock else ["SEC"],
                last_updated=datetime.now()
            )
            
            # Cache results for 6 hours
            await self.cache.set(cache_key, analysis.__dict__, ttl=21600)
            
            logger.info(f"Completed ownership analysis for {ticker}")
            return analysis
        
        except Exception as e:
            logger.error(f"Error analyzing ownership for {ticker}: {e}")
            
            # Return empty analysis on error
            return OwnershipAnalysis(
                ticker=ticker,
                analysis_date=datetime.now(),
                insider_sentiment=0.0,
                insider_activity_score=0.0,
                recent_insider_transactions=[],
                insider_net_buying=0.0,
                institutional_sentiment=0.0,
                smart_money_flow=0.0,
                top_institutional_holders=[],
                institutional_net_buying=0.0,
                ownership_concentration=0.0,
                promoter_holding_pct=0.0,
                institutional_holding_pct=0.0,
                public_holding_pct=0.0,
                key_insights=["Error in ownership analysis"],
                risk_factors=[],
                confidence_score=0.0,
                data_sources=[],
                last_updated=datetime.now()
            )
    
    def _analyze_insider_sentiment(
        self,
        transactions: List[InsiderTransaction]
    ) -> Dict[str, Any]:
        """Analyze insider sentiment from transactions"""
        if not transactions:
            return {
                "sentiment": 0.0,
                "activity_score": 0.0,
                "net_buying": 0.0
            }
        
        # Calculate net buying
        total_buying = sum(
            tx.total_value for tx in transactions
            if tx.transaction_type == TransactionType.BUY
        )
        total_selling = sum(
            tx.total_value for tx in transactions
            if tx.transaction_type == TransactionType.SELL
        )
        
        net_buying = total_buying - total_selling
        total_activity = total_buying + total_selling
        
        # Calculate sentiment (-1 to 1)
        if total_activity > 0:
            sentiment = net_buying / total_activity
        else:
            sentiment = 0.0
        
        # Calculate activity score (0 to 1)
        activity_score = min(1.0, len(transactions) / 10.0)  # Normalize to 10 transactions
        
        return {
            "sentiment": round(sentiment, 3),
            "activity_score": round(activity_score, 3),
            "net_buying": net_buying
        }
    
    def _analyze_institutional_sentiment(
        self,
        holdings: List[InstitutionalHolding]
    ) -> Dict[str, Any]:
        """Analyze institutional sentiment from holdings"""
        if not holdings:
            return {
                "sentiment": 0.0,
                "smart_money_flow": 0.0,
                "net_buying": 0.0
            }
        
        # Calculate net buying from position changes
        total_increases = sum(
            h.market_value for h in holdings
            if h.is_increased_position
        )
        total_decreases = sum(
            h.market_value for h in holdings
            if h.is_decreased_position
        )
        
        net_buying = total_increases - total_decreases
        total_activity = total_increases + total_decreases
        
        # Calculate sentiment (-1 to 1)
        if total_activity > 0:
            sentiment = net_buying / total_activity
        else:
            sentiment = 0.0
        
        # Smart money flow (weighted by institution size)
        smart_money_flow = sentiment  # Simplified for now
        
        return {
            "sentiment": round(sentiment, 3),
            "smart_money_flow": round(smart_money_flow, 3),
            "net_buying": net_buying
        }
    
    async def _get_ownership_structure(self, ticker: str) -> Dict[str, float]:
        """Get ownership structure from yfinance"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Extract ownership percentages
            promoter_pct = info.get('heldPercentInsiders', 0.0) * 100
            institutional_pct = info.get('heldPercentInstitutions', 0.0) * 100
            public_pct = 100 - promoter_pct - institutional_pct
            
            # Calculate concentration (Herfindahl index)
            concentration = (promoter_pct ** 2 + institutional_pct ** 2 + public_pct ** 2) / 10000
            
            return {
                "promoter_pct": promoter_pct,
                "institutional_pct": institutional_pct,
                "public_pct": public_pct,
                "concentration": concentration
            }
        
        except Exception as e:
            logger.warning(f"Error getting ownership structure for {ticker}: {e}")
            return {
                "promoter_pct": 0.0,
                "institutional_pct": 0.0,
                "public_pct": 100.0,
                "concentration": 0.0
            }
    
    async def _generate_insights(
        self,
        insider_transactions: List[InsiderTransaction],
        institutional_holdings: List[InstitutionalHolding],
        ownership_structure: Dict[str, float]
    ) -> Dict[str, Any]:
        """Generate key insights from ownership data"""
        insights = []
        risks = []
        confidence = 0.0
        
        # Insider insights
        if insider_transactions:
            buy_transactions = [tx for tx in insider_transactions if tx.transaction_type == TransactionType.BUY]
            sell_transactions = [tx for tx in insider_transactions if tx.transaction_type == TransactionType.SELL]
            
            if len(buy_transactions) > len(sell_transactions):
                insights.append(f"Insiders are net buyers with {len(buy_transactions)} buy transactions vs {len(sell_transactions)} sell transactions.")
            elif len(sell_transactions) > len(buy_transactions):
                insights.append(f"Insiders are net sellers with {len(sell_transactions)} sell transactions vs {len(buy_transactions)} buy transactions.")
                risks.append("High insider selling activity may indicate concerns about company prospects.")
            
            # Large transactions
            large_transactions = [tx for tx in insider_transactions if tx.total_value > 1000000]  # > $1M
            if large_transactions:
                insights.append(f"Notable large transactions: {len(large_transactions)} transactions over $1M.")
        
        # Institutional insights
        if institutional_holdings:
            new_positions = [h for h in institutional_holdings if h.is_new_position]
            increased_positions = [h for h in institutional_holdings if h.is_increased_position]
            
            if new_positions:
                insights.append(f"New institutional positions: {len(new_positions)} institutions initiated positions.")
            
            if increased_positions:
                insights.append(f"Increased institutional positions: {len(increased_positions)} institutions increased holdings.")
        
        # Ownership structure insights
        promoter_pct = ownership_structure.get("promoter_pct", 0.0)
        institutional_pct = ownership_structure.get("institutional_pct", 0.0)
        concentration = ownership_structure.get("concentration", 0.0)
        
        if promoter_pct > 50:
            insights.append(f"High promoter holding ({promoter_pct:.1f}%) indicates strong insider confidence.")
        elif promoter_pct < 20:
            risks.append(f"Low promoter holding ({promoter_pct:.1f}%) may indicate lack of insider confidence.")
        
        if institutional_pct > 70:
            insights.append(f"High institutional ownership ({institutional_pct:.1f}%) suggests professional investor interest.")
        
        if concentration > 0.5:
            risks.append(f"High ownership concentration ({concentration:.2f}) may indicate governance risks.")
        
        # Calculate confidence
        data_points = len(insider_transactions) + len(institutional_holdings)
        confidence = min(1.0, data_points / 20.0)  # Normalize to 20 data points
        
        return {
            "insights": insights,
            "risks": risks,
            "confidence": round(confidence, 2)
        }


# Main function for integration
async def analyze_ownership(ticker: str, days_back: int = 90, quarters_back: int = 4) -> OwnershipAnalysis:
    """
    Main function to analyze ownership and insider activity
    
    Args:
        ticker: Stock ticker symbol
        days_back: Number of days to look back for insider transactions
        quarters_back: Number of quarters to look back for institutional holdings
        
    Returns:
        Comprehensive ownership analysis
    """
    tracker = InsiderTracker()
    return await tracker.analyze_ownership(ticker, days_back, quarters_back)
