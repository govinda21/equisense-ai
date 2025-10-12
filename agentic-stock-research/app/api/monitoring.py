"""
API endpoints for monitoring and alert system
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from app.monitoring.alert_engine import (
    get_alert_manager, AlertRule, EventType, AlertSeverity, MarketEvent
)
from app.monitoring.notification_service import (
    get_notification_service, NotificationPreference, NotificationChannel
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


# Pydantic models for API requests/responses
class AlertRuleCreate(BaseModel):
    user_id: str
    tickers: List[str]
    event_types: List[str]  # Will be converted to EventType enum
    conditions: Dict[str, Any] = Field(default_factory=dict)
    severity_threshold: str = "medium"  # Will be converted to AlertSeverity
    enabled: bool = True


class AlertRuleResponse(BaseModel):
    rule_id: str
    user_id: str
    tickers: List[str]
    event_types: List[str]
    conditions: Dict[str, Any]
    severity_threshold: str
    enabled: bool
    created_at: datetime


class NotificationPreferenceCreate(BaseModel):
    user_id: str
    channels: List[str]  # Will be converted to NotificationChannel enum
    email: Optional[str] = None
    phone: Optional[str] = None
    webhook_url: Optional[str] = None
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    enabled: bool = True


class NotificationPreferenceResponse(BaseModel):
    user_id: str
    channels: List[str]
    email: Optional[str] = None
    phone: Optional[str] = None
    webhook_url: Optional[str] = None
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    enabled: bool


class MarketEventResponse(BaseModel):
    event_type: str
    ticker: str
    timestamp: datetime
    severity: str
    title: str
    description: str
    data: Dict[str, Any]
    confidence: float
    source: str


class TestNotificationRequest(BaseModel):
    user_id: str
    channel: str


@router.get("/health")
async def health_check():
    """Health check for monitoring system"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "alert_engine": "active",
            "notification_service": "active"
        }
    }


