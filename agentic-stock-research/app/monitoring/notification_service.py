"""
Multi-channel notification service for EquiSense AI alerts
Supports email, SMS, push notifications, and webhooks
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import aiohttp
try:
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    logger.warning("Email libraries not available. Email notifications will be disabled.")

from app.monitoring.alert_engine import MarketEvent, AlertRule

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Supported notification channels"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"


@dataclass
class NotificationPreference:
    """User notification preferences"""
    user_id: str
    channels: List[NotificationChannel]
    email: Optional[str] = None
    phone: Optional[str] = None
    webhook_url: Optional[str] = None
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None
    quiet_hours_start: Optional[int] = None  # Hour of day (0-23)
    quiet_hours_end: Optional[int] = None
    enabled: bool = True


@dataclass
class NotificationMessage:
    """Notification message to be sent"""
    user_id: str
    channel: NotificationChannel
    title: str
    message: str
    severity: str
    data: Dict[str, Any]
    timestamp: datetime


class EmailNotifier:
    """Email notification handler"""
    
    def __init__(self, smtp_server: str = "localhost", smtp_port: int = 587, 
                 username: str = None, password: str = None):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        
    async def send_notification(self, message: NotificationMessage, recipient: str) -> bool:
        """Send email notification"""
        if not EMAIL_AVAILABLE:
            logger.warning("Email functionality not available")
            return False
            
        try:
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🚨 EquiSense Alert: {message.title}"
            msg['From'] = "alerts@equisense.ai"
            msg['To'] = recipient
            
            # Create HTML email body
            html_body = self._create_email_html(message)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.username and self.password:
                    server.starttls()
                    server.login(self.username, self.password)
                server.send_message(msg)
                
            logger.info(f"Email notification sent to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
            
    def _create_email_html(self, message: NotificationMessage) -> str:
        """Create HTML email body"""
        severity_colors = {
            "low": "#28a745",
            "medium": "#ffc107", 
            "high": "#fd7e14",
            "critical": "#dc3545"
        }
        
        color = severity_colors.get(message.severity.lower(), "#6c757d")
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f8f9fa; padding: 20px; border-radius: 0 0 8px 8px; }}
                .severity {{ display: inline-block; padding: 4px 8px; border-radius: 4px; color: white; background-color: {color}; }}
                .data-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                .data-table th, .data-table td {{ border: 1px solid #dee2e6; padding: 8px; text-align: left; }}
                .data-table th {{ background-color: #e9ecef; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🚨 EquiSense AI Alert</h2>
                <span class="severity">{message.severity.upper()}</span>
            </div>
            <div class="content">
                <h3>{message.title}</h3>
                <p>{message.message}</p>
                <p><strong>Time:</strong> {message.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                
                {self._format_data_table(message.data) if message.data else ''}
                
                <hr>
                <p style="font-size: 12px; color: #6c757d;">
                    This alert was generated by EquiSense AI. 
                    <a href="https://equisense.ai">Manage your alerts</a>
                </p>
            </div>
        </body>
        </html>
        """
        
    def _format_data_table(self, data: Dict[str, Any]) -> str:
        """Format data as HTML table"""
        if not data:
            return ""
            
        rows = ""
        for key, value in data.items():
            rows += f"<tr><td><strong>{key.replace('_', ' ').title()}</strong></td><td>{value}</td></tr>"
            
        return f"""
        <table class="data-table">
            <thead>
                <tr><th>Metric</th><th>Value</th></tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """


class SMSNotifier:
    """SMS notification handler (placeholder for Twilio integration)"""
    
    def __init__(self, twilio_account_sid: str = None, twilio_auth_token: str = None):
        self.twilio_account_sid = twilio_account_sid
        self.twilio_auth_token = twilio_auth_token
        
    async def send_notification(self, message: NotificationMessage, recipient: str) -> bool:
        """Send SMS notification"""
        try:
            # Placeholder for Twilio integration
            # In production, use Twilio API
            logger.info(f"SMS notification would be sent to {recipient}: {message.title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {e}")
            return False


