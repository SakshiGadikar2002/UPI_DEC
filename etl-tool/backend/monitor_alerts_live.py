"""
Live Crypto Alert Monitor - Real-time dashboard showing alerts as they trigger
Usage: python monitor_alerts_live.py
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any, List
import sys
sys.path.insert(0, '.')

# Force reload of environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

from services.alert_manager import AlertManager
from services.notification_service import EmailNotifier
from database import get_pool, connect_to_postgres


class LiveAlertMonitor:
    """Monitor alerts in real-time with live dashboard"""
    
    def __init__(self):
        self.alert_manager = AlertManager(None)
        self.alerts_history: List[Dict[str, Any]] = []
        self.stats = {
            'total_checked': 0,
            'total_triggered': 0,
            'by_severity': {'info': 0, 'warning': 0, 'critical': 0},
            'by_category': {}
        }
        self.email_notifier = EmailNotifier()
        self.email_recipients = []  # Will be loaded async
        
        # Print email configuration for debugging
        print(f"\n📧 Email Configuration:")
        print(f"  SMTP Server: {self.email_notifier.smtp_server}")
        print(f"  SMTP Port: {self.email_notifier.smtp_port}")
        print(f"  From Email: {self.email_notifier.sender_email}")
        print(f"  Use TLS: {self.email_notifier.use_tls}")
        print(f"  Require Auth: {self.email_notifier.require_auth}")
        print()

    async def _load_email_recipients(self) -> List[str]:
        """Get recipient list from registered users in database, fallback to env"""
        try:
            # Try to connect to database and get active users
            await connect_to_postgres()
            pool = get_pool()
            
            async with pool.acquire() as conn:
                users = await conn.fetch(
                    """
                    SELECT email, full_name FROM users WHERE is_active = TRUE
                    ORDER BY created_at ASC
                    """
                )
                
                if users:
                    recipients = [user['email'] for user in users]
                    print(f"📧 Found {len(recipients)} registered user(s) in database:")
                    for user in users:
                        print(f"   ✓ {user['email']} ({user['full_name'] or 'No name'})")
                    return recipients
        except Exception as e:
            print(f"⚠️  Could not fetch users from database: {e}")
            print(f"   Falling back to environment variables...")
        
        # Fallback to environment variables if database fails
        recipients_env = os.getenv("ALERT_EMAIL_RECIPIENTS")
        if recipients_env:
            recipients = [r.strip() for r in recipients_env.split(",") if r.strip()]
            if recipients:
                print(f"📧 Using ALERT_EMAIL_RECIPIENTS from .env: {recipients}")
                return recipients

        fallback = (
            os.getenv("SMTP_TO")
            or os.getenv("SMTP_FROM_EMAIL")
            or os.getenv("SMTP_USER")
        )
        if fallback:
            print(f"📧 Using fallback email from .env: {fallback}")
            return [fallback]

        # Last resort default
        default = ["aishwarya.sakharkar@arithwise.com"]
        print(f"⚠️  No users found in database, using default: {default}")
        return default

    def _send_email_alerts(self, alerts: List[Dict[str, Any]]) -> None:
        """Send emails for warning/critical alerts without needing DB"""
        import time
        
        if not alerts or not self.email_recipients:
            return

        important_alerts = [a for a in alerts if a.get('severity') in ('warning', 'critical')]
        if not important_alerts:
            return

        for idx, alert in enumerate(important_alerts, 1):
            # Add delay between emails to avoid rate limiting and ensure delivery
            if idx > 1:
                time.sleep(3)  # Increased delay to 3 seconds for better delivery

            subject = f"[{alert.get('severity', 'INFO').upper()}] {alert.get('message', 'Alert')}"
            body = EmailNotifier.format_alert_email(
                alert_message=alert.get('message', 'Alert'),
                alert_category=alert.get('category', 'crypto_alerts'),
                alert_reason=alert.get('reason', 'No reason provided'),
                severity=alert.get('severity', 'info'),
                metadata=alert.get('metadata')
            )

            print(f"📤 Attempting to send email to {', '.join(self.email_recipients)}...")
            print(f"    Subject: {subject[:60]}...")
            
            success, error = self.email_notifier.send_email(
                recipients=self.email_recipients,
                subject=subject,
                body=body,
                html=True
            )

            if success:
                print(f"✅ Email QUEUED FOR DELIVERY: {alert.get('message')}")
                print(f"    ✓ Recipients: {', '.join(self.email_recipients)}")
                print(f"    ✓ Subject: {subject[:50]}...")
            else:
                print(f"❌ Email FAILED for alert: {alert.get('message')}")
                print(f"    Error: {error}")
                print(f"    Please check:")
                print(f"    1. SMTP credentials in .env file")
                print(f"    2. Network connectivity")
                print(f"    3. Email account settings (less secure apps for Gmail)")
                print(f"    4. Recipient email address: {', '.join(self.email_recipients)}")
        
        # Summary after all emails
        sent_count = len(important_alerts)
        if sent_count > 0:
            print(f"\n{'='*60}")
            print(f"📧 Email Summary: {sent_count} email(s) queued for delivery")
            print(f"   Recipient(s): {', '.join(self.email_recipients)}")
            print(f"   ⏳ Check your INBOX and SPAM folder in 1-5 minutes")
            print(f"{'='*60}\n")
    
    def print_dashboard(self):
        """Print live alert dashboard"""
        print("\033[2J\033[H")  # Clear screen
        
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║          🚀 CRYPTO ALERTS - LIVE MONITORING DASHBOARD              ║")
        print("╚════════════════════════════════════════════════════════════════════╝\n")
        
        # Stats
        print("📊 STATISTICS:")
        print(f"  Total Checked: {self.stats['total_checked']}")
        print(f"  Total Triggered: {self.stats['total_triggered']}")
        print(f"  Severity Breakdown:")
        print(f"    🔵 Info: {self.stats['by_severity']['info']}")
        print(f"    🟡 Warning: {self.stats['by_severity']['warning']}")
        print(f"    🔴 Critical: {self.stats['by_severity']['critical']}\n")
        
        # Recent alerts
        print("⚡ RECENT ALERTS:")
        if self.alerts_history:
            for i, alert in enumerate(self.alerts_history[-10:], 1):
                severity_icon = {
                    'info': '🔵',
                    'warning': '🟡',
                    'critical': '🔴'
                }.get(alert['severity'], '⚪')
                
                timestamp = alert['timestamp']
                message = alert['message'][:60]
                category = alert['category']
                
                print(f"  {i}. {severity_icon} [{timestamp}] {message}...")
                print(f"     Category: {category}\n")
        else:
            print("  No alerts yet. Waiting for market events...\n")
        
        print("╔════════════════════════════════════════════════════════════════════╗")
        print(f"  Last Updated: {datetime.now().strftime('%H:%M:%S')}")
        print("  Status: 🟢 MONITORING ACTIVE")
        print("╚════════════════════════════════════════════════════════════════════╝")
    
    async def simulate_market_events(self):
        """Simulate realistic market events"""
        
        events = [
            {
                'name': 'Price Surge',
                'data': {
                    'price_data': {
                        'BTC': {'price': 95000, 'threshold': 90000, 'volatility_percent': 8}
                    }
                }
            },
            {
                'name': 'Volume Spike',
                'data': {
                    'volume_data': {
                        'DOGE': {'current_volume': 5000000, 'average_volume': 2000000}
                    }
                }
            },
            {
                'name': 'Technical Crossover',
                'data': {
                    'technical_data': {
                        'ETH': {'short_ma': 3500, 'long_ma': 3400, 'rsi': 78}
                    }
                }
            },
            {
                'name': 'API Issue',
                'data': {
                    'api_status': {
                        'api_name': 'Binance',
                        'minutes_without_data': 45
                    }
                }
            },
            {
                'name': 'Security Alert',
                'data': {
                    'security_data': {
                        'new_login': True,
                        'device_info': 'Unknown Device',
                        'api_key_days_to_expiry': 3
                    }
                }
            }
        ]
        
        return events
    
    async def check_market_conditions(self, market_data: Dict[str, Any]):
        """Check market conditions and update dashboard"""
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        self.stats['total_checked'] += results['checked']
        self.stats['total_triggered'] += results['triggered']
        
        for alert in results['alerts']:
            self.alerts_history.append(alert)
            severity = alert.get('severity', 'info')
            self.stats['by_severity'][severity] += 1
            
            category = alert.get('category', 'unknown')
            if category not in self.stats['by_category']:
                self.stats['by_category'][category] = 0
            self.stats['by_category'][category] += 1

        # Fire off email notifications for important alerts
        self._send_email_alerts(results['alerts'])
        
        self.print_dashboard()
    
    async def run_live_monitoring(self, duration_seconds: int = 60, interval: int = 5):
        """Run live monitoring for specified duration"""
        
        start_time = datetime.now()
        events = await self.simulate_market_events()
        event_idx = 0
        
        print(f"🟢 Starting live monitoring for {duration_seconds} seconds...")
        print(f"   New market event every {interval} seconds")
        
        while (datetime.now() - start_time).total_seconds() < duration_seconds:
            # Get next event
            event = events[event_idx % len(events)]
            event_idx += 1
            
            # Check alerts
            await self.check_market_conditions(event['data'])
            
            # Wait before next check
            await asyncio.sleep(interval)
        
        print("\n\n✅ Monitoring completed!")


async def verify_email_setup(monitor: LiveAlertMonitor) -> bool:
    """Verify email configuration before starting monitoring"""
    from datetime import datetime
    
    # Load recipients first
    print("\n📧 Loading email recipients from registered users...")
    monitor.email_recipients = await monitor._load_email_recipients()
    
    if not monitor.email_recipients:
        print("❌ No email recipients found!")
        return False
    
    print("\n" + "="*80)
    print("📧 VERIFYING EMAIL SETUP")
    print("="*80)
    
    test_subject = "[TEST] Crypto Alert Monitor - Email Verification"
    test_body = """
    <html>
    <body>
        <h2>Email Verification Test</h2>
        <p>This is a test email to verify that the alert email system is working correctly.</p>
        <p>If you receive this email, the monitoring system is properly configured.</p>
        <p style="color: #666; font-size: 12px;">Sent at: {}</p>
    </body>
    </html>
    """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    print(f"\nSending test email to: {', '.join(monitor.email_recipients)}")
    success, error = monitor.email_notifier.send_email(
        recipients=monitor.email_recipients,
        subject=test_subject,
        body=test_body,
        html=True
    )
    
    if success:
        print("✅ Test email sent successfully!")
        print("   Please check your inbox (and spam folder) to confirm receipt.\n")
        return True
    else:
        print(f"❌ Test email failed: {error}")
        print("\n⚠️  WARNING: Email setup verification failed!")
        print("   Alert emails may not be delivered.\n")
        return False

async def main():
    """Main entry point"""
    monitor = LiveAlertMonitor()
    
    # Verify email setup first
    email_ok = await verify_email_setup(monitor)
    if not email_ok:
        print("⚠️  Starting monitoring anyway, but emails may not be delivered.")
        print("   Press Ctrl+C to stop and fix email configuration.\n")
        import time
        time.sleep(3)
    
    # Run for 60 seconds with 5-second intervals
    await monitor.run_live_monitoring(duration_seconds=60, interval=5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⛔ Monitoring stopped by user")