@router.post("/alert-rules", response_model=AlertRuleResponse)
async def create_alert_rule(rule_data: AlertRuleCreate):
    """Create a new alert rule"""
    try:
        alert_manager = await get_alert_manager()
        
        # Convert string enums to actual enums
        event_types = [EventType(event_type) for event_type in rule_data.event_types]
        severity_threshold = AlertSeverity(rule_data.severity_threshold)
        
        # Create alert rule
        rule = AlertRule(
            rule_id=f"rule_{datetime.now().timestamp()}",
            user_id=rule_data.user_id,
            tickers=rule_data.tickers,
            event_types=event_types,
            conditions=rule_data.conditions,
            severity_threshold=severity_threshold,
            enabled=rule_data.enabled
        )
        
        await alert_manager.add_alert_rule(rule)
        
        return AlertRuleResponse(
            rule_id=rule.rule_id,
            user_id=rule.user_id,
            tickers=rule.tickers,
            event_types=[et.value for et in rule.event_types],
            conditions=rule.conditions,
            severity_threshold=rule.severity_threshold.value,
            enabled=rule.enabled,
            created_at=rule.created_at
        )
        
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alert-rules/{user_id}", response_model=List[AlertRuleResponse])
async def get_user_alert_rules(user_id: str):
    """Get all alert rules for a user"""
    try:
        alert_manager = await get_alert_manager()
        rules = await alert_manager.get_user_alerts(user_id)
        
        return [
            AlertRuleResponse(
                rule_id=rule.rule_id,
                user_id=rule.user_id,
                tickers=rule.tickers,
                event_types=[et.value for et in rule.event_types],
                conditions=rule.conditions,
                severity_threshold=rule.severity_threshold.value,
                enabled=rule.enabled,
                created_at=rule.created_at
            )
            for rule in rules
        ]
        
    except Exception as e:
        logger.error(f"Error getting alert rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alert-rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """Delete an alert rule"""
    try:
        alert_manager = await get_alert_manager()
        success = await alert_manager.remove_alert_rule(rule_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert rule not found")
            
        return {"message": "Alert rule deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notification-preferences", response_model=NotificationPreferenceResponse)
async def create_notification_preference(pref_data: NotificationPreferenceCreate):
    """Create or update notification preferences"""
    try:
        notification_service = get_notification_service()
        
        # Convert string channels to enum
        channels = [NotificationChannel(channel) for channel in pref_data.channels]
        
        preference = NotificationPreference(
            user_id=pref_data.user_id,
            channels=channels,
            email=pref_data.email,
            phone=pref_data.phone,
            webhook_url=pref_data.webhook_url,
            slack_webhook=pref_data.slack_webhook,
            discord_webhook=pref_data.discord_webhook,
            quiet_hours_start=pref_data.quiet_hours_start,
            quiet_hours_end=pref_data.quiet_hours_end,
            enabled=pref_data.enabled
        )
        
        notification_service.add_user_preference(preference)
        
        return NotificationPreferenceResponse(
            user_id=preference.user_id,
            channels=[ch.value for ch in preference.channels],
            email=preference.email,
            phone=preference.phone,
            webhook_url=preference.webhook_url,
            slack_webhook=preference.slack_webhook,
            discord_webhook=preference.discord_webhook,
            quiet_hours_start=preference.quiet_hours_start,
            quiet_hours_end=preference.quiet_hours_end,
            enabled=preference.enabled
        )
        
    except Exception as e:
        logger.error(f"Error creating notification preference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notification-preferences/{user_id}", response_model=Optional[NotificationPreferenceResponse])
async def get_notification_preferences(user_id: str):
    """Get notification preferences for a user"""
    try:
        notification_service = get_notification_service()
        preference = notification_service.get_user_preference(user_id)
        
        if not preference:
            return None
            
        return NotificationPreferenceResponse(
            user_id=preference.user_id,
            channels=[ch.value for ch in preference.channels],
            email=preference.email,
            phone=preference.phone,
            webhook_url=preference.webhook_url,
            slack_webhook=preference.slack_webhook,
            discord_webhook=preference.discord_webhook,
            quiet_hours_start=preference.quiet_hours_start,
            quiet_hours_end=preference.quiet_hours_end,
            enabled=preference.enabled
        )
        
    except Exception as e:
        logger.error(f"Error getting notification preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/notification-preferences/{user_id}")
async def delete_notification_preferences(user_id: str):
    """Delete notification preferences for a user"""
    try:
        notification_service = get_notification_service()
        success = notification_service.remove_user_preference(user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Notification preferences not found")
            
        return {"message": "Notification preferences deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-notification")
async def send_test_notification(request: TestNotificationRequest):
    """Send a test notification to verify settings"""
    try:
        notification_service = get_notification_service()
        channel = NotificationChannel(request.channel)
        
        success = await notification_service.send_test_notification(request.user_id, channel)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to send test notification")
            
        return {"message": "Test notification sent successfully"}
        
    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/{ticker}", response_model=List[MarketEventResponse])
async def monitor_ticker(ticker: str, background_tasks: BackgroundTasks):
    """Monitor a ticker and return detected events"""
    try:
        alert_manager = await get_alert_manager()
        events = await alert_manager.monitor_ticker(ticker)
        
        return [
            MarketEventResponse(
                event_type=event.event_type.value,
                ticker=event.ticker,
                timestamp=event.timestamp,
                severity=event.severity.value,
                title=event.title,
                description=event.description,
                data=event.data,
                confidence=event.confidence,
                source=event.source
            )
            for event in events
        ]
        
    except Exception as e:
        logger.error(f"Error monitoring ticker {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/event-types")
async def get_event_types():
    """Get all available event types"""
    return {
        "event_types": [
            {
                "value": event_type.value,
                "name": event_type.value.replace("_", " ").title(),
                "description": _get_event_type_description(event_type)
            }
            for event_type in EventType
        ]
    }


@router.get("/severity-levels")
async def get_severity_levels():
    """Get all available severity levels"""
    return {
        "severity_levels": [
            {
                "value": severity.value,
                "name": severity.value.title(),
                "description": _get_severity_description(severity)
            }
            for severity in AlertSeverity
        ]
    }


@router.get("/notification-channels")
async def get_notification_channels():
    """Get all available notification channels"""
    return {
        "notification_channels": [
            {
                "value": channel.value,
                "name": channel.value.title(),
                "description": _get_channel_description(channel)
            }
            for channel in NotificationChannel
        ]
    }


def _get_event_type_description(event_type: EventType) -> str:
    """Get description for event type"""
    descriptions = {
        EventType.PRICE_SPIKE: "Significant price increase (>5%)",
        EventType.PRICE_DROP: "Significant price decrease (<-5%)",
        EventType.VOLUME_SURGE: "Unusual trading volume increase (>200%)",
        EventType.TECHNICAL_BREAKOUT: "Price breaks key technical levels",
        EventType.TECHNICAL_REVERSAL: "Technical indicators suggest reversal",
        EventType.NEW_FILING: "New regulatory filing published",
        EventType.INSIDER_BUY: "Significant insider buying activity",
        EventType.INSIDER_SELL: "Significant insider selling activity",
        EventType.EARNINGS_ANNOUNCEMENT: "Earnings announcement released",
        EventType.ANALYST_UPGRADE: "Analyst rating upgrade",
        EventType.ANALYST_DOWNGRADE: "Analyst rating downgrade",
        EventType.NEWS_SENTIMENT_SHIFT: "Major shift in news sentiment",
        EventType.SECTOR_ROTATION: "Sector-wide market movement"
    }
    return descriptions.get(event_type, "Market event detected")


def _get_severity_description(severity: AlertSeverity) -> str:
    """Get description for severity level"""
    descriptions = {
        AlertSeverity.LOW: "Minor event, informational only",
        AlertSeverity.MEDIUM: "Moderate event, worth monitoring",
        AlertSeverity.HIGH: "Important event, consider action",
        AlertSeverity.CRITICAL: "Urgent event, immediate attention required"
    }
    return descriptions.get(severity, "Event severity level")


def _get_channel_description(channel: NotificationChannel) -> str:
    """Get description for notification channel"""
    descriptions = {
        NotificationChannel.EMAIL: "Email notifications",
        NotificationChannel.SMS: "SMS text messages",
        NotificationChannel.PUSH: "Push notifications",
        NotificationChannel.WEBHOOK: "Custom webhook endpoint",
        NotificationChannel.SLACK: "Slack channel notifications",
        NotificationChannel.DISCORD: "Discord channel notifications"
    }
    return descriptions.get(channel, "Notification channel")
