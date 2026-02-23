"""
Real-time data provider for Indian markets using yfinance
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass
from app.monitoring.alert_engine import MarketEvent
logger = logging.getLogger(__name__)

@dataclass
class RealTimePrice:
    ticker: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: float
    timestamp: datetime
    high_52w: float = 0
    low_52w: float = 0

@dataclass
class OptionsChain:
    ticker: str
    expiry_date: datetime
    strike_price: float
    call_oi: int
    call_volume: int
    call_iv: float
    put_oi: int
    put_volume: int
    put_iv: float
    timestamp: datetime

@dataclass
class CorporateAction:
    action_type: str
    ex_date: datetime
    record_date: datetime
    payment_date: datetime
    amount: float
    description: Optional[str] = None

class RealTimeDataProvider:
    """Real-time data provider for Indian markets using yfinance"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 30  # 30 seconds for real-time data
        
    async def get_real_time_price(self, ticker: str) -> Optional[RealTimePrice]:
        """Get real-time price for a ticker using yfinance"""
        cache_key = f"realtime_price:{ticker}"
        
        # Check cache first
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                return cached_data
        
        try:
            # Use yfinance for all data (NSE, BSE, etc.)
            price_data = await self._get_yfinance_price(ticker)
            if price_data:
                self.cache[cache_key] = (price_data, datetime.now())
                return price_data
            
        except Exception as e:
            logger.error(f"Error fetching real-time price for {ticker}: {e}")
        
        return None
    
    async def _get_yfinance_price(self, ticker: str) -> Optional[RealTimePrice]:
        """Get price from yfinance (works for NSE, BSE, and other exchanges)"""
        try:
            import yfinance as yf

            def _fetch_price():
                t = yf.Ticker(ticker)
                info = t.info or {}

                # Log the fetched info for debugging
                logger.debug(f"Fetched info for {ticker}: {info}")

                # Get latest price from history
                hist = t.history(period="1d", interval="1m")
                latest_price = hist['Close'].iloc[-1] if len(hist) > 0 else info.get('currentPrice', 0)

                # Calculate change
                prev_close = info.get('previousClose', latest_price)
                change = latest_price - prev_close
                change_percent = (change / prev_close * 100) if prev_close > 0 else 0

                return RealTimePrice(
                    ticker=ticker,
                    price=latest_price,
                    change=change,
                    change_percent=change_percent,
                    volume=info.get('volume', 0),
                    market_cap=info.get('marketCap', 0),
                    timestamp=datetime.now(),
                    high_52w=info.get('fiftyTwoWeekHigh', 0),
                    low_52w=info.get('fiftyTwoWeekLow', 0)
                )

            result = await asyncio.to_thread(_fetch_price)
            logger.debug(f"Successfully fetched yfinance price for {ticker}: {result}")
            return result

        except Exception as e:
            logger.warning(f"yfinance API error for {ticker}: {e}")

        return None
    
    async def get_options_chain(self, ticker: str) -> List[OptionsChain]:
        """Get options chain for a ticker using yfinance"""
        cache_key = f"options_chain:{ticker}"
        
        # Check cache first
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(minutes=5):  # 5 min cache for options
                return cached_data
        
        try:
            import yfinance as yf
            
            def _fetch_options():
                t = yf.Ticker(ticker)
                try:
                    # Get options data
                    options = t.options
                    if not options:
                        return []
                    
                    # Get the nearest expiry
                    nearest_expiry = options[0]
                    option_chain = t.option_chain(nearest_expiry)
                    
                    chains = []
                    # Process calls
                    for _, row in option_chain.calls.iterrows():
                        chains.append(OptionsChain(
                            ticker=ticker,
                            expiry_date=datetime.strptime(nearest_expiry, '%Y-%m-%d'),
                            strike_price=row['strike'],
                            call_oi=row['openInterest'],
                            call_volume=row['volume'],
                            call_iv=row.get('impliedVolatility', 0),
                            put_oi=0,  # Will be filled from puts
                            put_volume=0,
                            put_iv=0,
                            timestamp=datetime.now()
                        ))
                    
                    # Process puts
                    for _, row in option_chain.puts.iterrows():
                        chains.append(OptionsChain(
                            ticker=ticker,
                            expiry_date=datetime.strptime(nearest_expiry, '%Y-%m-%d'),
                            strike_price=row['strike'],
                            call_oi=0,  # Will be filled from calls
                            call_volume=0,
                            call_iv=0,
                            put_oi=row['openInterest'],
                            put_volume=row['volume'],
                            put_iv=row.get('impliedVolatility', 0),
                            timestamp=datetime.now()
                        ))
                    
                    return chains
                except Exception as e:
                    logger.warning(f"yfinance options error for {ticker}: {e}")
                    return []
            
            result = await asyncio.to_thread(_fetch_options)
            if result:
                self.cache[cache_key] = (result, datetime.now())
            return result
                
        except Exception as e:
            logger.error(f"Error fetching options chain for {ticker}: {e}")
        
        return []
    
    async def get_corporate_actions(self, ticker: str) -> List[CorporateAction]:
        """Get corporate actions for a ticker using yfinance"""
        cache_key = f"corporate_actions:{ticker}"
        
        # Check cache first
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(hours=1):  # 1 hour cache for corporate actions
                return cached_data
        
        try:
            import yfinance as yf
            
            def _fetch_corporate_actions():
                t = yf.Ticker(ticker)
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
                    logger.debug(f"No dividend data available for {ticker}: {e}")
                
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
                    logger.debug(f"No split data available for {ticker}: {e}")
                
                return actions
            
            result = await asyncio.to_thread(_fetch_corporate_actions)
            if result:
                self.cache[cache_key] = (result, datetime.now())
            return result
                        
        except Exception as e:
            logger.error(f"Error fetching corporate actions for {ticker}: {e}")
        
        return []

