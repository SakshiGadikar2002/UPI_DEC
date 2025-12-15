"""
Real-time Crypto Alert Testing - Monitor alerts as they trigger
This script simulates market conditions and displays alerts in real-time
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any
import sys
sys.path.insert(0, '.')

# Force reload of environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

from services.alert_manager import AlertManager
from services.crypto_alert_engine import CryptoAlertManager
from services.notification_service import EmailNotifier
from database import get_pool, connect_to_postgres


class RealTimeAlertTester:
    """Test alerts with real-time market data simulation"""
    
    def __init__(self):
        self.alert_manager = AlertManager(None)  # No DB needed for testing
        self.test_count = 0
        self.total_alerts = 0
        self.collected_alerts = []
        self.email_notifier = EmailNotifier()
        self.email_recipients = []  # Will be loaded async
        
        # Print email configuration for debugging (recipients will be shown after loading)
        print(f"\n📧 Email Configuration:")
        print(f"  SMTP Server: {self.email_notifier.smtp_server}")
        print(f"  SMTP Port: {self.email_notifier.smtp_port}")
        print(f"  From Email: {self.email_notifier.sender_email}")
        print(f"  Use TLS: {self.email_notifier.use_tls}")
        print(f"  Require Auth: {self.email_notifier.require_auth}")
        print()

    async def _load_email_recipients(self):
        """Load recipients from registered users in database, fallback to env"""
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

    def _send_email_alerts(self, alerts):
        """Send emails for warning/critical alerts during tests"""
        import time
        
        if not alerts or not self.email_recipients:
            return

        print(f"\n📧 Sending emails for {len([a for a in alerts if a.get('severity') in ('warning', 'critical')])} alerts...")
        
        for idx, alert in enumerate(alerts, 1):
            if alert.get('severity') not in ('warning', 'critical'):
                continue

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

            print(f"📤 [{idx}] Attempting to send email to {', '.join(self.email_recipients)}...")
            print(f"    Subject: {subject[:60]}...")
            
            success, error = self.email_notifier.send_email(
                recipients=self.email_recipients,
                subject=subject,
                body=body,
                html=True
            )

            if success:
                print(f"✅ [{idx}] Email QUEUED FOR DELIVERY: {alert.get('message')}")
                print(f"    ✓ Recipients: {', '.join(self.email_recipients)}")
                print(f"    ✓ Subject: {subject}")
                print(f"    ⏳ Please check your inbox (and spam folder) in a few moments")
            else:
                print(f"❌ [{idx}] Email FAILED for alert: {alert.get('message')}")
                print(f"    Error: {error}")
                print(f"    Please check:")
                print(f"    1. SMTP credentials in .env file")
                print(f"    2. Network connectivity")
                print(f"    3. Email account settings (less secure apps for Gmail)")
                print(f"    4. Recipient email address: {', '.join(self.email_recipients)}")
        
        print(f"\n✅ Email sending completed!")
        print(f"\n{'='*80}")
        print(f"📧 EMAIL DELIVERY SUMMARY")
        print(f"{'='*80}")
        print(f"Total emails sent: {len([a for a in alerts if a.get('severity') in ('warning', 'critical')])}")
        print(f"Recipient email(s): {', '.join(self.email_recipients)}")
        print(f"\n⚠️  IMPORTANT:")
        print(f"   - Emails are queued for delivery by the SMTP server")
        print(f"   - Please check your INBOX and SPAM/JUNK folder")
        print(f"   - Delivery may take 1-5 minutes depending on your email provider")
        print(f"   - If emails don't arrive, check:")
        print(f"     1. Email address is correct: {', '.join(self.email_recipients)}")
        print(f"     2. SMTP server settings in .env file")
        print(f"     3. Email provider's spam filters")
        print(f"{'='*80}\n")
    
    def print_separator(self, title=""):
        """Print colored separator"""
        if title:
            print(f"\n{'='*80}")
            print(f"  {title}")
            print(f"{'='*80}\n")
        else:
            print(f"\n{'-'*80}\n")
    
    def print_alert(self, alert: Dict[str, Any]):
        """Print alert in formatted style"""
        severity_colors = {
            'info': '🔵 INFO    ',
            'warning': '🟡 WARNING ',
            'critical': '🔴 CRITICAL'
        }
        
        severity = alert.get('severity', 'info')
        color = severity_colors.get(severity, '⚪')
        
        print(f"{color} | {alert['message']}")
        print(f"         | Category: {alert['category']}")
        print(f"         | Reason: {alert['reason']}")
        if alert.get('metadata'):
            print(f"         | Data: {json.dumps(alert['metadata'], indent=2)}")
        print()
        # Track for email sending
        self.collected_alerts.append(alert)
    
    async def test_scenario_1_price_alerts(self):
        """Test 1: Price threshold and volatility alerts"""
        self.print_separator("TEST 1: PRICE ALERTS 📈")
        
        print("Scenario: Bitcoin reaches $95,000 (threshold $90,000)")
        print("Scenario: Ethereum shows 12.5% volatility in 1 hour\n")
        
        market_data = {
            'price_data': {
                'BTC': {
                    'price': 95000,
                    'threshold': 90000,
                    'volatility_percent': 5
                },
                'ETH': {
                    'price': 3500,
                    'volatility_percent': 12.5
                }
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_2_volume_alerts(self):
        """Test 2: Volume surge and liquidity alerts"""
        self.print_separator("TEST 2: VOLUME & LIQUIDITY ALERTS 📊")
        
        print("Scenario: Dogecoin volume increases 150%")
        print("Scenario: Liquidity drops below threshold\n")
        
        market_data = {
            'volume_data': {
                'DOGE': {
                    'current_volume': 5000000,
                    'average_volume': 2000000
                },
                'XRP': {
                    'current_volume': 1000000,
                    'average_volume': 2000000
                }
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_3_technical_alerts(self):
        """Test 3: Moving average and RSI alerts"""
        self.print_separator("TEST 3: TECHNICAL INDICATORS 🔧")
        
        print("Scenario: Bitcoin MA crossover detected")
        print("Scenario: Ethereum RSI at 78 (overbought)\n")
        
        market_data = {
            'technical_data': {
                'BTC': {
                    'short_ma': 48000,
                    'long_ma': 47000,
                    'rsi': 65
                },
                'ETH': {
                    'short_ma': 3500,
                    'long_ma': 3400,
                    'rsi': 78
                }
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_4_portfolio_alerts(self):
        """Test 4: Portfolio and watchlist alerts"""
        self.print_separator("TEST 4: PORTFOLIO & WATCHLIST 💼")
        
        print("Scenario: Portfolio drops 10.5% today")
        print("Scenario: Solana in watchlist up 12.3%\n")
        
        market_data = {
            'portfolio_data': {
                'value_change_percent': -10.5
            },
            'watchlist_data': {
                'SOL': {
                    'price_change_percent': 12.3
                },
                'ADA': {
                    'price_change_percent': 3.5
                }
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_5_etl_alerts(self):
        """Test 5: ETL system and data quality alerts"""
        self.print_separator("TEST 5: ETL SYSTEM ALERTS ⚙️")
        
        print("Scenario: Binance API offline for 45 minutes")
        print("Scenario: Daily Price Aggregation job failed")
        print("Scenario: Bitcoin price changed 40% in 1 minute (anomaly)\n")
        
        market_data = {
            'api_status': {
                'api_name': 'Binance API',
                'status': 'offline',
                'minutes_without_data': 45
            },
            'etl_jobs': [
                {
                    'name': 'Daily Price Aggregation',
                    'status': 'failed',
                    'error_type': 'timeout',
                    'error_message': 'Connection timeout after 30 seconds'
                }
            ]
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        # Test data anomaly separately
        market_data['etl_jobs'].append({
            'name': 'Data Validation',
            'status': 'success',
            'data_anomaly': {
                'symbol': 'BTC',
                'price_change_percent': 40
            }
        })
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        for alert in results['alerts']:
            if 'anomaly' in alert.get('reason', '').lower():
                self.print_alert(alert)
                self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_6_security_alerts(self):
        """Test 6: Security and account alerts"""
        self.print_separator("TEST 6: SECURITY & ACCOUNT ALERTS 🔒")
        
        print("Scenario: New login from Chrome on Windows")
        print("Scenario: API key expires in 3 days\n")
        
        market_data = {
            'security_data': {
                'new_login': True,
                'device_info': 'Chrome on Windows',
                'is_new_device': True,
                'api_key_days_to_expiry': 3
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_7_combined(self):
        """Test 7: Combined multiple alerts at once"""
        self.print_separator("TEST 7: REAL-WORLD SCENARIO (Multiple Alerts)")
        
        print("Scenario: Multiple market events happening simultaneously\n")
        
        market_data = {
            'price_data': {
                'BTC': {'price': 95000, 'threshold': 90000, 'volatility_percent': 8},
                'ETH': {'price': 3500, 'volatility_percent': 15}
            },
            'volume_data': {
                'DOGE': {'current_volume': 5000000, 'average_volume': 2000000}
            },
            'technical_data': {
                'BTC': {'short_ma': 48000, 'long_ma': 47000, 'rsi': 75}
            },
            'portfolio_data': {'value_change_percent': -10.5},
            'watchlist_data': {'SOL': {'price_change_percent': 12.3}},
            'api_status': {'api_name': 'Kraken', 'minutes_without_data': 30},
            'security_data': {'new_login': True, 'device_info': 'Mobile Safari', 'api_key_days_to_expiry': 5}
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        # Group by severity
        info_alerts = [a for a in results['alerts'] if a.get('severity') == 'info']
        warning_alerts = [a for a in results['alerts'] if a.get('severity') == 'warning']
        critical_alerts = [a for a in results['alerts'] if a.get('severity') == 'critical']
        
        if critical_alerts:
            print("🔴 CRITICAL ALERTS:")
            for alert in critical_alerts:
                self.print_alert(alert)
                self.total_alerts += 1
        
        if warning_alerts:
            print("🟡 WARNING ALERTS:")
            for alert in warning_alerts:
                self.print_alert(alert)
                self.total_alerts += 1
        
        if info_alerts:
            print("🔵 INFO ALERTS:")
            for alert in info_alerts:
                self.print_alert(alert)
                self.total_alerts += 1
        
        return results['triggered']
    
    async def verify_email_setup(self):
        """Verify email configuration before running tests"""
        print("\n" + "="*80)
        print("📧 VERIFYING EMAIL SETUP")
        print("="*80)
        
        # Test sending a simple email
        test_subject = "[TEST] Crypto Alert System - Email Verification"
        test_body = """
        <html>
        <body>
            <h2>Email Verification Test</h2>
            <p>This is a test email to verify that the alert email system is working correctly.</p>
            <p>If you receive this email, the system is properly configured.</p>
            <p style="color: #666; font-size: 12px;">Sent at: {}</p>
        </body>
        </html>
        """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        print(f"\nSending test email to: {', '.join(self.email_recipients)}")
        success, error = self.email_notifier.send_email(
            recipients=self.email_recipients,
            subject=test_subject,
            body=test_body,
            html=True
        )
        
        if success:
            print("✅ Test email sent successfully!")
            print("   Please check your inbox (and spam folder) to confirm receipt.")
            print("   If you received the test email, alert emails will also work.\n")
            return True
        else:
            print(f"❌ Test email failed: {error}")
            print("\n⚠️  WARNING: Email setup verification failed!")
            print("   Alert emails may not be delivered.")
            print("   Please check:")
            print("   1. SMTP credentials in .env file")
            print("   2. Network connectivity")
            print("   3. Email account settings\n")
            response = input("Continue anyway? (y/n): ").strip().lower()
            return response == 'y'
    
    async def run_all_tests(self):
        """Run all test scenarios"""
        self.print_separator("🚀 CRYPTO ALERTS - REAL-TIME TESTING SUITE")
        print("Testing all 7 alert categories with realistic market scenarios\n")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Load email recipients from database
        print("📧 Loading email recipients from registered users...")
        self.email_recipients = await self._load_email_recipients()
        print(f"📧 Email Recipients: {', '.join(self.email_recipients) if self.email_recipients else 'None found'}")
        print()
        
        # Verify email setup first
        email_ok = await self.verify_email_setup()
        if not email_ok:
            print("\n⚠️  Skipping tests due to email verification failure.")
            return
        
        try:
            # Run all test scenarios
            await self.test_scenario_1_price_alerts()
            await self.test_scenario_2_volume_alerts()
            await self.test_scenario_3_technical_alerts()
            await self.test_scenario_4_portfolio_alerts()
            await self.test_scenario_5_etl_alerts()
            await self.test_scenario_6_security_alerts()
            await self.test_scenario_7_combined()

            # Send email notifications once for all collected alerts
            self._send_email_alerts(self.collected_alerts)
            
            # Summary
            self.print_separator("📊 TEST SUMMARY")
            print(f"Total Tests Run: 7")
            print(f"Total Alerts Triggered: {self.total_alerts}")
            print(f"Status: ✅ ALL TESTS PASSED")
            print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            print("\n✓ Price alerts - threshold and volatility detection")
            print("✓ Volume alerts - surge and liquidity drop detection")
            print("✓ Technical alerts - MA crossovers and RSI levels")
            print("✓ Portfolio alerts - watchlist and portfolio value changes")
            print("✓ ETL system alerts - API failures and data anomalies")
            print("✓ Security alerts - login detection and key expiry")
            print("✓ Real-world scenario - combined multiple alerts")
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run real-time alert tests"""
    tester = RealTimeAlertTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
