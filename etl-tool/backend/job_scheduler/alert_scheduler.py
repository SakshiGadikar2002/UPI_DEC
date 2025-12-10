"""
Alert Scheduler - Integrates alert checking into APScheduler with email triggering
"""
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import asyncio

from services.alert_manager import AlertManager
from database import get_pool

logger = logging.getLogger(__name__)


class AlertScheduler:
    """Manages scheduled alert checking with email notifications"""
    
    def __init__(self):
        self.alert_manager: Optional[AlertManager] = None
        self.is_running = False
        self.email_recipients: List[str] = []
    
    async def initialize(self):
        """Initialize alert scheduler"""
        try:
            pool = get_pool()
            self.alert_manager = AlertManager(pool)
            
            # Load email recipients from config
            self.email_recipients = self._load_email_recipients()
            
            logger.info(f"Alert scheduler initialized with {len(self.email_recipients)} email recipients")
        except Exception as e:
            logger.error(f"Failed to initialize alert scheduler: {e}")
    
    def _load_email_recipients(self) -> List[str]:
        """Load email recipients from environment or config"""
        import os
        recipients_str = os.getenv("ALERT_EMAIL_RECIPIENTS", "aishwarya.sakharkar@arithwise.com")
        if recipients_str:
            return [email.strip() for email in recipients_str.split(",")]
        return []
    
    async def get_latest_market_data(self) -> Dict[str, Any]:
        """
        Fetch latest market data from websocket_messages table
        Converts raw websocket data to alert manager format
        """
        try:
            pool = get_pool()
            
            async with pool.acquire() as conn:
                # Get latest prices from websocket messages
                latest_data = await conn.fetch("""
                    SELECT DISTINCT ON (instrument) 
                        instrument,
                        data,
                        timestamp
                    FROM websocket_messages
                    WHERE timestamp > NOW() - INTERVAL '5 minutes'
                    ORDER BY instrument, timestamp DESC
                """)
                
                if not latest_data:
                    logger.debug("No recent websocket data available")
                    return {}
                
                # Convert to alert manager format
                market_data = {
                    'price_data': {},
                    'volume_data': {},
                    'technical_data': {},
                }
                
                for row in latest_data:
                    instrument = row['instrument'] or 'unknown'
                    data = row['data'] or {}
                    # DB may return JSON as a string; ensure we parse it to a dict
                    if isinstance(data, (bytes, bytearray)):
                        try:
                            data = json.loads(data.decode('utf-8'))
                        except Exception:
                            logger.debug("Could not decode bytes data for instrument %s", instrument)
                            data = {}
                    elif isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except Exception:
                            # If it's not JSON, leave as empty dict to avoid attribute errors
                            logger.debug("Could not parse string data as JSON for instrument %s", instrument)
                            data = {}
                    
                    # Extract price data
                    if 'price' in data:
                        market_data['price_data'][instrument] = {
                            'current_price': float(data.get('price', 0)),
                            'price_change_1h': float(data.get('change_1h', 0)),
                            'price_high_24h': float(data.get('high_24h', 0)),
                            'price_low_24h': float(data.get('low_24h', 0)),
                        }
                    
                    # Extract volume data
                    if 'volume' in data:
                        market_data['volume_data'][instrument] = {
                            'volume_24h': float(data.get('volume', 0)),
                            'volume_change_percent': float(data.get('volume_change_percent', 0)),
                        }
                    
                    # Extract technical data
                    if 'rsi' in data or 'macd' in data:
                        market_data['technical_data'][instrument] = {
                            'rsi': float(data.get('rsi', 50)),
                            'macd': float(data.get('macd', 0)),
                            'bb_upper': float(data.get('bb_upper', 0)),
                            'bb_lower': float(data.get('bb_lower', 0)),
                        }
                
                logger.debug(f"Fetched market data for {len(latest_data)} instruments")
                return market_data
        
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return {}
    
    async def run_alert_check(self):
        """Run alert checking cycle with email triggering"""
        if not self.alert_manager:
            logger.warning("Alert scheduler not initialized")
            return
        
        try:
            # Get latest market data from websocket
            market_data = await self.get_latest_market_data()
            
            if not market_data or not any([
                market_data.get('price_data'),
                market_data.get('volume_data'),
                market_data.get('technical_data')
            ]):
                logger.debug("No market data available for alert checking")
                return
            
            # Check alerts AND send emails
            logger.debug("Starting alert check cycle with email triggering")
            result = await self.alert_manager.check_crypto_alerts_and_email(
                market_data=market_data,
                email_recipients=self.email_recipients
            )
            
            alerts_triggered = result.get('triggered', 0)
            emails_sent = result.get('email_info', {}).get('emails_sent', 0)
            emails_failed = result.get('email_info', {}).get('failed', 0)
            
            # Log results
            if alerts_triggered > 0 or emails_sent > 0:
                logger.info(
                    f"Alert check: {result.get('checked', 0)} checked, "
                    f"{alerts_triggered} triggered, "
                    f"{emails_sent} emails sent"
                )
            
            if emails_failed > 0:
                logger.warning(f"Alert check: {emails_failed} emails failed to send")
            
            # Log to database if alerts were triggered
            if alerts_triggered > 0:
                await self._log_alert_check_results(result)
        
        except Exception as e:
            logger.error(f"Error in alert check cycle: {e}", exc_info=True)
    
    async def _log_alert_check_results(self, result: Dict[str, Any]):
        """Log alert check results to database"""
        try:
            pool = get_pool()
            triggered_count = result.get('triggered', 0)
            
            if triggered_count == 0:
                return
            
            async with pool.acquire() as conn:
                # Log summary to alert_logs
                await conn.execute("""
                    INSERT INTO alert_logs (
                        alert_type,
                        status,
                        message,
                        metadata,
                        created_at
                    ) VALUES ($1, $2, $3, $4, NOW())
                """, 'system', 'triggered', 
                    f"{triggered_count} alerts triggered during check",
                    json.dumps(result)
                )
        except Exception as e:
            logger.error(f"Error logging alert results: {e}")



# Global alert scheduler instance
alert_scheduler = AlertScheduler()


async def start_alert_scheduler():
    """Start alert scheduler (called from main.py lifespan)"""
    try:
        await alert_scheduler.initialize()
        
        # Schedule alert checking every minute
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        
        scheduler = AsyncIOScheduler()
        
        # Add job to check alerts every 5 minutes
        scheduler.add_job(
            alert_scheduler.run_alert_check,
            'interval',
            minutes=5,
            id='alert_check',
            name='Check alert conditions with email triggering every 5 minutes',
            coalesce=True,
            max_instances=1
        )
        
        # Add job to clean up old alerts weekly
        scheduler.add_job(
            cleanup_old_alerts,
            'interval',
            days=1,
            id='cleanup_alerts',
            name='Clean up old alerts',
            coalesce=True,
            max_instances=1
        )
        
        scheduler.start()
        logger.info("Alert scheduler started with jobs")
        
        return scheduler
    except Exception as e:
        logger.error(f"Failed to start alert scheduler: {e}")
        return None


async def cleanup_old_alerts():
    """Clean up old alerts from database (older than 90 days)"""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Delete old alert logs
            deleted_count = await conn.fetchval("""
                DELETE FROM alert_logs
                WHERE created_at < NOW() - INTERVAL '90 days'
            """)
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old alerts")
    except Exception as e:
        logger.error(f"Error cleaning up old alerts: {e}")


async def stop_alert_scheduler(scheduler):
    """Stop alert scheduler"""
    try:
        if scheduler:
            scheduler.shutdown()
            logger.info("Alert scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping alert scheduler: {e}")
