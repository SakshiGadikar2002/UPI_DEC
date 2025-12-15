#!/usr/bin/env python3
"""
COMPREHENSIVE EMAIL ALERT TRIGGER SYSTEM TEST
Verifies that emails are automatically sent when alerts trigger
"""
import os
import sys

# Clear stale environment variables before importing
if 'SMTP_USE_TLS' in os.environ:
    del os.environ['SMTP_USE_TLS']
if 'SMTP_REQUIRE_AUTH' in os.environ:
    del os.environ['SMTP_REQUIRE_AUTH']

from dotenv import load_dotenv
load_dotenv(override=True)

import asyncio
from datetime import datetime
from typing import Dict, Any, List

sys.path.insert(0, '.')

from services.alert_manager import AlertManager
from services.notification_service import NotificationService


class ComprehensiveEmailAlertTest:
    """Test the complete email alert triggering system"""
    
    def __init__(self):
        self.alert_manager = AlertManager(None)
        self.notification_service = NotificationService(None)
    
    async def run_comprehensive_test(self):
        """Run comprehensive email alert test"""
        print("\n" + "=" * 70)
        print("🔔 COMPREHENSIVE EMAIL ALERT TRIGGER SYSTEM TEST")
        print("=" * 70)
        
        # Test multiple market scenarios
        test_scenarios = [
            {
                "name": "High Volatility Scenario",
                "market_data": {
                    "BTC": {
                        "price": 95000,
                        "price_1h_ago": 87500,
                        "price_24h_high": 96000,
                        "volume_24h": 28000000000,
                        "volume_24h_avg": 20000000000,
                        "rsi": 72,
                        "ma_short": 93000,
                        "ma_long": 85000,
                    },
                    "ETH": {
                        "price": 3500,
                        "price_1h_ago": 3400,
                        "volume_24h": 15000000000,
                        "volume_24h_avg": 12000000000,
                        "rsi": 65,
                        "ma_short": 3450,
                        "ma_long": 3200,
                    }
                }
            },
            {
                "name": "Portfolio Risk Scenario",
                "market_data": {
                    "portfolio_value": 89500,
                    "portfolio_value_yesterday": 100000,
                    "total_holding_value": 89500,
                    "positions": [
                        {"symbol": "BTC", "allocation": 0.6, "change_percent": -10},
                        {"symbol": "ETH", "allocation": 0.4, "change_percent": -11}
                    ],
                    "BTC": {"price": 90000, "rsi": 35},
                    "ETH": {"price": 3400, "rsi": 40}
                }
            },
            {
                "name": "System Health Scenario",
                "market_data": {
                    "api_status": "offline",
                    "last_data_time": (datetime.now() - __import__('datetime').timedelta(seconds=2700)).isoformat(),
                    "etl_job_status": "failed",
                    "api_key_expiry_days": 2,
                    "BTC": {"price": 85000},
                    "ETH": {"price": 3200}
                }
            }
        ]
        
        all_emails_sent = 0
        all_alerts_triggered = 0
        
        for scenario in test_scenarios:
            print(f"\n📊 Testing: {scenario['name']}")
            print("-" * 70)
            
            try:
                # Check alerts and send emails
                result = await self.alert_manager.check_crypto_alerts_and_email(
                    market_data=scenario['market_data'],
                    email_recipients=["aishwarya.sakharkar@arithwise.com"]
                )
                
                alerts_triggered = result.get('triggered', 0)
                emails_sent = result.get('email_info', {}).get('emails_sent', 0)
                email_failed = result.get('email_info', {}).get('failed', 0)
                
                all_alerts_triggered += alerts_triggered
                all_emails_sent += emails_sent
                
                print(f"  Alerts Checked: {result.get('checked', 0)}")
                print(f"  Alerts Triggered: {alerts_triggered}")
                print(f"  Emails Sent: {emails_sent} ✓")
                print(f"  Emails Failed: {email_failed}")
                
                if alerts_triggered > 0 and emails_sent > 0:
                    print(f"\n  📧 Alerts that triggered emails:")
                    for alert in result.get('alerts', [])[:3]:  # Show first 3
                        print(f"     • {alert['message']}")
                        print(f"       Severity: {alert['severity']}")
                        print(f"       Category: {alert['category']}")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print("\n" + "=" * 70)
        print("📈 TEST SUMMARY")
        print("=" * 70)
        print(f"Total Alerts Triggered: {all_alerts_triggered}")
        print(f"Total Emails Sent: {all_emails_sent}")
        
        if all_emails_sent > 0:
            print("\n✅ SUCCESS: Email alert triggering is working!")
            print(f"   {all_emails_sent} alert emails were automatically sent")
            print(f"\n   Emails sent to: aishwarya.sakharkar@arithwise.com")
        else:
            print("\n❌ FAILURE: No emails were sent")
        
        print("\n" + "=" * 70 + "\n")


async def main():
    test = ComprehensiveEmailAlertTest()
    await test.run_comprehensive_test()


if __name__ == "__main__":
    asyncio.run(main())
