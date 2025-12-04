"""
REST API connector with polling support
"""
import aiohttp
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import logging
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from connectors.base_connector import BaseConnector
from services.auth_handler import AuthHandlerFactory


logger = logging.getLogger(__name__)


class RESTConnector(BaseConnector):
    """REST API connector with scheduled polling"""
    
    def __init__(
        self,
        connector_id: str,
        api_url: str,
        http_method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, str]] = None,
        auth_type: str = "None",
        polling_interval: int = 1000
    ):
        super().__init__(connector_id, api_url, headers, query_params, credentials, auth_type)
        self.http_method = http_method.upper()
        self.polling_interval = polling_interval / 1000.0  # Convert ms to seconds
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_handler = AuthHandlerFactory.create(auth_type) if auth_type != "None" else None
    
    async def connect(self) -> bool:
        """Create HTTP session"""
        try:
            self.session = aiohttp.ClientSession()
            logger.info(f"✅ REST connector {self.connector_id} session created")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create session for {self.connector_id}: {e}")
            return False
    
    async def disconnect(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info(f"🛑 REST connector {self.connector_id} session closed")
    
    def _build_url(self) -> str:
        """Build URL with query parameters"""
        parsed = urlparse(self.api_url)
        existing_params = parse_qs(parsed.query)
        
        # Merge existing and new query params
        all_params = {}
        for key, value_list in existing_params.items():
            all_params[key] = value_list[0] if len(value_list) == 1 else value_list
        
        # Add new query params
        if self.query_params:
            all_params.update(self.query_params)
        
        # Rebuild URL
        new_query = urlencode(all_params) if all_params else ""
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)
    
    def _prepare_headers(self) -> Dict[str, str]:
        """Prepare headers with authentication"""
        headers = self.headers.copy()
        
        # Debug logging
        logger.debug(f"[{self.connector_id}] Auth type: {self.auth_type}, Has handler: {self.auth_handler is not None}, Has credentials: {self.credentials is not None}")
        if self.credentials:
            # Log credential keys but not values for security
            logger.debug(f"[{self.connector_id}] Credential keys: {list(self.credentials.keys())}")
        
        if self.auth_handler and self.credentials:
            try:
                headers = self.auth_handler.add_auth_headers(headers, self.credentials)
                logger.info(f"[{self.connector_id}] ✅ Auth headers added successfully. Headers: {list(headers.keys())}")
            except Exception as e:
                logger.error(f"[{self.connector_id}] ❌ Error adding auth headers: {e}")
                import traceback
                traceback.print_exc()
        elif not self.auth_handler:
            logger.warning(f"[{self.connector_id}] ⚠️ No auth handler created for auth_type: '{self.auth_type}'")
        elif not self.credentials:
            logger.warning(f"[{self.connector_id}] ⚠️ No credentials available for auth_type: '{self.auth_type}'")
        
        return headers
    
    async def _make_request(self) -> Dict[str, Any]:
        """Make HTTP request"""
        url = self._build_url()
        headers = self._prepare_headers()
        start_time = datetime.utcnow()
        
        try:
            async with self.session.request(
                method=self.http_method,
                url=url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                content_type = response.headers.get('Content-Type', '')
                
                if 'application/json' in content_type:
                    raw_data = await response.json()
                    # Extract nested data from common API response formats
                    data = self._extract_nested_data(raw_data)
                elif 'text/csv' in content_type:
                    text = await response.text()
                    # Simple CSV parsing (can be enhanced)
                    lines = text.strip().split('\n')
                    if lines:
                        headers_list = lines[0].split(',')
                        data = []
                        for line in lines[1:]:
                            values = line.split(',')
                            data.append(dict(zip(headers_list, values)))
                    else:
                        data = []
                else:
                    data = {"raw": await response.text()}
                    raw_data = data
                
                return {
                    "status": "success",
                    "data": data,
                    "status_code": response.status,
                    "headers": dict(response.headers),
                    "raw_response": raw_data if 'raw_data' in locals() else data,  # Store raw response for database
                    "response_time_ms": response_time
                }
        except asyncio.TimeoutError:
            raise Exception("Request timeout")
        except aiohttp.ClientError as e:
            raise Exception(f"Client error: {str(e)}")
    
    async def process_message(self, message: Any) -> Dict[str, Any]:
        """Process API response message"""
        # For REST, the message is the API response from _make_request
        # It has structure: {"status": "success", "data": extracted_data, "raw_response": original_response, ...}
        if isinstance(message, dict) and "data" in message:
            # This is the response wrapper from _make_request
            data = message["data"]  # Already extracted nested data
            raw_response = message.get("raw_response", message.get("data"))
            status_code = message.get("status_code")
            response_time_ms = message.get("response_time_ms")
        else:
            # Fallback: treat message as raw data
            data = message
            raw_response = message
            status_code = None
            response_time_ms = None
        
        # Normalize data structure - always return a single message dict
        # If data is a list, we'll store the whole list as data (for orderbook, etc.)
        # The frontend will handle displaying it
        if isinstance(data, list):
            # For lists (like orderbook data, trades, etc.), store the whole list
            return {
                "exchange": self._detect_exchange(),
                "data": data,  # Store the whole list
                "timestamp": datetime.utcnow().isoformat(),
                "connector_id": self.connector_id,
                "message_type": "rest_response",
                "raw_response": raw_response if raw_response else data,
                "status_code": status_code,
                "response_time_ms": response_time_ms
            }
        elif isinstance(data, dict):
            # For dict responses, store as-is
            # This could be a single object or nested structure
            return {
                "exchange": self._detect_exchange(),
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
                "connector_id": self.connector_id,
                "message_type": "rest_response",
                "raw_response": raw_response if raw_response else data,
                "status_code": status_code,
                "response_time_ms": response_time_ms
            }
        else:
            # For other types (string, number, etc.), wrap in a dict
            return {
                "exchange": self._detect_exchange(),
                "data": {"value": data},
                "timestamp": datetime.utcnow().isoformat(),
                "connector_id": self.connector_id,
                "message_type": "rest_response",
                "raw_response": raw_response if raw_response else data,
                "status_code": status_code,
                "response_time_ms": response_time_ms
            }
    
    def _extract_nested_data(self, response_data: Any) -> Any:
        """Extract nested data from common API response formats"""
        if not isinstance(response_data, dict):
            return response_data
        
        # OKX format: {"code":"0","msg":"","data":[...]}
        if "code" in response_data and "data" in response_data:
            # Check if code indicates success (0 or "0" or "200" or 200)
            code = response_data.get("code")
            if code == 0 or code == "0" or code == 200 or code == "200":
                nested_data = response_data.get("data")
                if nested_data is not None:
                    return nested_data
        
        # KuCoin format: {"code":"200000","data":{...}} or {"code":"200000","data":[...]}
        if "code" in response_data and "data" in response_data:
            code = response_data.get("code")
            if code == "200000" or code == 200000:
                nested_data = response_data.get("data")
                if nested_data is not None:
                    return nested_data
        
        # Generic format: {"data":[...]} or {"data":{...}}
        if "data" in response_data and len(response_data) <= 3:
            # Only extract if response is mostly just a wrapper (has data + maybe status/code/msg)
            nested_data = response_data.get("data")
            if nested_data is not None:
                # Check if other keys are just metadata (status, code, msg, message, success)
                metadata_keys = {"status", "code", "msg", "message", "success", "error", "errors"}
                other_keys = set(response_data.keys()) - {"data"}
                if other_keys.issubset(metadata_keys):
                    return nested_data
        
        # CoinGecko format: {"data":{...}} but might have other important keys
        # For now, return as-is if it's a complex structure
        
        return response_data
    
    def _detect_exchange(self) -> str:
        """Detect exchange / provider name from URL (REST)"""
        from urllib.parse import urlparse

        url = self.api_url or ""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return "unknown"

        # Known exchanges / providers
        if "binance" in hostname:
            return "binance"
        if "okx" in hostname or "okex" in hostname:
            return "okx"
        if "coinbase" in hostname:
            return "coinbase"
        if "kraken" in hostname:
            return "kraken"
        if "kucoin" in hostname:
            return "kucoin"

        # Fallback: derive a readable name from the hostname
        parts = hostname.split(".")
        if len(parts) >= 2:
            core_parts = [p for p in parts[:-1] if p not in ("api", "www", "min", "data")]
            if core_parts:
                core = core_parts[-1]
            else:
                core = parts[-2]
        else:
            core = parts[0]

        return core or "unknown"
    
    async def _run_loop(self):
        """Main polling loop"""
        logger.info(f"🔄 Starting polling loop for {self.connector_id} (interval: {self.polling_interval}s)")
        
        while self._running:
            try:
                response = await self._make_request()
                await self._on_message(response)
                
                # Wait before next poll
                await asyncio.sleep(self.polling_interval)
            
            except Exception as e:
                logger.error(f"Error in polling loop for {self.connector_id}: {e}")
                await self.handle_error(e)
                # Wait before retry
                await asyncio.sleep(self.polling_interval)

