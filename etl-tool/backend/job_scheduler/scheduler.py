"""
Job Scheduler - Parallel execution of non-realtime API calls
Uses ThreadPoolExecutor for concurrent HTTP requests
Saves results to database automatically on each interval
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Dict, List, Any
import requests
import time

logger = logging.getLogger(__name__)

# List of non-realtime APIs to schedule
# Each runs in parallel every SCHEDULE_INTERVAL_SECONDS
SCHEDULED_APIS = [
    {
        "id": "binance_orderbook",
        "name": "Binance - Order Book (BTC/USDT)",
        "url": "https://api.binance.com/api/v3/depth?symbol=BTCUSDT",
        "method": "GET"
    },
    {
        "id": "binance_prices",
        "name": "Binance - Current Prices",
        "url": "https://api.binance.com/api/v3/ticker/price",
        "method": "GET"
    },
    {
        "id": "binance_24hr",
        "name": "Binance - 24hr Ticker",
        "url": "https://api.binance.com/api/v3/ticker/24hr",
        "method": "GET"
    },
    {
        "id": "coingecko_global",
        "name": "CoinGecko - Global Market",
        "url": "https://api.coingecko.com/api/v3/global",
        "method": "GET"
    },
    {
        "id": "coingecko_top",
        "name": "CoinGecko - Top Cryptocurrencies",
        "url": "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false",
        "method": "GET"
    },
    {
        "id": "coingecko_trending",
        "name": "CoinGecko - Trending Coins",
        "url": "https://api.coingecko.com/api/v3/search/trending",
        "method": "GET"
    },
    {
        "id": "cryptocompare_multi",
        "name": "CryptoCompare - Multi Price",
        "url": "https://min-api.cryptocompare.com/data/pricemulti?fsyms=BTC,ETH,BNB&tsyms=USD",
        "method": "GET"
    },
    {
        "id": "cryptocompare_top",
        "name": "CryptoCompare - Top Coins",
        "url": "https://min-api.cryptocompare.com/data/top/mktcapfull?limit=10&tsym=USD",
        "method": "GET"
    }
]

# Schedule interval in seconds (all APIs run every N seconds)
SCHEDULE_INTERVAL_SECONDS = 10

# Max concurrent workers in thread pool
MAX_WORKERS = 8


class JobScheduler:
    """
    Manages scheduled execution of non-realtime APIs.
    
    Features:
    - Parallel execution using ThreadPoolExecutor
    - Automatic scheduling of all APIs at fixed interval
    - Saves results to database via callback
    - Thread-safe startup/shutdown
    """
    
    def __init__(self, event_loop: asyncio.AbstractEventLoop, save_callback: Callable, save_items_callback: Callable = None):
        """
        Initialize the job scheduler.
        
        Args:
            event_loop: asyncio event loop for scheduling async callbacks
            save_callback: async function to call with API result message
            save_items_callback: async function to call with individual items from API response
        """
        self.event_loop = event_loop
        self.save_callback = save_callback
        self.save_items_callback = save_items_callback
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.is_running = False
        self._schedule_handle = None
    
    def _execute_api_call(self, api_config: Dict[str, str]) -> None:
        """
        Execute a single API call and save result to database.
        Runs in thread pool executor.
        
        Args:
            api_config: API configuration with id, name, url, method
        """
        start_time = time.time()
        api_id = api_config.get("id", "unknown")
        api_name = api_config.get("name", "Unknown API")
        url = api_config.get("url", "")
        method = api_config.get("method", "GET").upper()
        
        try:
            logger.info(f"[JOB] Executing: {api_name} -> {url}")
            
            # Make HTTP request
            response = requests.request(
                method=method,
                url=url,
                timeout=15
            )
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Parse response
            content_type = response.headers.get("content-type", "")
            data = None
            raw_response = response.text
            
            if "application/json" in content_type:
                try:
                    data = response.json()
                except Exception:
                    data = {"raw": raw_response}
            else:
                data = {"raw": raw_response}
            
            # Build message for database
            message = {
                "connector_id": api_id,
                "exchange": "scheduled_api",
                "instrument": None,
                "price": None,
                "data": data,
                "raw_response": raw_response,
                "message_type": "scheduled_api_call",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status_code": response.status_code,
                "response_time_ms": response_time_ms,
            }
            
            # Schedule async save on event loop
            try:
                asyncio.run_coroutine_threadsafe(
                    self.save_callback(message),
                    self.event_loop
                )
                
                # Also save individual items if callback provided
                if self.save_items_callback:
                    logger.debug(f"[JOB] Calling items callback for {api_id}...")
                    if isinstance(data, (list, dict)):
                        try:
                            asyncio.run_coroutine_threadsafe(
                                self.save_items_callback(api_id, api_name, data, response_time_ms),
                                self.event_loop
                            )
                            logger.debug(f"[JOB] Items callback scheduled for {api_id}")
                        except Exception as callback_error:
                            logger.error(f"[JOB] Error scheduling items callback: {callback_error}")
                    else:
                        logger.debug(f"[JOB] Data is not list/dict for {api_id}, skipping items callback")
                else:
                    logger.debug(f"[JOB] save_items_callback is None!")
                
                logger.info(f"[JOB] ✅ {api_name}: Saved to DB (status={response.status_code}, time={response_time_ms}ms)")
                print(f"[JOB] ✅ {api_name}: Saved to DB (status={response.status_code}, time={response_time_ms}ms)")
            except Exception as e:
                logger.error(f"[JOB] ❌ Failed to schedule save callback: {e}")
                print(f"[JOB] ❌ Failed to schedule save callback: {e}")
        
        except requests.exceptions.Timeout:
            logger.error(f"[JOB] TIMEOUT: {api_name} (exceeded 15s)")
        except requests.exceptions.RequestException as e:
            logger.error(f"[JOB] REQUEST ERROR: {api_name}: {e}")
        except Exception as e:
            logger.error(f"[JOB] UNEXPECTED ERROR: {api_name}: {e}")
    
    def _run_scheduled_batch(self) -> None:
        """
        Submit all API calls to executor pool in parallel.
        Called every SCHEDULE_INTERVAL_SECONDS.
        """
        if not self.is_running:
            return
        
        logger.info(f"[JOB SCHEDULER] ⚡ Running batch of {len(SCHEDULED_APIS)} APIs in parallel (every {SCHEDULE_INTERVAL_SECONDS}s)...")
        print(f"[JOB SCHEDULER] ⚡ Running batch of {len(SCHEDULED_APIS)} APIs in parallel (every {SCHEDULE_INTERVAL_SECONDS}s)...")
        
        # Submit all API calls to thread pool (they run concurrently)
        for api_config in SCHEDULED_APIS:
            try:
                self.executor.submit(self._execute_api_call, api_config)
            except Exception as e:
                logger.error(f"[JOB] Failed to submit job: {e}")
                print(f"[JOB] ❌ Failed to submit job: {e}")
        
        # Schedule next batch
        if self.is_running:
            self._schedule_handle = self.event_loop.call_later(
                SCHEDULE_INTERVAL_SECONDS,
                self._run_scheduled_batch
            )
    
    def start(self) -> None:
        """Start the job scheduler (runs first batch immediately, then at interval)."""
        if self.is_running:
            logger.warning("[JOB] Scheduler already running")
            print("[JOB] ⚠️  Scheduler already running")
            return
        
        self.is_running = True
        logger.info(f"[JOB SCHEDULER] ✅ STARTED: {len(SCHEDULED_APIS)} APIs every {SCHEDULE_INTERVAL_SECONDS}s")
        print(f"[JOB SCHEDULER] ✅ STARTED: {len(SCHEDULED_APIS)} APIs every {SCHEDULE_INTERVAL_SECONDS}s")
        print(f"[JOB SCHEDULER] 📊 APIs configured: {', '.join([api['id'] for api in SCHEDULED_APIS])}")
        
        # Run first batch immediately
        self._run_scheduled_batch()
    
    def stop(self) -> None:
        """Stop the job scheduler and wait for in-flight requests to complete."""
        if not self.is_running:
            logger.warning("[JOB] Scheduler not running")
            return
        
        self.is_running = False
        
        # Cancel pending schedule
        if self._schedule_handle:
            self._schedule_handle.cancel()
            self._schedule_handle = None
        
        logger.info("[JOB] Scheduler stopped")
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor and clean up resources."""
        self.stop()
        try:
            self.executor.shutdown(wait=wait)
            logger.info("[JOB] Executor shutdown complete")
        except Exception as e:
            logger.error(f"[JOB] Error shutting down executor: {e}")


# Global scheduler instance
_scheduler: JobScheduler = None


def start_job_scheduler(event_loop: asyncio.AbstractEventLoop, save_callback: Callable, save_items_callback: Callable = None) -> JobScheduler:
    """
    Start the global job scheduler.
    
    Args:
        event_loop: asyncio event loop
        save_callback: async callback function to save results
        save_items_callback: optional async callback to save individual items
    
    Returns:
        JobScheduler instance
    """
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("[JOB] Scheduler already started")
        return _scheduler
    
    _scheduler = JobScheduler(event_loop, save_callback, save_items_callback)
    _scheduler.start()
    return _scheduler


def stop_job_scheduler() -> None:
    """Stop and shutdown the global job scheduler."""
    global _scheduler
    
    if _scheduler is None:
        logger.warning("[JOB] No scheduler to stop")
        return
    
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("[JOB] Global scheduler shut down")


def get_scheduler() -> JobScheduler:
    """Get the global scheduler instance."""
    return _scheduler
