"""
Job Scheduler - Parallel execution of non-realtime API calls
Uses ThreadPoolExecutor for concurrent HTTP requests
Saves results to database automatically on each interval
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Any
import requests
import time

from database import (
    complete_pipeline_run,
    log_pipeline_step,
    start_pipeline_run,
    get_pool,
)

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
# Reduced to 60 seconds for more frequent data updates (continuous updater handles 2-second refreshes)
SCHEDULE_INTERVAL_SECONDS = 60
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
        pipeline_run_id = None
        pipeline_next_run = datetime.utcnow() + timedelta(seconds=SCHEDULE_INTERVAL_SECONDS)
        run_error = None
        run_status = "success"
        response = None
        record_count = 0

        def _log_step(step_name: str, status: str, details: Dict[str, Any] = None, error_message: str = None):
            """Log pipeline step status asynchronously."""
            nonlocal pipeline_run_id
            if not pipeline_run_id:
                return
            try:
                asyncio.run_coroutine_threadsafe(
                    log_pipeline_step(
                        run_id=pipeline_run_id,
                        step_name=step_name,
                        status=status,
                        details=details,
                        error_message=error_message,
                    ),
                    self.event_loop,
                ).result(timeout=5)
            except Exception as log_err:
                logger.debug(f"[PIPELINE] Failed to log step {step_name} for {api_id}: {log_err}")
        
        try:
            try:
                run_info_future = asyncio.run_coroutine_threadsafe(
                    start_pipeline_run(
                        api_id=api_id,
                        api_name=api_name,
                        source_url=url,
                        api_type="non-realtime",
                        schedule_interval_seconds=SCHEDULE_INTERVAL_SECONDS,
                    ),
                    self.event_loop,
                )
                run_info = run_info_future.result(timeout=3)
                pipeline_run_id = run_info.get("run_id")
                pipeline_next_run = run_info.get("next_run_at") or pipeline_next_run
            except Exception as start_err:
                logger.warning(f"[PIPELINE] Could not start pipeline run for {api_id}: {start_err}")

            logger.info(f"[JOB] Executing: {api_name} -> {url}")
            
            # ETL: Extract
            _log_step("extract", "running", {"url": url, "method": method})
            response = requests.request(
                method=method,
                url=url,
                timeout=15
            )
            response_time_ms = int((time.time() - start_time) * 1000)
            _log_step(
                "extract",
                "success",
                {"status_code": response.status_code, "response_time_ms": response_time_ms},
            )

            if response.status_code >= 400:
                run_status = "failure"
                run_error = f"HTTP {response.status_code}"
            
            # ETL: Clean (lightweight placeholder)
            _log_step("clean", "running")

            # ETL: Transform (parse/shape)
            _log_step("transform", "running", {"content_type": response.headers.get("content-type", "")})
            content_type = response.headers.get("content-type", "")
            data = None
            raw_response = response.text
            
            if "application/json" in content_type:
                try:
                    data = response.json()
                except Exception as parse_err:
                    data = {"raw": raw_response}
                    _log_step("transform", "failure", error_message=str(parse_err))
                    raise
            else:
                data = {"raw": raw_response}
            _log_step(
                "transform",
                "success",
                {
                    "content_type": content_type,
                    "parsed_keys": list(data.keys()) if isinstance(data, dict) else None,
                },
            )
            record_count = len(data) if isinstance(data, list) else 1
            _log_step("clean", "success", {"records": record_count})

            # ETL: Load
            _log_step("load", "running")
            
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
                save_future = asyncio.run_coroutine_threadsafe(
                    self.save_callback(message),
                    self.event_loop,
                )
                save_result = save_future.result(timeout=20)
                records_saved = (
                    save_result.get("records_saved", 0) if isinstance(save_result, dict) else 0
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
                
                _log_step(
                    "load",
                    "success",
                    {
                        "status_code": response.status_code,
                        "records_saved": records_saved or record_count,
                        "records": records_saved or record_count,
                    },
                )
                logger.info(f"[JOB] ✅ {api_name}: Saved to DB (status={response.status_code}, time={response_time_ms}ms)")
                print(f"[JOB] ✅ {api_name}: Saved to DB (status={response.status_code}, time={response_time_ms}ms)")
            except Exception as e:
                logger.error(f"[JOB] ❌ Failed to schedule save callback: {e}")
                print(f"[JOB] ❌ Failed to schedule save callback: {e}")
                _log_step("load", "failure", error_message=str(e))
                run_status = "failure"
                run_error = str(e)
        
        except requests.exceptions.Timeout:
            logger.error(f"[JOB] TIMEOUT: {api_name} (exceeded 15s)")
            _log_step("extract", "failure", error_message="timeout after 15s")
            run_status = "failure"
            run_error = "timeout"
        except requests.exceptions.RequestException as e:
            logger.error(f"[JOB] REQUEST ERROR: {api_name}: {e}")
            _log_step("extract", "failure", error_message=str(e))
            run_status = "failure"
            run_error = str(e)
        except Exception as e:
            logger.error(f"[JOB] UNEXPECTED ERROR: {api_name}: {e}")
            _log_step("transform", "failure", error_message=str(e))
            run_status = "failure"
            run_error = str(e)
        finally:
            if pipeline_run_id:
                try:
                    asyncio.run_coroutine_threadsafe(
                        complete_pipeline_run(
                            run_id=pipeline_run_id,
                            status=run_status,
                            error_message=run_error,
                            next_run_at=pipeline_next_run,
                        ),
                        self.event_loop,
                    )
                except Exception as complete_err:
                    logger.debug(f"[PIPELINE] Failed to finalize run {pipeline_run_id}: {complete_err}")
    
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
    
    async def _update_scheduled_connectors_status(self, status: str):
        """Update api_connectors status for all scheduled APIs"""
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                for api in SCHEDULED_APIS:
                    api_id = api.get("id", "unknown")
                    await conn.execute("""
                        UPDATE api_connectors 
                        SET status = $1, updated_at = NOW()
                        WHERE connector_id = $2
                    """, status, api_id)
            logger.info(f"[JOB] Updated {len(SCHEDULED_APIS)} scheduled connectors to status: {status}")
        except Exception as e:
            logger.error(f"[JOB] Error updating scheduled connector statuses: {e}")
    
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
        
        # Update api_connectors status to 'running' for all scheduled APIs
        try:
            asyncio.run_coroutine_threadsafe(
                self._update_scheduled_connectors_status("running"),
                self.event_loop
            ).result(timeout=5)
        except Exception as e:
            logger.warning(f"[JOB] Could not update connector statuses: {e}")
        
        # Run first batch immediately
        self._run_scheduled_batch()
    
    def stop(self) -> None:
        """Stop the job scheduler and wait for in-flight requests to complete."""
        if not self.is_running:
            logger.warning("[JOB] Scheduler not running")
            return
        
        self.is_running = False
        
        # Update api_connectors status to 'inactive' for all scheduled APIs
        try:
            asyncio.run_coroutine_threadsafe(
                self._update_scheduled_connectors_status("inactive"),
                self.event_loop
            ).result(timeout=5)
        except Exception as e:
            logger.warning(f"[JOB] Could not update connector statuses: {e}")
        
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
