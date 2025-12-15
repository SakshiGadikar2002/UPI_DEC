#!/usr/bin/env python3
"""
EXAMPLE: Integration of Email Alert Triggering into Job Scheduler

This example shows how to integrate the email alert system into the 
job scheduler so alerts are checked and emails sent automatically on schedule.
"""

import os
import sys
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

# Clear environment before imports
if 'SMTP_USE_TLS' in os.environ:
    del os.environ['SMTP_USE_TLS']
if 'SMTP_REQUIRE_AUTH' in os.environ:
    del os.environ['SMTP_REQUIRE_AUTH']

from dotenv import load_dotenv
load_dotenv(override=True)

sys.path.insert(0, '.')

from services.alert_manager import AlertManager
from services.notification_service import NotificationService


class AlertEmailScheduler:
    """
    Scheduler for automated alert checking and email triggering.
    
    This integrates with the job scheduler to periodically:
    1. Fetch latest market data
    2. Check for alerts
    3. Automatically send emails for triggered alerts
    
    Example integration with APScheduler or similar:
    
        scheduler = APScheduler()
        alert_email_scheduler = AlertEmailScheduler(db_pool)
        
        # Schedule to run every 5 minutes
        scheduler.add_job(
            alert_email_scheduler.check_and_email_alerts,
            'interval',
            minutes=5,
            args=[market_data_fetcher, email_config]
        )
    """
    
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.alert_manager = AlertManager(db_pool)
        self.notification_service = NotificationService(db_pool)
        
        # Configuration for email alerts
        self.email_recipients = self._load_email_recipients()
        self.alert_thresholds = self._load_alert_thresholds()
    
    def _load_email_recipients(self) -> List[str]:
        """Load email recipients from config or database"""
        # This could be from .env, database, or config file
        recipients = os.getenv("ALERT_EMAIL_RECIPIENTS", "")
        if recipients:
            return [email.strip() for email in recipients.split(",")]
        return ["aishwarya.sakharkar@arithwise.com"]  # Default
    
    def _load_alert_thresholds(self) -> Dict[str, Any]:
        """Load alert thresholds from configuration"""
        return {
            "price_change_percent": float(os.getenv("ALERT_PRICE_CHANGE", "5")),
            "volume_spike_percent": float(os.getenv("ALERT_VOLUME_SPIKE", "100")),
            "rsi_overbought": float(os.getenv("ALERT_RSI_OVERBOUGHT", "70")),
            "rsi_oversold": float(os.getenv("ALERT_RSI_OVERSOLD", "30")),
            "portfolio_loss_percent": float(os.getenv("ALERT_PORTFOLIO_LOSS", "5")),
        }
    
    async def check_and_email_alerts(
        self, 
        market_data_fetcher,
        log_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Main scheduler function: Check alerts and email triggered alerts.
        
        Args:
            market_data_fetcher: Async function that returns current market data
            log_to_db: Whether to log results to database
        
        Returns:
            Dictionary with results:
            {
                "timestamp": "2025-12-10T10:30:00",
                "alerts_checked": 6,
                "alerts_triggered": 3,
                "emails_sent": 3,
                "emails_failed": 0,
                "alert_details": [...]
            }
        """
        try:
            # Fetch current market data
            print(f"[{datetime.now()}] 📊 Fetching market data...")
            market_data = await market_data_fetcher()
            
            if not market_data:
                print(f"[{datetime.now()}] ⚠️  No market data available")
                return {
                    "timestamp": datetime.now().isoformat(),
                    "status": "skipped",
                    "reason": "No market data"
                }
            
            # Check alerts and send emails
            print(f"[{datetime.now()}] 🔍 Checking alerts...")
            result = await self.alert_manager.check_crypto_alerts_and_email(
                market_data=market_data,
                email_recipients=self.email_recipients
            )
            
            # Log results
            alerts_checked = result.get('checked', 0)
            alerts_triggered = result.get('triggered', 0)
            emails_sent = result.get('email_info', {}).get('emails_sent', 0)
            emails_failed = result.get('email_info', {}).get('failed', 0)
            
            print(f"[{datetime.now()}] ✓ Alerts checked: {alerts_checked}")
            print(f"[{datetime.now()}] ✓ Alerts triggered: {alerts_triggered}")
            print(f"[{datetime.now()}] ✓ Emails sent: {emails_sent}")
            
            if emails_failed > 0:
                print(f"[{datetime.now()}] ⚠️  Email failures: {emails_failed}")
            
            # Optionally log to database
            if log_to_db and alerts_triggered > 0:
                await self._log_alert_check(
                    alerts_triggered=alerts_triggered,
                    emails_sent=emails_sent,
                    details=result
                )
            
            return {
                "timestamp": datetime.now().isoformat(),
                "alerts_checked": alerts_checked,
                "alerts_triggered": alerts_triggered,
                "emails_sent": emails_sent,
                "emails_failed": emails_failed,
                "status": "success",
                "alert_details": result.get('alerts', [])
            }
        
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Error checking alerts: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }
    
    async def _log_alert_check(
        self, 
        alerts_triggered: int,
        emails_sent: int,
        details: Dict[str, Any]
    ):
        """Log alert check results to database (optional)"""
        # This would insert into alert_logs or similar table
        # Implementation depends on your database schema
        pass


# ============================================================================
# EXAMPLE SCHEDULER INTEGRATION
# ============================================================================

async def example_market_data_fetcher() -> Dict[str, Any]:
    """
    Example function to fetch real market data.
    Replace this with your actual data source (Binance API, database, etc.)
    """
    # This would fetch from your actual API/data source
    return {
        "BTC": {
            "price": 94500,
            "price_1h_ago": 93000,
            "price_24h_high": 96000,
            "volume_24h": 28000000000,
            "volume_24h_avg": 25000000000,
            "rsi": 65,
            "ma_short": 92000,
            "ma_long": 85000,
        },
        "ETH": {
            "price": 3450,
            "price_1h_ago": 3350,
            "volume_24h": 15000000000,
            "volume_24h_avg": 12000000000,
            "rsi": 58,
            "ma_short": 3400,
            "ma_long": 3100,
        }
    }


async def example_scheduler_loop():
    """
    Example of how to run the scheduler in a loop.
    In production, use APScheduler or similar for scheduling.
    """
    scheduler = AlertEmailScheduler()
    
    print("\n" + "=" * 70)
    print("📧 ALERT EMAIL SCHEDULER - EXAMPLE INTEGRATION")
    print("=" * 70 + "\n")
    
    # Run alert check
    result = await scheduler.check_and_email_alerts(
        market_data_fetcher=example_market_data_fetcher,
        log_to_db=True
    )
    
    # Display results
    print(f"\n{'=' * 70}")
    print("📊 SCHEDULER RESULTS")
    print("=" * 70)
    
    for key, value in result.items():
        if key != 'alert_details':
            print(f"{key:20s}: {value}")
    
    if result.get('alerts_triggered', 0) > 0:
        print(f"\n📧 Alert emails sent to: {scheduler.email_recipients}")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_scheduler_loop())
    
    print("\n💡 PRODUCTION INTEGRATION GUIDE:")
    print("""
1. Import this scheduler into your job_scheduler module:
   from alert_email_scheduler import AlertEmailScheduler

2. Initialize in your scheduler setup:
   alert_scheduler = AlertEmailScheduler(db_pool)

3. Add scheduled job (using APScheduler):
   scheduler.add_job(
       alert_scheduler.check_and_email_alerts,
       'interval',
       minutes=5,  # Check every 5 minutes
       args=[your_market_data_fetcher],
       id='crypto_alerts_email'
   )

4. Configure recipients in .env:
   ALERT_EMAIL_RECIPIENTS=user1@example.com,user2@example.com,admin@example.com

5. Customize thresholds in .env:
   ALERT_PRICE_CHANGE=5
   ALERT_VOLUME_SPIKE=100
   ALERT_RSI_OVERBOUGHT=70
   ALERT_PORTFOLIO_LOSS=10

6. Monitor job execution:
   - Check logs for "✓ Alerts checked"
   - Verify emails arrive in recipients' inboxes
   - Track email_info {sent, failed} in results
    """)