# Global provider instance
_realtime_provider = None

async def get_realtime_provider() -> RealTimeDataProvider:
    """Get the global real-time data provider instance"""
    global _realtime_provider
    if _realtime_provider is None:
        _realtime_provider = RealTimeDataProvider()
    return _realtime_provider

from enum import Enum

class MarketEvent(Enum):
    PRICE_UPDATE = "price_update"
    TECHNICAL_SIGNAL = "technical_signal"

class EventTrigger:
    """
    Represents a trigger for market events based on specific conditions.
    """

    def __init__(self, event_type: str, condition: callable, priority: int = 5):
        """
        Initialize an EventTrigger.

        :param event_type: Type of the event (e.g., "PRICE_UPDATE").
        :param condition: A callable that evaluates whether the event is triggered.
        :param priority: Priority of the trigger (higher means more important).
        """
        self.event_type = event_type
        self.condition = condition
        self.priority = priority

    def check(self, data: dict) -> bool:
        """
        Check if the event is triggered based on the provided data.

        :param data: Data to evaluate the condition.
        :return: True if the event is triggered, False otherwise.
        """
        return self.condition(data)

class EventDrivenAnalyzer:
    def __init__(self):
        self.triggers: List[EventTrigger] = []
        self._setup_default_triggers()

    def _setup_default_triggers(self):
        # Basic price movement trigger
        default_trigger = EventTrigger(
            MarketEvent.PRICE_UPDATE,
            lambda d: abs(d.get("change_percent", 0)) > 3.0,
            priority=5
        )
        self.triggers.append(default_trigger)
        self._sort_triggers()

    def add_trigger(self, trigger: EventTrigger):
        self.triggers.append(trigger)
        self._sort_triggers()

    def _sort_triggers(self):
        self.triggers.sort(key=lambda t: t.priority, reverse=True)

class MarketDataAggregator:
    def __init__(self):
        self.market_indicators = {}

    async def update_market_context(self) -> dict:
        vix = self.market_indicators.get("vix", 20)

        # Determine volatility regime
        if vix < 15:
            regime = "low_volatility"
        elif vix < 20:
            regime = "normal"
        elif vix < 30:
            regime = "elevated_volatility"
        else:
            regime = "high_volatility"

        # Determine market session (simple time-based logic)
        now = datetime.utcnow().hour

        if 13 <= now <= 20:
            session = "regular"
        elif 11 <= now < 13:
            session = "pre_market"
        elif 20 < now <= 23:
            session = "after_hours"
        else:
            session = "closed"

        return {
            "regime": regime,
            "session": session
        }