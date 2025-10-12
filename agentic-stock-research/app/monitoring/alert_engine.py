"""
Real-time monitoring and alert engine for EquiSense AI
Detects market events and triggers intelligent alerts
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import yfinance as yf
import aiohttp
from bs4 import BeautifulSoup

from app.cache.redis_cache import get_cache_manager
from app.tools.llm_orchestrator import get_llm_orchestrator, TaskType, TaskComplexity

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of market events that can trigger alerts"""
    PRICE_SPIKE = "price_spike"  # >5% price movement
    PRICE_DROP = "price_drop"    # <-5% price movement
    VOLUME_SURGE = "volume_surge"  # >200% volume increase
    TECHNICAL_BREAKOUT = "technical_breakout"  # Key resistance/support break
    TECHNICAL_REVERSAL = "technical_reversal"  # RSI oversold/overbought reversal
    NEW_FILING = "new_filing"    # New SEC/BSE/NSE filing
    INSIDER_BUY = "insider_buy"  # Significant insider buying
    INSIDER_SELL = "insider_sell"  # Significant insider selling
    EARNINGS_ANNOUNCEMENT = "earnings_announcement"  # Earnings release
    ANALYST_UPGRADE = "analyst_upgrade"  # Rating upgrade
    ANALYST_DOWNGRADE = "analyst_downgrade"  # Rating downgrade
    NEWS_SENTIMENT_SHIFT = "news_sentiment_shift"  # Major sentiment change
    SECTOR_ROTATION = "sector_rotation"  # Sector-wide movement


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MarketEvent:
    """Represents a detected market event"""
    event_type: EventType
    ticker: str
    timestamp: datetime
    severity: AlertSeverity
    title: str
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    source: str = "equisense_ai"


@dataclass
class AlertRule:
    """User-defined alert rule"""
    rule_id: str
    user_id: str
    tickers: List[str]
    event_types: List[EventType]
    conditions: Dict[str, Any]
    severity_threshold: AlertSeverity
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)