class WebhookNotifier:
    """Webhook notification handler"""
    
    async def send_notification(self, message: NotificationMessage, webhook_url: str) -> bool:
        """Send webhook notification"""
        try:
            payload = {
                "title": message.title,
                "message": message.message,
                "severity": message.severity,
                "timestamp": message.timestamp.isoformat(),
                "data": message.data,
                "source": "equisense_ai"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Webhook notification sent to {webhook_url}")
                        return True
                    else:
                        logger.error(f"Webhook notification failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False


class SlackNotifier:
    """Slack notification handler"""
    
    async def send_notification(self, message: NotificationMessage, webhook_url: str) -> bool:
        """Send Slack notification"""
        try:
            severity_emoji = {
                "low": ":information_source:",
                "medium": ":warning:",
                "high": ":exclamation:",
                "critical": ":rotating_light:"
            }
            
            emoji = severity_emoji.get(message.severity.lower(), ":bell:")
            
            # Create Slack message blocks
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} EquiSense AI Alert"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{message.title}*\n{message.message}"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Severity: {message.severity.upper()} | Time: {message.timestamp.strftime('%H:%M:%S UTC')}"
                        }
                    ]
                }
            ]
            
            # Add data fields if available
            if message.data:
                fields = []
                for key, value in list(message.data.items())[:10]:  # Limit to 10 fields
                    fields.append({
                        "type": "mrkdwn",
                        "text": f"*{key.replace('_', ' ').title()}*\n{value}"
                    })
                    
                blocks.append({
                    "type": "section",
                    "fields": fields
                })
            
            payload = {"blocks": blocks}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent")
                        return True
                    else:
                        logger.error(f"Slack notification failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False


class DiscordNotifier:
    """Discord notification handler"""
    
    async def send_notification(self, message: NotificationMessage, webhook_url: str) -> bool:
        """Send Discord notification"""
        try:
            severity_colors = {
                "low": 0x28a745,
                "medium": 0xffc107,
                "high": 0xfd7e14,
                "critical": 0xdc3545
            }
            
            color = severity_colors.get(message.severity.lower(), 0x6c757d)
            
            embed = {
                "title": f"🚨 {message.title}",
                "description": message.message,
                "color": color,
                "timestamp": message.timestamp.isoformat(),
                "footer": {
                    "text": "EquiSense AI Alert"
                }
            }
            
            # Add fields for data
            if message.data:
                fields = []
                for key, value in list(message.data.items())[:25]:  # Discord limit
                    fields.append({
                        "name": key.replace('_', ' ').title(),
                        "value": str(value),
                        "inline": True
                    })
                embed["fields"] = fields
            
            payload = {"embeds": [embed]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status == 204:
                        logger.info(f"Discord notification sent")
                        return True
                    else:
                        logger.error(f"Discord notification failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False


class NotificationService:
    """Main notification service coordinating all channels"""
    
    def __init__(self):
        self.email_notifier = EmailNotifier()
        self.sms_notifier = SMSNotifier()
        self.webhook_notifier = WebhookNotifier()
        self.slack_notifier = SlackNotifier()
        self.discord_notifier = DiscordNotifier()
        self.user_preferences: Dict[str, NotificationPreference] = {}
        
    def add_user_preference(self, preference: NotificationPreference) -> None:
        """Add or update user notification preferences"""
        self.user_preferences[preference.user_id] = preference
        logger.info(f"Added notification preferences for user {preference.user_id}")
        
    def remove_user_preference(self, user_id: str) -> bool:
        """Remove user notification preferences"""
        if user_id in self.user_preferences:
            del self.user_preferences[user_id]
            logger.info(f"Removed notification preferences for user {user_id}")
            return True
        return False
        
    def get_user_preference(self, user_id: str) -> Optional[NotificationPreference]:
        """Get user notification preferences"""
        return self.user_preferences.get(user_id)
        
    async def send_alerts(self, triggered_alerts: List[Dict]) -> None:
        """Send notifications for triggered alerts"""
        if not triggered_alerts:
            return
            
        # Group alerts by user
        user_alerts = {}
        for alert in triggered_alerts:
            rule = alert["rule"]
            event = alert["event"]
            user_id = rule.user_id
            
            if user_id not in user_alerts:
                user_alerts[user_id] = []
            user_alerts[user_id].append(alert)
            
        # Send notifications for each user
        for user_id, alerts in user_alerts.items():
            await self._send_user_alerts(user_id, alerts)
            
    async def _send_user_alerts(self, user_id: str, alerts: List[Dict]) -> None:
        """Send alerts for a specific user"""
        preference = self.get_user_preference(user_id)
        if not preference or not preference.enabled:
            return
            
        # Check quiet hours
        if self._is_quiet_hours(preference):
            logger.info(f"Skipping notifications for user {user_id} during quiet hours")
            return
            
        # Create notification messages
        messages = []
        for alert in alerts:
            rule = alert["rule"]
            event = alert["event"]
            
            message = NotificationMessage(
                user_id=user_id,
                channel=NotificationChannel.EMAIL,  # Default channel
                title=event.title,
                message=event.description,
                severity=event.severity.value,
                data=event.data,
                timestamp=event.timestamp
            )
            messages.append(message)
            
        # Send notifications through all enabled channels
        notification_tasks = []
        
        for channel in preference.channels:
            for message in messages:
                message.channel = channel
                
                if channel == NotificationChannel.EMAIL and preference.email:
                    notification_tasks.append(
                        self.email_notifier.send_notification(message, preference.email)
                    )
                elif channel == NotificationChannel.SMS and preference.phone:
                    notification_tasks.append(
                        self.sms_notifier.send_notification(message, preference.phone)
                    )
                elif channel == NotificationChannel.WEBHOOK and preference.webhook_url:
                    notification_tasks.append(
                        self.webhook_notifier.send_notification(message, preference.webhook_url)
                    )
                elif channel == NotificationChannel.SLACK and preference.slack_webhook:
                    notification_tasks.append(
                        self.slack_notifier.send_notification(message, preference.slack_webhook)
                    )
                elif channel == NotificationChannel.DISCORD and preference.discord_webhook:
                    notification_tasks.append(
                        self.discord_notifier.send_notification(message, preference.discord_webhook)
                    )
                    
        # Send all notifications in parallel
        if notification_tasks:
            results = await asyncio.gather(*notification_tasks, return_exceptions=True)
            successful = sum(1 for result in results if result is True)
            logger.info(f"Sent {successful}/{len(notification_tasks)} notifications for user {user_id}")
            
    def _is_quiet_hours(self, preference: NotificationPreference) -> bool:
        """Check if current time is in quiet hours"""
        if not preference.quiet_hours_start or not preference.quiet_hours_end:
            return False
            
        current_hour = datetime.now().hour
        
        if preference.quiet_hours_start <= preference.quiet_hours_end:
            # Same day quiet hours (e.g., 22:00 to 08:00)
            return preference.quiet_hours_start <= current_hour <= preference.quiet_hours_end
        else:
            # Overnight quiet hours (e.g., 22:00 to 08:00)
            return current_hour >= preference.quiet_hours_start or current_hour <= preference.quiet_hours_end
            
    async def send_test_notification(self, user_id: str, channel: NotificationChannel) -> bool:
        """Send a test notification to verify settings"""
        preference = self.get_user_preference(user_id)
        if not preference:
            return False
            
        test_message = NotificationMessage(
            user_id=user_id,
            channel=channel,
            title="Test Alert",
            message="This is a test notification from EquiSense AI to verify your alert settings.",
            severity="low",
            data={"test": True},
            timestamp=datetime.now()
        )
        
        try:
            if channel == NotificationChannel.EMAIL and preference.email:
                return await self.email_notifier.send_notification(test_message, preference.email)
            elif channel == NotificationChannel.SMS and preference.phone:
                return await self.sms_notifier.send_notification(test_message, preference.phone)
            elif channel == NotificationChannel.WEBHOOK and preference.webhook_url:
                return await self.webhook_notifier.send_notification(test_message, preference.webhook_url)
            elif channel == NotificationChannel.SLACK and preference.slack_webhook:
                return await self.slack_notifier.send_notification(test_message, preference.slack_webhook)
            elif channel == NotificationChannel.DISCORD and preference.discord_webhook:
                return await self.discord_notifier.send_notification(test_message, preference.discord_webhook)
            else:
                return False
        except Exception as e:
            logger.error(f"Failed to send test notification: {e}")
            return False


# Global notification service instance
_notification_service = None

def get_notification_service() -> NotificationService:
    """Get the global notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
