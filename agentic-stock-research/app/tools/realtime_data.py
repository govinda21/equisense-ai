"""
Real-time data ingestion and event-driven updates with production WebSocket providers
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import os

import httpx
from asyncio import Queue

logger = logging.getLogger(__name__)


class DataProvider(Enum):
    """Supported real-time data providers"""
    ALPHA_VANTAGE = "alpha_vantage"
    POLYGON = "polygon"
    FINNHUB = "finnhub"
    IEX_CLOUD = "iex_cloud"
    YAHOO_FINANCE = "yahoo_finance"


class MarketEvent(Enum):
    """Types of market events"""
    PRICE_UPDATE = "price_update"
    VOLUME_SPIKE = "volume_spike"
    NEWS_ALERT = "news_alert"
    EARNINGS_RELEASE = "earnings_release"
    ANALYST_CHANGE = "analyst_change"
    INSIDER_TRADE = "insider_trade"
    TECHNICAL_SIGNAL = "technical_signal"
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"


class EventTrigger:
    """Define conditions for triggering events"""
    
    def __init__(
        self,
        event_type: MarketEvent,
        condition: Callable[[Dict[str, Any]], bool],
        priority: int = 5
    ):
        self.event_type = event_type
        self.condition = condition
        self.priority = priority  # 1-10, higher is more important
    
    def check(self, data: Dict[str, Any]) -> bool:
        """Check if trigger condition is met"""
        try:
            return self.condition(data)
        except Exception as e:
            logger.error(f"Trigger check failed: {e}")
            return False


class RealtimeDataStream:
    """
    Real-time data streaming with WebSocket and polling fallback
    """
    
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.websocket = None
        self.is_connected = False
        self.last_price = None
        self.last_volume = None
        self.subscribers: Set[Callable] = set()
        self.event_queue: Queue = Queue()
        
    async def connect_websocket(self, provider: DataProvider = DataProvider.POLYGON):
        """Connect to WebSocket for real-time data based on provider"""
        try:
            import websockets
            
            # Get API keys from environment
            api_keys = {
                DataProvider.POLYGON: os.getenv("POLYGON_API_KEY"),
                DataProvider.FINNHUB: os.getenv("FINNHUB_API_KEY"),
                DataProvider.ALPHA_VANTAGE: os.getenv("ALPHA_VANTAGE_API_KEY"),
                DataProvider.IEX_CLOUD: os.getenv("IEX_CLOUD_API_KEY"),
            }
            
            api_key = api_keys.get(provider)
            if not api_key:
                logger.warning(f"No API key for {provider.value}, falling back to polling")
                asyncio.create_task(self._polling_fallback())
                return
            
            # Provider-specific WebSocket URLs
            ws_urls = {
                DataProvider.POLYGON: f"wss://socket.polygon.io/stocks",
                DataProvider.FINNHUB: f"wss://ws.finnhub.io?token={api_key}",
                DataProvider.ALPHA_VANTAGE: None,  # No WebSocket support
                DataProvider.IEX_CLOUD: f"wss://ws-api.iexcloud.com/1.0/last?token={api_key}",
            }
            
            url = ws_urls.get(provider)
            if not url:
                logger.info(f"{provider.value} doesn't support WebSocket, using polling")
                asyncio.create_task(self._polling_fallback())
                return
            
            self.websocket = await websockets.connect(url)
            self.is_connected = True
            self.provider = provider
            logger.info(f"Connected to {provider.value} WebSocket for {self.ticker}")
            
            # Send subscription message based on provider
            await self._subscribe_to_ticker(provider, api_key)
            
            # Start listening for messages
            asyncio.create_task(self._listen_websocket())
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.is_connected = False
            asyncio.create_task(self._polling_fallback())
    
    async def _subscribe_to_ticker(self, provider: DataProvider, api_key: str):
        """Send subscription message to WebSocket"""
        try:
            if provider == DataProvider.POLYGON:
                # Polygon subscription format
                await self.websocket.send(json.dumps({
                    "action": "auth",
                    "params": api_key
                }))
                await asyncio.sleep(0.5)
                await self.websocket.send(json.dumps({
                    "action": "subscribe",
                    "params": f"T.{self.ticker}"  # Trade updates
                }))
                
            elif provider == DataProvider.FINNHUB:
                # Finnhub subscription format
                await self.websocket.send(json.dumps({
                    "type": "subscribe",
                    "symbol": self.ticker
                }))
                
            elif provider == DataProvider.IEX_CLOUD:
                # IEX Cloud subscription format
                await self.websocket.send(json.dumps({
                    "subscribe": [self.ticker]
                }))
                
            logger.info(f"Subscribed to {self.ticker} on {provider.value}")
            
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
    
    async def _listen_websocket(self):
        """Listen for WebSocket messages"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                
                # Normalize data based on provider
                normalized_data = await self._normalize_websocket_data(data)
                if normalized_data:
                    await self._process_realtime_data(normalized_data)
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.is_connected = False
            # Fallback to polling
            asyncio.create_task(self._polling_fallback())
    
    async def _normalize_websocket_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize WebSocket data from different providers to common format"""
        try:
            provider = getattr(self, 'provider', None)
            
            if provider == DataProvider.POLYGON:
                # Polygon format: {"ev":"T","sym":"AAPL","p":150.25,"s":100,"t":1234567890}
                if data.get("ev") == "T":  # Trade event
                    return {
                        "ticker": data.get("sym"),
                        "price": data.get("p"),
                        "volume": data.get("s"),
                        "timestamp": data.get("t"),
                        "source": "polygon"
                    }
                elif data.get("ev") == "status":
                    logger.debug(f"Polygon status: {data.get('message')}")
                    return None
                    
            elif provider == DataProvider.FINNHUB:
                # Finnhub format: {"data":[{"p":150.25,"s":"AAPL","t":1234567890,"v":100}],"type":"trade"}
                if data.get("type") == "trade" and data.get("data"):
                    trade = data["data"][0]
                    return {
                        "ticker": trade.get("s"),
                        "price": trade.get("p"),
                        "volume": trade.get("v"),
                        "timestamp": trade.get("t"),
                        "source": "finnhub"
                    }
                elif data.get("type") == "ping":
                    # Respond to ping
                    await self.websocket.send(json.dumps({"type": "pong"}))
                    return None
                    
            elif provider == DataProvider.IEX_CLOUD:
                # IEX Cloud format: {"symbol":"AAPL","price":150.25,"size":100,"time":1234567890}
                return {
                    "ticker": data.get("symbol"),
                    "price": data.get("price"),
                    "volume": data.get("size"),
                    "timestamp": data.get("time"),
                    "source": "iex_cloud"
                }
                
        except Exception as e:
            logger.error(f"Data normalization failed: {e}")
            
        return None
    
    async def _polling_fallback(self):
        """Fallback to polling if WebSocket fails"""
        logger.info(f"Starting polling fallback for {self.ticker}")
        
        while not self.is_connected:
            try:
                # Poll for price updates
                data = await self._fetch_latest_data()
                if data:
                    await self._process_realtime_data(data)
                
                # Wait before next poll (adjust based on requirements)
                await asyncio.sleep(5)  # 5 second intervals
                
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(10)
    
    async def _fetch_latest_data(self) -> Optional[Dict[str, Any]]:
        """Fetch latest data via HTTP from multiple providers"""
        providers = [
            self._fetch_from_alpha_vantage,
            self._fetch_from_finnhub,
            self._fetch_from_yfinance,
        ]
        
        for provider_func in providers:
            try:
                data = await provider_func()
                if data:
                    return data
            except Exception as e:
                logger.debug(f"Provider fetch failed: {e}")
                continue
        
        return None
    
    async def _fetch_from_alpha_vantage(self) -> Optional[Dict[str, Any]]:
        """Fetch from Alpha Vantage API"""
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            return None
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"https://www.alphavantage.co/query",
                    params={
                        "function": "GLOBAL_QUOTE",
                        "symbol": self.ticker,
                        "apikey": api_key
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    quote = data.get("Global Quote", {})
                    if quote:
                        return {
                            "ticker": self.ticker,
                            "price": float(quote.get("05. price", 0)),
                            "volume": int(quote.get("06. volume", 0)),
                            "timestamp": datetime.utcnow().timestamp(),
                            "source": "alpha_vantage"
                        }
        except Exception as e:
            logger.debug(f"Alpha Vantage fetch failed: {e}")
        
        return None
    
    async def _fetch_from_finnhub(self) -> Optional[Dict[str, Any]]:
        """Fetch from Finnhub API"""
        api_key = os.getenv("FINNHUB_API_KEY")
        if not api_key:
            return None
            
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"https://finnhub.io/api/v1/quote",
                    params={
                        "symbol": self.ticker,
                        "token": api_key
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "ticker": self.ticker,
                        "price": data.get("c"),  # current price
                        "volume": None,  # Finnhub quote doesn't include volume
                        "timestamp": data.get("t"),
                        "source": "finnhub"
                    }
        except Exception as e:
            logger.debug(f"Finnhub fetch failed: {e}")
        
        return None
    
    async def _fetch_from_yfinance(self) -> Optional[Dict[str, Any]]:
        """Fetch from Yahoo Finance (fallback)"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(self.ticker)
            info = ticker.history(period="1d", interval="1m")
            
            if not info.empty:
                latest = info.iloc[-1]
                return {
                    "ticker": self.ticker,
                    "price": float(latest["Close"]),
                    "volume": int(latest["Volume"]) if "Volume" in latest else None,
                    "timestamp": datetime.utcnow().timestamp(),
                    "source": "yahoo_finance"
                }
        except Exception as e:
            logger.debug(f"Yahoo Finance fetch failed: {e}")
        
        return None
    
    async def _process_realtime_data(self, data: Dict[str, Any]):
        """Process incoming real-time data"""
        
        # Extract price and volume
        current_price = data.get("price") or data.get("last")
        current_volume = data.get("volume")
        
        # Check for significant changes
        events = []
        
        if current_price and self.last_price:
            price_change = abs((current_price - self.last_price) / self.last_price)
            
            # Price change event (>1% move)
            if price_change > 0.01:
                events.append({
                    "type": MarketEvent.PRICE_UPDATE,
                    "ticker": self.ticker,
                    "price": current_price,
                    "previous_price": self.last_price,
                    "change_percent": price_change * 100,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        if current_volume and self.last_volume:
            volume_change = (current_volume - self.last_volume) / self.last_volume if self.last_volume > 0 else 0
            
            # Volume spike event (>50% increase)
            if volume_change > 0.5:
                events.append({
                    "type": MarketEvent.VOLUME_SPIKE,
                    "ticker": self.ticker,
                    "volume": current_volume,
                    "previous_volume": self.last_volume,
                    "change_percent": volume_change * 100,
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        # Update last values
        self.last_price = current_price
        self.last_volume = current_volume
        
        # Queue events for processing
        for event in events:
            await self.event_queue.put(event)
        
        # Notify subscribers
        for subscriber in self.subscribers:
            try:
                await subscriber(data)
            except Exception as e:
                logger.error(f"Subscriber notification failed: {e}")
    
    def subscribe(self, callback: Callable):
        """Subscribe to data updates"""
        self.subscribers.add(callback)
    
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from data updates"""
        self.subscribers.discard(callback)
    
    async def get_next_event(self) -> Dict[str, Any]:
        """Get next event from queue"""
        return await self.event_queue.get()


class EventDrivenAnalyzer:
    """
    Event-driven analysis system that triggers re-analysis based on market events
    """
    
    def __init__(self):
        self.triggers: List[EventTrigger] = []
        self.event_handlers: Dict[MarketEvent, List[Callable]] = {}
        self.active_streams: Dict[str, RealtimeDataStream] = {}
        self._setup_default_triggers()
    
    def _setup_default_triggers(self):
        """Setup default event triggers"""
        
        # Price movement trigger (>2% change)
        self.add_trigger(EventTrigger(
            MarketEvent.PRICE_UPDATE,
            lambda d: abs(d.get("change_percent", 0)) > 2.0,
            priority=7
        ))
        
        # Volume spike trigger (>100% increase)
        self.add_trigger(EventTrigger(
            MarketEvent.VOLUME_SPIKE,
            lambda d: d.get("volume_change_percent", 0) > 100,
            priority=6
        ))
        
        # News alert trigger
        self.add_trigger(EventTrigger(
            MarketEvent.NEWS_ALERT,
            lambda d: d.get("is_breaking", False) or "urgent" in d.get("title", "").lower(),
            priority=8
        ))
        
        # Earnings release trigger
        self.add_trigger(EventTrigger(
            MarketEvent.EARNINGS_RELEASE,
            lambda d: d.get("event_type") == "earnings",
            priority=9
        ))
    
    def add_trigger(self, trigger: EventTrigger):
        """Add an event trigger"""
        self.triggers.append(trigger)
        self.triggers.sort(key=lambda x: x.priority, reverse=True)
    
    def register_handler(self, event_type: MarketEvent, handler: Callable):
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def start_monitoring(self, ticker: str):
        """Start monitoring a ticker for events"""
        
        if ticker in self.active_streams:
            logger.info(f"Already monitoring {ticker}")
            return
        
        # Create data stream
        stream = RealtimeDataStream(ticker)
        self.active_streams[ticker] = stream
        
        # Try WebSocket first, fallback to polling
        ws_url = f"wss://stream.example.com/stocks/{ticker}"
        await stream.connect_websocket(ws_url)
        
        # Start event processing
        asyncio.create_task(self._process_events(ticker))
        
        logger.info(f"Started monitoring {ticker}")
    
    async def stop_monitoring(self, ticker: str):
        """Stop monitoring a ticker"""
        
        if ticker in self.active_streams:
            stream = self.active_streams[ticker]
            if stream.websocket:
                await stream.websocket.close()
            del self.active_streams[ticker]
            logger.info(f"Stopped monitoring {ticker}")
    
    async def _process_events(self, ticker: str):
        """Process events for a ticker"""
        
        stream = self.active_streams.get(ticker)
        if not stream:
            return
        
        while ticker in self.active_streams:
            try:
                # Get next event
                event = await asyncio.wait_for(
                    stream.get_next_event(),
                    timeout=60.0  # 1 minute timeout
                )
                
                # Check triggers
                triggered = []
                for trigger in self.triggers:
                    if trigger.check(event):
                        triggered.append(trigger)
                
                # Execute handlers for triggered events
                for trigger in triggered:
                    handlers = self.event_handlers.get(trigger.event_type, [])
                    for handler in handlers:
                        try:
                            await handler(event)
                        except Exception as e:
                            logger.error(f"Handler execution failed: {e}")
                
                # Log high-priority events
                if triggered and max(t.priority for t in triggered) >= 7:
                    logger.info(f"High-priority event for {ticker}: {event}")
                    
            except asyncio.TimeoutError:
                # No events in timeout period, continue
                continue
            except Exception as e:
                logger.error(f"Event processing error for {ticker}: {e}")
                await asyncio.sleep(5)


class MarketDataAggregator:
    """
    Aggregate market-wide data for context
    """
    
    def __init__(self):
        self.market_indicators = {}
        self.update_interval = 60  # seconds
        self.last_update = None
    
    async def update_market_context(self) -> Dict[str, Any]:
        """Update market-wide context data"""
        
        # Check if update needed
        if (self.last_update and 
            datetime.utcnow() - self.last_update < timedelta(seconds=self.update_interval)):
            return self.market_indicators
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Fetch VIX (volatility index)
                vix_response = await client.get("https://api.example.com/index/VIX")
                if vix_response.status_code == 200:
                    vix_data = vix_response.json()
                    self.market_indicators["vix"] = vix_data.get("value", 20)
                
                # Fetch S&P 500
                sp500_response = await client.get("https://api.example.com/index/SPX")
                if sp500_response.status_code == 200:
                    sp500_data = sp500_response.json()
                    self.market_indicators["sp500"] = sp500_data.get("value")
                    self.market_indicators["sp500_change"] = sp500_data.get("change_percent")
                
                # Determine market trend
                sp500_change = self.market_indicators.get("sp500_change", 0)
                if sp500_change > 1:
                    self.market_indicators["trend"] = "up"
                elif sp500_change < -1:
                    self.market_indicators["trend"] = "down"
                else:
                    self.market_indicators["trend"] = "neutral"
                
                # Market regime based on VIX
                vix = self.market_indicators.get("vix", 20)
                if vix < 15:
                    self.market_indicators["regime"] = "low_volatility"
                elif vix < 25:
                    self.market_indicators["regime"] = "normal"
                elif vix < 35:
                    self.market_indicators["regime"] = "elevated_volatility"
                else:
                    self.market_indicators["regime"] = "high_volatility"
                
                # Trading session
                now = datetime.utcnow()
                market_open = now.replace(hour=13, minute=30, second=0)  # 9:30 AM ET in UTC
                market_close = now.replace(hour=20, minute=0, second=0)  # 4:00 PM ET in UTC
                
                if market_open <= now <= market_close and now.weekday() < 5:
                    self.market_indicators["session"] = "regular"
                elif now < market_open:
                    self.market_indicators["session"] = "pre_market"
                elif now > market_close:
                    self.market_indicators["session"] = "after_hours"
                else:
                    self.market_indicators["session"] = "closed"
                
                self.last_update = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"Failed to update market context: {e}")
            # Use defaults if update fails
            if not self.market_indicators:
                self.market_indicators = {
                    "vix": 20,
                    "trend": "neutral",
                    "regime": "normal",
                    "session": "closed"
                }
        
        return self.market_indicators
    
    async def get_sector_performance(self) -> Dict[str, float]:
        """Get sector performance data"""
        
        sectors = {
            "XLK": "Technology",
            "XLF": "Financials",
            "XLV": "Healthcare",
            "XLE": "Energy",
            "XLY": "Consumer Discretionary",
            "XLP": "Consumer Staples",
            "XLI": "Industrials",
            "XLB": "Materials",
            "XLRE": "Real Estate",
            "XLU": "Utilities",
            "XLC": "Communication Services"
        }
        
        performance = {}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                tasks = []
                for etf, sector in sectors.items():
                    tasks.append(self._fetch_etf_performance(client, etf, sector))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, tuple):
                        sector, perf = result
                        performance[sector] = perf
                        
        except Exception as e:
            logger.error(f"Failed to fetch sector performance: {e}")
        
        return performance
    
    async def _fetch_etf_performance(
        self,
        client: httpx.AsyncClient,
        etf: str,
        sector: str
    ) -> Tuple[str, float]:
        """Fetch ETF performance"""
        
        try:
            response = await client.get(f"https://api.example.com/quote/{etf}")
            if response.status_code == 200:
                data = response.json()
                return sector, data.get("change_percent", 0.0)
        except Exception:
            pass
        
        return sector, 0.0


class IncrementalAnalysisEngine:
    """
    Perform incremental re-analysis based on events
    """
    
    def __init__(self, graph_executor: Callable):
        self.graph_executor = graph_executor
        self.event_analyzer = EventDrivenAnalyzer()
        self.market_aggregator = MarketDataAggregator()
        self.analysis_cache = {}
        self.last_full_analysis = {}
        
        # Register event handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register handlers for different event types"""
        
        self.event_analyzer.register_handler(
            MarketEvent.PRICE_UPDATE,
            self._handle_price_update
        )
        
        self.event_analyzer.register_handler(
            MarketEvent.VOLUME_SPIKE,
            self._handle_volume_spike
        )
        
        self.event_analyzer.register_handler(
            MarketEvent.NEWS_ALERT,
            self._handle_news_alert
        )
        
        self.event_analyzer.register_handler(
            MarketEvent.EARNINGS_RELEASE,
            self._handle_earnings_release
        )
    
    async def _handle_price_update(self, event: Dict[str, Any]):
        """Handle price update event"""
        
        ticker = event.get("ticker")
        change_percent = event.get("change_percent", 0)
        
        logger.info(f"Price update for {ticker}: {change_percent:.2f}%")
        
        # Trigger re-analysis of technical indicators
        await self._incremental_analysis(ticker, ["technicals", "valuation"])
    
    async def _handle_volume_spike(self, event: Dict[str, Any]):
        """Handle volume spike event"""
        
        ticker = event.get("ticker")
        volume_change = event.get("change_percent", 0)
        
        logger.info(f"Volume spike for {ticker}: {volume_change:.2f}%")
        
        # Trigger re-analysis of technicals and sentiment
        await self._incremental_analysis(ticker, ["technicals", "news_sentiment"])
    
    async def _handle_news_alert(self, event: Dict[str, Any]):
        """Handle news alert event"""
        
        ticker = event.get("ticker")
        
        logger.info(f"News alert for {ticker}")
        
        # Trigger re-analysis of sentiment
        await self._incremental_analysis(ticker, ["news_sentiment"])
    
    async def _handle_earnings_release(self, event: Dict[str, Any]):
        """Handle earnings release event"""
        
        ticker = event.get("ticker")
        
        logger.info(f"Earnings release for {ticker}")
        
        # Trigger full re-analysis
        await self._full_analysis(ticker)
    
    async def _incremental_analysis(self, ticker: str, nodes: List[str]):
        """Perform incremental analysis on specific nodes"""
        
        logger.info(f"Incremental analysis for {ticker}: {nodes}")
        
        # Get last full analysis
        last_state = self.last_full_analysis.get(ticker)
        if not last_state:
            # No previous analysis, do full analysis
            await self._full_analysis(ticker)
            return
        
        # Update market context
        market_context = await self.market_aggregator.update_market_context()
        
        # Create partial state for incremental update
        partial_state = {
            "tickers": [ticker],
            "market_context": market_context,
            "analysis": last_state.get("analysis", {}),
            "confidences": last_state.get("confidences", {})
        }
        
        # Execute only specified nodes
        # This would require modifying the graph to support partial execution
        # For now, we'll simulate it
        logger.info(f"Would execute nodes: {nodes} for {ticker}")
        
        # Cache the incremental update
        self.analysis_cache[ticker] = {
            "timestamp": datetime.utcnow(),
            "nodes_updated": nodes,
            "state": partial_state
        }
    
    async def _full_analysis(self, ticker: str):
        """Perform full analysis"""
        
        logger.info(f"Full analysis triggered for {ticker}")
        
        # Update market context
        market_context = await self.market_aggregator.update_market_context()
        
        # Execute full graph
        state = {
            "tickers": [ticker],
            "market_context": market_context
        }
        
        # This would call the actual graph executor
        # result = await self.graph_executor(state)
        
        # Cache the result
        self.last_full_analysis[ticker] = state
        self.analysis_cache[ticker] = {
            "timestamp": datetime.utcnow(),
            "nodes_updated": "all",
            "state": state
        }
    
    async def start_realtime_monitoring(self, tickers: List[str]):
        """Start real-time monitoring for multiple tickers"""
        
        for ticker in tickers:
            await self.event_analyzer.start_monitoring(ticker)
        
        # Start market context updates
        asyncio.create_task(self._update_market_context_loop())
    
    async def _update_market_context_loop(self):
        """Continuously update market context"""
        
        while True:
            try:
                await self.market_aggregator.update_market_context()
                await asyncio.sleep(60)  # Update every minute
            except Exception as e:
                logger.error(f"Market context update failed: {e}")
                await asyncio.sleep(60)