class EventDetector:
    """Detects market events from various data sources"""
    
    def __init__(self):
        self.cache = None
        self.llm_orchestrator = None
        
    async def initialize(self):
        """Initialize dependencies"""
        try:
            self.cache = await get_cache_manager()
            self.llm_orchestrator = get_llm_orchestrator()
        except Exception as e:
            logger.warning(f"Failed to initialize EventDetector dependencies: {e}")
    
    async def detect_events(self, ticker: str) -> List[MarketEvent]:
        """Detect all events for a given ticker"""
        events = []
        
        try:
            # Run all detection methods in parallel
            detection_tasks = [
                self._detect_price_events(ticker),
                self._detect_volume_events(ticker),
                self._detect_technical_events(ticker),
                self._detect_filing_events(ticker),
                self._detect_insider_events(ticker),
                self._detect_analyst_events(ticker),
                self._detect_news_events(ticker)
            ]
            
            results = await asyncio.gather(*detection_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    events.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Event detection error: {result}")
                    
        except Exception as e:
            logger.error(f"Error detecting events for {ticker}: {e}")
            
        return events
    
    async def _detect_price_events(self, ticker: str) -> List[MarketEvent]:
        """Detect price-based events"""
        events = []
        
        try:
            # Get recent price data
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d", interval="1d")
            
            if len(hist) < 2:
                return events
                
            current_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            price_change_pct = (current_price - prev_price) / prev_price
            
            # Check for significant price movements
            if price_change_pct > 0.05:  # >5% increase
                events.append(MarketEvent(
                    event_type=EventType.PRICE_SPIKE,
                    ticker=ticker,
                    timestamp=datetime.now(),
                    severity=AlertSeverity.HIGH if price_change_pct > 0.10 else AlertSeverity.MEDIUM,
                    title=f"{ticker} Price Spike: +{price_change_pct:.1%}",
                    description=f"Significant price increase of {price_change_pct:.1%} detected",
                    data={
                        "current_price": float(current_price),
                        "previous_price": float(prev_price),
                        "price_change_pct": float(price_change_pct)
                    }
                ))
            elif price_change_pct < -0.05:  # <-5% decrease
                events.append(MarketEvent(
                    event_type=EventType.PRICE_DROP,
                    ticker=ticker,
                    timestamp=datetime.now(),
                    severity=AlertSeverity.HIGH if price_change_pct < -0.10 else AlertSeverity.MEDIUM,
                    title=f"{ticker} Price Drop: {price_change_pct:.1%}",
                    description=f"Significant price decrease of {price_change_pct:.1%} detected",
                    data={
                        "current_price": float(current_price),
                        "previous_price": float(prev_price),
                        "price_change_pct": float(price_change_pct)
                    }
                ))
                
        except Exception as e:
            logger.error(f"Error detecting price events for {ticker}: {e}")
            
        return events
    
    async def _detect_volume_events(self, ticker: str) -> List[MarketEvent]:
        """Detect volume-based events"""
        events = []
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="10d", interval="1d")
            
            if len(hist) < 5:
                return events
                
            current_volume = hist['Volume'].iloc[-1]
            avg_volume = hist['Volume'].iloc[:-1].mean()
            
            if avg_volume > 0:
                volume_ratio = current_volume / avg_volume
                
                if volume_ratio > 2.0:  # >200% of average volume
                    events.append(MarketEvent(
                        event_type=EventType.VOLUME_SURGE,
                        ticker=ticker,
                        timestamp=datetime.now(),
                        severity=AlertSeverity.MEDIUM,
                        title=f"{ticker} Volume Surge: {volume_ratio:.1f}x Average",
                        description=f"Trading volume {volume_ratio:.1f}x higher than 10-day average",
                        data={
                            "current_volume": int(current_volume),
                            "average_volume": int(avg_volume),
                            "volume_ratio": float(volume_ratio)
                        }
                    ))
                    
        except Exception as e:
            logger.error(f"Error detecting volume events for {ticker}: {e}")
            
        return events
    
    async def _detect_technical_events(self, ticker: str) -> List[MarketEvent]:
        """Detect technical analysis events"""
        events = []
        
        try:
            # Get technical indicators (simplified)
            stock = yf.Ticker(ticker)
            hist = stock.history(period="30d", interval="1d")
            
            if len(hist) < 20:
                return events
                
            # Calculate RSI (simplified)
            prices = hist['Close']
            deltas = prices.diff()
            gains = deltas.where(deltas > 0, 0)
            losses = -deltas.where(deltas < 0, 0)
            
            avg_gain = gains.rolling(window=14).mean().iloc[-1]
            avg_loss = losses.rolling(window=14).mean().iloc[-1]
            
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
                
                # Check for oversold/overbought conditions
                if rsi < 30:
                    events.append(MarketEvent(
                        event_type=EventType.TECHNICAL_REVERSAL,
                        ticker=ticker,
                        timestamp=datetime.now(),
                        severity=AlertSeverity.MEDIUM,
                        title=f"{ticker} Oversold Condition: RSI {rsi:.1f}",
                        description=f"RSI indicates oversold condition, potential reversal opportunity",
                        data={"rsi": float(rsi), "condition": "oversold"}
                    ))
                elif rsi > 70:
                    events.append(MarketEvent(
                        event_type=EventType.TECHNICAL_REVERSAL,
                        ticker=ticker,
                        timestamp=datetime.now(),
                        severity=AlertSeverity.MEDIUM,
                        title=f"{ticker} Overbought Condition: RSI {rsi:.1f}",
                        description=f"RSI indicates overbought condition, potential reversal risk",
                        data={"rsi": float(rsi), "condition": "overbought"}
                    ))
                    
        except Exception as e:
            logger.error(f"Error detecting technical events for {ticker}: {e}")
            
        return events
    
    async def _detect_filing_events(self, ticker: str) -> List[MarketEvent]:
        """Detect new regulatory filings"""
        events = []
        
        try:
            # Check cache for recent filings
            cache_key = f"filings:{ticker}:recent"
            if self.cache:
                recent_filings = await self.cache.get(cache_key)
                if recent_filings:
                    # Check if any new filings in last 24 hours
                    for filing in recent_filings:
                        filing_date = datetime.fromisoformat(filing.get('filing_date', ''))
                        if datetime.now() - filing_date < timedelta(hours=24):
                            events.append(MarketEvent(
                                event_type=EventType.NEW_FILING,
                                ticker=ticker,
                                timestamp=datetime.now(),
                                severity=AlertSeverity.MEDIUM,
                                title=f"{ticker} New Filing: {filing.get('type', 'Unknown')}",
                                description=f"New regulatory filing detected: {filing.get('type', 'Unknown')}",
                                data=filing
                            ))
                            
        except Exception as e:
            logger.error(f"Error detecting filing events for {ticker}: {e}")
            
        return events
    
    async def _detect_insider_events(self, ticker: str) -> List[MarketEvent]:
        """Detect insider trading events"""
        events = []
        
        try:
            # Check cache for recent insider transactions
            cache_key = f"insider:{ticker}:recent"
            if self.cache:
                recent_transactions = await self.cache.get(cache_key)
                if recent_transactions:
                    for transaction in recent_transactions:
                        transaction_date = datetime.fromisoformat(transaction.get('date', ''))
                        if datetime.now() - transaction_date < timedelta(days=7):
                            transaction_type = transaction.get('type', '').lower()
                            amount = transaction.get('amount', 0)
                            
                            if 'buy' in transaction_type and amount > 100000:  # >$100k buy
                                events.append(MarketEvent(
                                    event_type=EventType.INSIDER_BUY,
                                    ticker=ticker,
                                    timestamp=datetime.now(),
                                    severity=AlertSeverity.HIGH,
                                    title=f"{ticker} Significant Insider Buying",
                                    description=f"Insider purchased ${amount:,.0f} worth of shares",
                                    data=transaction
                                ))
                            elif 'sell' in transaction_type and amount > 100000:  # >$100k sell
                                events.append(MarketEvent(
                                    event_type=EventType.INSIDER_SELL,
                                    ticker=ticker,
                                    timestamp=datetime.now(),
                                    severity=AlertSeverity.MEDIUM,
                                    title=f"{ticker} Significant Insider Selling",
                                    description=f"Insider sold ${amount:,.0f} worth of shares",
                                    data=transaction
                                ))
                                
        except Exception as e:
            logger.error(f"Error detecting insider events for {ticker}: {e}")
            
        return events
    
    async def _detect_analyst_events(self, ticker: str) -> List[MarketEvent]:
        """Detect analyst rating changes"""
        events = []
        
        try:
            # Check for recent analyst recommendations
            stock = yf.Ticker(ticker)
            recommendations = stock.recommendations
            
            if recommendations is not None and len(recommendations) > 0:
                latest_rec = recommendations.iloc[-1]
                rec_date = latest_rec.name
                
                # Check if recommendation is recent (last 7 days)
                if datetime.now() - rec_date < timedelta(days=7):
                    firm = latest_rec.get('Firm', 'Unknown')
                    to_grade = latest_rec.get('To Grade', 'Unknown')
                    from_grade = latest_rec.get('From Grade', 'Unknown')
                    
                    # Determine if it's an upgrade or downgrade
                    if to_grade and from_grade:
                        grade_order = ['Sell', 'Underperform', 'Hold', 'Outperform', 'Buy', 'Strong Buy']
                        try:
                            to_index = grade_order.index(to_grade)
                            from_index = grade_order.index(from_grade)
                            
                            if to_index > from_index:
                                events.append(MarketEvent(
                                    event_type=EventType.ANALYST_UPGRADE,
                                    ticker=ticker,
                                    timestamp=datetime.now(),
                                    severity=AlertSeverity.MEDIUM,
                                    title=f"{ticker} Analyst Upgrade: {from_grade} → {to_grade}",
                                    description=f"{firm} upgraded {ticker} from {from_grade} to {to_grade}",
                                    data={
                                        "firm": firm,
                                        "from_grade": from_grade,
                                        "to_grade": to_grade,
                                        "date": rec_date.isoformat()
                                    }
                                ))
                            elif to_index < from_index:
                                events.append(MarketEvent(
                                    event_type=EventType.ANALYST_DOWNGRADE,
                                    ticker=ticker,
                                    timestamp=datetime.now(),
                                    severity=AlertSeverity.MEDIUM,
                                    title=f"{ticker} Analyst Downgrade: {from_grade} → {to_grade}",
                                    description=f"{firm} downgraded {ticker} from {from_grade} to {to_grade}",
                                    data={
                                        "firm": firm,
                                        "from_grade": from_grade,
                                        "to_grade": to_grade,
                                        "date": rec_date.isoformat()
                                    }
                                ))
                        except ValueError:
                            pass  # Grade not in our list
                            
        except Exception as e:
            logger.error(f"Error detecting analyst events for {ticker}: {e}")
            
        return events
    
    async def _detect_news_events(self, ticker: str) -> List[MarketEvent]:
        """Detect news sentiment shifts"""
        events = []
        
        try:
            # Check cache for recent news sentiment
            cache_key = f"news_sentiment:{ticker}:recent"
            if self.cache:
                sentiment_data = await self.cache.get(cache_key)
                if sentiment_data:
                    current_sentiment = sentiment_data.get('score', 0)
                    previous_sentiment = sentiment_data.get('previous_score', 0)
                    
                    # Check for significant sentiment shift
                    sentiment_change = abs(current_sentiment - previous_sentiment)
                    if sentiment_change > 0.3:  # Significant shift
                        direction = "positive" if current_sentiment > previous_sentiment else "negative"
                        events.append(MarketEvent(
                            event_type=EventType.NEWS_SENTIMENT_SHIFT,
                            ticker=ticker,
                            timestamp=datetime.now(),
                            severity=AlertSeverity.MEDIUM,
                            title=f"{ticker} News Sentiment Shift: {direction.title()}",
                            description=f"Significant {direction} shift in news sentiment detected",
                            data={
                                "current_sentiment": current_sentiment,
                                "previous_sentiment": previous_sentiment,
                                "change": sentiment_change,
                                "direction": direction
                            }
                        ))
                        
        except Exception as e:
            logger.error(f"Error detecting news events for {ticker}: {e}")
            
        return events


