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
    log_failed_api_call,
)

logger = logging.getLogger(__name__)

# Import delta-integrated save function at module level
try:
    from services.delta_integrated_save import save_to_database_with_delta
except ImportError as e:
    logger.error(f"[JOB] Failed to import save_to_database_with_delta: {e}")
    save_to_database_with_delta = None

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
                # Extract main error reason from response
                error_reason = f"HTTP {response.status_code}"
                try:
                    # Try to parse error message from JSON response
                    if response.headers.get("content-type", "").startswith("application/json"):
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            error_msg = error_data.get("message") or error_data.get("error") or error_data.get("msg") or error_data.get("description")
                            if error_msg:
                                error_reason = f"HTTP {response.status_code}: {error_msg}"
                            else:
                                error_reason = f"HTTP {response.status_code}: {str(error_data)[:200]}"
                        else:
                            error_reason = f"HTTP {response.status_code}: {str(error_data)[:200]}"
                    else:
                        # For non-JSON responses, get first 200 chars
                        error_text = response.text[:200].strip()
                        if error_text:
                            error_reason = f"HTTP {response.status_code}: {error_text}"
                except Exception:
                    # Fallback to status code only
                    error_reason = f"HTTP {response.status_code}: Server returned error response"
                
                run_error = error_reason
                # Log failed API call for observability
                try:
                    asyncio.run_coroutine_threadsafe(
                        log_failed_api_call(
                            api_id=api_id,
                            api_name=api_name,
                            url=url,
                            method=method,
                            error_message=error_reason,
                            status_code=response.status_code,
                            response_time_ms=response_time_ms,
                            pipeline_run_id=pipeline_run_id,
                            step_name="extract",
                        ),
                        self.event_loop,
                    ).result(timeout=3)
                except Exception as log_err:
                    logger.debug(f"[FAILED_API] Failed to log failed API call: {log_err}")
            
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
                    error_reason = f"JSON parse error: {str(parse_err)[:200]}"
                    _log_step("transform", "failure", error_message=error_reason)
                    # Log failed API call for transform error
                    try:
                        asyncio.run_coroutine_threadsafe(
                            log_failed_api_call(
                                api_id=api_id,
                                api_name=api_name,
                                url=url,
                                method=method,
                                error_message=error_reason,
                                status_code=response.status_code if response else None,
                                response_time_ms=response_time_ms if 'response_time_ms' in locals() else None,
                                pipeline_run_id=pipeline_run_id,
                                step_name="transform",
                            ),
                            self.event_loop,
                        ).result(timeout=3)
                    except Exception as log_err:
                        logger.debug(f"[FAILED_API] Failed to log failed API call: {log_err}")
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
                "pipeline_run_id": pipeline_run_id,  # Add pipeline_run_id for delta tracking
            }
            
            # Schedule async save on event loop
            # For scheduled APIs, use delta-integrated save
            try:
                # Check if delta-integrated save function is available
                if save_to_database_with_delta is None:
                    raise ImportError("save_to_database_with_delta function is not available")
                
                save_future = asyncio.run_coroutine_threadsafe(
                    save_to_database_with_delta(message),
                    self.event_loop,
                )
                save_result = save_future.result(timeout=20)
                
                # Check if save_result indicates an error
                if save_result and isinstance(save_result, dict) and save_result.get("error"):
                    # Database save failed - extract detailed error
                    error_type = save_result.get("error_type", "UnknownError")
                    error_message = save_result.get("error_message", "Unknown error")
                    error_details = save_result.get("error_details", error_message)
                    
                    # Create specific error reason based on error type and message
                    if "timeout" in error_message.lower() or "timed out" in error_message.lower():
                        error_reason = f"Database operation timeout: {error_details[:200]}"
                    elif "connection" in error_message.lower() or "connect" in error_message.lower():
                        error_reason = f"Database connection failed: {error_details[:200]}"
                    elif "constraint" in error_message.lower() or "violates" in error_message.lower():
                        error_reason = f"Database constraint violation: {error_details[:200]}"
                    elif "duplicate" in error_message.lower() or "unique" in error_message.lower():
                        error_reason = f"Duplicate entry error: {error_details[:200]}"
                    elif "permission" in error_message.lower() or "access" in error_message.lower():
                        error_reason = f"Database permission denied: {error_details[:200]}"
                    elif "syntax" in error_message.lower() or "invalid" in error_message.lower():
                        error_reason = f"Database query error: {error_details[:200]}"
                    else:
                        error_reason = f"Database error ({error_type}): {error_details[:200]}"
                    
                    raise Exception(error_reason)
                
                # Extract delta information from save result
                records_saved = save_result.get("records_saved", 0) if isinstance(save_result, dict) else 0
                new_count = save_result.get("new_count", 0) if isinstance(save_result, dict) else 0
                updated_count = save_result.get("updated_count", 0) if isinstance(save_result, dict) else 0
                unchanged_count = save_result.get("unchanged_count", 0) if isinstance(save_result, dict) else 0
                
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
                        "records_saved": records_saved,
                        "new_count": new_count,
                        "updated_count": updated_count,
                        "unchanged_count": unchanged_count,
                    },
                )
                logger.info(
                    f"[JOB] ✅ {api_name}: Delta saved (NEW={new_count}, UPDATED={updated_count}, "
                    f"UNCHANGED={unchanged_count}, TOTAL={records_saved}, time={response_time_ms}ms)"
                )
                print(
                    f"[JOB] ✅ {api_name}: Delta saved (NEW={new_count}, UPDATED={updated_count}, "
                    f"UNCHANGED={unchanged_count}, TOTAL={records_saved})"
                )
            except asyncio.TimeoutError:
                error_reason = "Database save timeout - operation exceeded 20 seconds"
                logger.error(f"[JOB] ❌ Database save timeout for {api_name}")
                _log_step("load", "failure", error_message=error_reason)
                run_status = "failure"
                run_error = error_reason
                # Log failed API call for observability
                try:
                    asyncio.run_coroutine_threadsafe(
                        log_failed_api_call(
                            api_id=api_id,
                            api_name=api_name,
                            url=url,
                            method=method,
                            error_message=error_reason,
                            status_code=response.status_code if response else None,
                            response_time_ms=response_time_ms,
                            pipeline_run_id=pipeline_run_id,
                            step_name="load",
                        ),
                        self.event_loop,
                    ).result(timeout=3)
                except Exception as log_err:
                    logger.debug(f"[FAILED_API] Failed to log failed API call: {log_err}")
            except Exception as e:
                error_str = str(e)
                # Don't spam errors - log once per unique error per API
                logger.error(f"[JOB] ❌ Failed to save to database for {api_name}: {error_str[:200]}")
                # Only print if it's a new error type (not repeated schema/import errors)
                if "schema" not in error_str.lower() and "import" not in error_str.lower():
                    print(f"[JOB] ❌ Failed to save to database for {api_name}: {error_str[:200]}")
                _log_step("load", "failure", error_message=error_str[:500])
                run_status = "failure"
                
                # Extract main error reason from exception
                error_str = str(e)
                error_type = type(e).__name__
                
                # The error_reason is already set in the exception if it came from database error handling
                # Otherwise, extract it from the exception message
                if error_str and not error_str.startswith("Database"):
                    if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                        error_reason = f"Database save timeout: {error_str[:200]}"
                    elif "connection" in error_str.lower() or "connect" in error_str.lower():
                        error_reason = f"Database connection error: {error_str[:200]}"
                    elif "constraint" in error_str.lower() or "violates" in error_str.lower():
                        error_reason = f"Database constraint violation: {error_str[:200]}"
                    elif "duplicate" in error_str.lower() or "unique" in error_str.lower():
                        error_reason = f"Duplicate key error: {error_str[:200]}"
                    elif "permission" in error_str.lower() or "access" in error_str.lower():
                        error_reason = f"Database permission denied: {error_str[:200]}"
                    elif "syntax" in error_str.lower() or "invalid" in error_str.lower():
                        error_reason = f"Database query error: {error_str[:200]}"
                    else:
                        error_reason = f"Database error ({error_type}): {error_str[:200]}"
                else:
                    # Error reason already formatted
                    error_reason = error_str[:300] if error_str else f"Database save failed: {error_type}"
                
                run_error = error_reason
                # Log failed API call for observability
                try:
                    asyncio.run_coroutine_threadsafe(
                        log_failed_api_call(
                            api_id=api_id,
                            api_name=api_name,
                            url=url,
                            method=method,
                            error_message=error_reason,
                            status_code=response.status_code if response else None,
                            response_time_ms=response_time_ms,
                            pipeline_run_id=pipeline_run_id,
                            step_name="load",
                        ),
                        self.event_loop,
                    ).result(timeout=3)
                except Exception as log_err:
                    logger.debug(f"[FAILED_API] Failed to log failed API call: {log_err}")
        
        except requests.exceptions.Timeout:
            logger.error(f"[JOB] TIMEOUT: {api_name} (exceeded 15s)")
            _log_step("extract", "failure", error_message="timeout after 15s")
            run_status = "failure"
            run_error = "timeout"
            # Log failed API call for observability
            try:
                asyncio.run_coroutine_threadsafe(
                    log_failed_api_call(
                        api_id=api_id,
                        api_name=api_name,
                        url=url,
                        method=method,
                        error_message="Request timeout after 15 seconds",
                        status_code=None,
                        response_time_ms=None,
                        pipeline_run_id=pipeline_run_id,
                        step_name="extract",
                    ),
                    self.event_loop,
                ).result(timeout=3)
            except Exception as log_err:
                logger.debug(f"[FAILED_API] Failed to log failed API call: {log_err}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[JOB] REQUEST ERROR: {api_name}: {e}")
            _log_step("extract", "failure", error_message=str(e))
            run_status = "failure"
            
            # Extract main error reason
            error_type = type(e).__name__
            error_str = str(e)
            if isinstance(e, requests.exceptions.ConnectionError):
                error_reason = f"Connection error: Unable to connect to {url.split('/')[2] if '/' in url else 'server'}"
            elif isinstance(e, requests.exceptions.SSLError):
                error_reason = "SSL/TLS error: Certificate verification failed"
            elif isinstance(e, requests.exceptions.InvalidURL):
                error_reason = f"Invalid URL: {error_str[:150]}"
            elif isinstance(e, requests.exceptions.TooManyRedirects):
                error_reason = "Too many redirects: Request exceeded maximum redirect limit"
            else:
                error_reason = f"Request failed ({error_type}): {error_str[:200]}"
            
            run_error = error_reason
            # Log failed API call for observability
            try:
                asyncio.run_coroutine_threadsafe(
                    log_failed_api_call(
                        api_id=api_id,
                        api_name=api_name,
                        url=url,
                        method=method,
                        error_message=error_reason,
                        status_code=None,
                        response_time_ms=None,
                        pipeline_run_id=pipeline_run_id,
                        step_name="extract",
                    ),
                    self.event_loop,
                ).result(timeout=3)
            except Exception as log_err:
                logger.debug(f"[FAILED_API] Failed to log failed API call: {log_err}")
        except Exception as e:
            logger.error(f"[JOB] UNEXPECTED ERROR: {api_name}: {e}")
            _log_step("transform", "failure", error_message=str(e))
            run_status = "failure"
            
            # Extract main error reason
            error_type = type(e).__name__
            error_str = str(e)
            error_reason = f"Unexpected error ({error_type}): {error_str[:200]}"
            
            run_error = error_reason
            # Log failed API call for observability
            try:
                asyncio.run_coroutine_threadsafe(
                    log_failed_api_call(
                        api_id=api_id,
                        api_name=api_name,
                        url=url,
                        method=method,
                        error_message=error_reason,
                        status_code=response.status_code if response else None,
                        response_time_ms=response_time_ms if 'response_time_ms' in locals() else None,
                        pipeline_run_id=pipeline_run_id,
                        step_name="transform",
                    ),
                    self.event_loop,
                ).result(timeout=3)
            except Exception as log_err:
                logger.debug(f"[FAILED_API] Failed to log failed API call: {log_err}")
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
        
        # Check if delta save function is available before running
        if save_to_database_with_delta is None:
            logger.error("[JOB SCHEDULER] ❌ Cannot run scheduled APIs: save_to_database_with_delta is not available. Please restart the server.")
            print("[JOB SCHEDULER] ❌ Cannot run scheduled APIs: save_to_database_with_delta is not available. Please restart the server.")
            # Still schedule next batch to retry after restart
            if self.is_running:
                self._schedule_handle = self.event_loop.call_later(
                    SCHEDULE_INTERVAL_SECONDS,
                    self._run_scheduled_batch
                )
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
