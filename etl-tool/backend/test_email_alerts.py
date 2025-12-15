"""
Email Alert Trigger System - Automatically send emails when alerts trigger
"""
import os
import sys

# Clear stale environment variables before importing
if 'SMTP_USE_TLS' in os.environ:
    del os.environ['SMTP_USE_TLS']
if 'SMTP_REQUIRE_AUTH' in os.environ:
    del os.environ['SMTP_REQUIRE_AUTH']

# Reload environment from .env
from dotenv import load_dotenv
load_dotenv(override=True)

# Now import the rest
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List

sys.path.insert(0, '.')

from services.alert_manager import AlertManager
from services.notification_service import NotificationService


class EmailAlertTrigger:
    """Automatically trigger emails when alerts are detected"""
    
    def __init__(self, db_pool=None):
        self.alert_manager = AlertManager(db_pool)
        self.notification_service = NotificationService(db_pool)
        self.alerts_sent = []
    
    async def check_and_send_alerts(self, market_data: Dict[str, Any], email_recipients: List[str] = None):
        """
        Check for alerts and automatically send emails
        
        Args:
            market_data: Market conditions to check
            email_recipients: List of email addresses to send alerts to
        
        Returns:
            Dictionary with sent email info
        """
        
        if not email_recipients:
            email_recipients = ["aishwarya.sakharkar@arithwise.com"]  # Default recipient
        
        results = {
            'alerts_checked': 0,
            'alerts_triggered': 0,
            'emails_sent': 0,
            'failed': 0,
            'sent_alerts': []
        }
        
        try:
            # Check for alerts
            alert_results = await self.alert_manager.check_crypto_alerts(market_data)
            results['alerts_checked'] = alert_results['checked']
            results['alerts_triggered'] = alert_results['triggered']
            
            # Send email for each triggered alert
            for alert in alert_results['alerts']:
                try:
                    # Only send email for warning and critical alerts
                    if alert['severity'] in ['warning', 'critical']:
                        email_sent = await self._send_alert_email(
                            alert=alert,
                            recipients=email_recipients
                        )
                        
                        if email_sent:
                            results['emails_sent'] += 1
                            results['sent_alerts'].append({
                                'message': alert['message'],
                                'severity': alert['severity'],
                                'category': alert['category'],
                                'sent_to': email_recipients,
                                'timestamp': datetime.now().isoformat()
                            })
                        else:
                            results['failed'] += 1
                
                except Exception as e:
                    print(f"❌ Error sending email for alert: {e}")
                    results['failed'] += 1
            
            return results
        
        except Exception as e:
            print(f"❌ Error in check_and_send_alerts: {e}")
            return results
    
    async def _send_alert_email(self, alert: Dict[str, Any], recipients: List[str]) -> bool:
        """
        Send email for a single alert
        
        Args:
            alert: Alert object to send
            recipients: Email addresses
        
        Returns:
            True if email sent successfully
        """
        try:
            # Build email subject
            severity_icon = {
                'info': '📋',
                'warning': '⚠️',
                'critical': '🚨'
            }.get(alert['severity'], '📨')
            
            subject = f"{severity_icon} [{alert['severity'].upper()}] {alert['message'][:60]}"
            
            # Build email body
            body = f"""
CRYPTO ALERT NOTIFICATION
{'='*60}

Alert Type: {alert['category']}
Severity: {alert['severity'].upper()}
Time: {alert['timestamp']}

MESSAGE:
{alert['message']}

REASON:
{alert['reason']}

DETAILS:
{json.dumps(alert['metadata'], indent=2)}

{'='*60}
This is an automated alert from your Crypto Alert System.
Do not reply to this email.
"""
            
            # Send email via notification service
            success, error = self.notification_service.email_notifier.send_email(
                recipients=recipients,
                subject=subject,
                body=body
            )
            
            if success:
                print(f"✓ Email sent for: {alert['message']}")
                return True
            else:
                print(f"✗ Failed to send email: {error}")
                return False
        
        except Exception as e:
            print(f"✗ Failed to send email: {e}")
            return False


async def demo_with_email_trigger():
    """Demo: Check alerts and automatically send emails"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  CRYPTO ALERTS - AUTO EMAIL TRIGGER DEMO                  ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    trigger = EmailAlertTrigger()
    
    # Define market conditions that will trigger alerts
    market_data = {
        'price_data': {
            'BTC': {
                'price': 95000,
                'threshold': 90000,
                'volatility_percent': 8
            }
        },
        'volume_data': {
            'DOGE': {
                'current_volume': 5000000,
                'average_volume': 2000000
            }
        },
        'technical_data': {
            'ETH': {
                'short_ma': 3500,
                'long_ma': 3400,
                'rsi': 78
            }
        },
        'portfolio_data': {
            'value_change_percent': -10.5
        },
        'api_status': {
            'api_name': 'Binance',
            'minutes_without_data': 45
        },
        'security_data': {
            'new_login': True,
            'device_info': 'Chrome on Windows',
            'api_key_days_to_expiry': 3
        }
    }
    
    # Email recipients
    email_recipients = ["aishwarya.sakharkar@arithwise.com"]
    
    print(f"📧 Email Recipients: {', '.join(email_recipients)}\n")
    print("🔍 Checking market conditions...")
    print("📤 Sending emails for triggered alerts...\n")
    
    # Check alerts and send emails
    results = await trigger.check_and_send_alerts(market_data, email_recipients)
    
    # Display results
    print("\n" + "═"*60)
    print("📊 RESULTS:")
    print("═"*60)
    print(f"Alerts Checked: {results['alerts_checked']}")
    print(f"Alerts Triggered: {results['alerts_triggered']}")
    print(f"✓ Emails Sent: {results['emails_sent']}")
    print(f"✗ Failed: {results['failed']}")
    
    if results['sent_alerts']:
        print("\n📧 EMAILS SENT FOR:")
        for i, sent_alert in enumerate(results['sent_alerts'], 1):
            print(f"\n  {i}. {sent_alert['message']}")
            print(f"     Severity: [{sent_alert['severity'].upper()}]")
            print(f"     Category: {sent_alert['category']}")
            print(f"     Sent To: {', '.join(sent_alert['sent_to'])}")
    
    print("\n" + "═"*60)
    if results['emails_sent'] > 0:
        print(f"✅ SUCCESS: {results['emails_sent']} email(s) sent!")
    else:
        print("⚠️  No emails sent (check conditions)")
    print("═"*60)


if __name__ == "__main__":
    asyncio.run(demo_with_email_trigger())