class AlertRulesEngine:
    """Manages user-defined alert rules and triggers"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        
    def add_rule(self, rule: AlertRule) -> None:
        """Add a new alert rule"""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added alert rule {rule.rule_id} for user {rule.user_id}")
        
    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed alert rule {rule_id}")
            return True
        return False
        
    def get_user_rules(self, user_id: str) -> List[AlertRule]:
        """Get all rules for a user"""
        return [rule for rule in self.rules.values() if rule.user_id == user_id]
        
    def should_trigger_alert(self, event: MarketEvent, rule: AlertRule) -> bool:
        """Check if an event should trigger an alert based on rule conditions"""
        if not rule.enabled:
            return False
            
        if event.ticker not in rule.tickers:
            return False
            
        if event.event_type not in rule.event_types:
            return False
            
        # Check severity threshold
        severity_order = [AlertSeverity.LOW, AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        event_severity_index = severity_order.index(event.severity)
        rule_severity_index = severity_order.index(rule.severity_threshold)
        
        if event_severity_index < rule_severity_index:
            return False
            
        # Check custom conditions
        for condition_key, condition_value in rule.conditions.items():
            if condition_key in event.data:
                event_value = event.data[condition_key]
                if isinstance(condition_value, dict):
                    # Range condition
                    if 'min' in condition_value and event_value < condition_value['min']:
                        return False
                    if 'max' in condition_value and event_value > condition_value['max']:
                        return False
                elif event_value != condition_value:
                    return False
                    
        return True


class AlertManager:
    """Main alert management system"""
    
    def __init__(self):
        self.event_detector = EventDetector()
        self.rules_engine = AlertRulesEngine()
        self.notification_service = None  # Will be set by notification service
        
    async def initialize(self):
        """Initialize the alert manager"""
        await self.event_detector.initialize()
        logger.info("AlertManager initialized")
        
    async def monitor_ticker(self, ticker: str) -> List[MarketEvent]:
        """Monitor a ticker and return detected events"""
        events = await self.event_detector.detect_events(ticker)
        
        # Check which rules should trigger alerts
        triggered_alerts = []
        for rule in self.rules_engine.rules.values():
            for event in events:
                if self.rules_engine.should_trigger_alert(event, rule):
                    triggered_alerts.append({
                        "rule": rule,
                        "event": event
                    })
                    
        # Send notifications for triggered alerts
        if triggered_alerts and self.notification_service:
            await self.notification_service.send_alerts(triggered_alerts)
            
        return events
        
    async def add_alert_rule(self, rule: AlertRule) -> None:
        """Add a new alert rule"""
        self.rules_engine.add_rule(rule)
        
    async def remove_alert_rule(self, rule_id: str) -> bool:
        """Remove an alert rule"""
        return self.rules_engine.remove_rule(rule_id)
        
    async def get_user_alerts(self, user_id: str) -> List[AlertRule]:
        """Get all alert rules for a user"""
        return self.rules_engine.get_user_rules(user_id)


# Global alert manager instance
_alert_manager = None

async def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
        await _alert_manager.initialize()
    return _alert_manager
