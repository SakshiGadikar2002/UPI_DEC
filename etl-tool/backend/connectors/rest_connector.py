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
        
        if self.auth_handler and self.credentials:
            try:
                headers = self.auth_handler.add_auth_headers(headers, self.credentials)
            except Exception as e:
                logger.error(f"Error adding auth headers: {e}")
        
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
                    data = await response.json()
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
                    data = {"raw": await response.text()}
                
                return {
                    "status": "success",
                    "data": data,
                    "status_code": response.status,
                    "headers": dict(response.headers),
                    "raw_response": data,  # Store raw response for database
                    "response_time_ms": response_time
                }
        except asyncio.TimeoutError:
            raise Exception("Request timeout")
        except aiohttp.ClientError as e:
            raise Exception(f"Client error: {str(e)}")
    
    async def process_message(self, message: Any) -> Dict[str, Any]:
        """Process API response message"""
        # For REST, the message is the API response
        if isinstance(message, dict) and "data" in message:
            data = message["data"]
            raw_response = message.get("raw_response", message["data"])
            status_code = message.get("status_code")
            response_time_ms = message.get("response_time_ms")
        else:
            data = message
            raw_response = message
            status_code = None
            response_time_ms = None
        
        # Normalize data structure - always return a single message dict
        # If data is a list, we'll store the whole list as data (for orderbook, etc.)
        # The frontend will handle displaying it
        if isinstance(data, list):
            # For lists (like orderbook data), store the whole list
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
            # For other types, wrap in a dict
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
    
    def _detect_exchange(self) -> str:
        """Detect exchange name from URL"""
        url_lower = self.api_url.lower()
        if "binance" in url_lower:
            return "binance"
        elif "okx" in url_lower or "okex" in url_lower:
            return "okx"
        elif "coinbase" in url_lower:
            return "coinbase"
        elif "kraken" in url_lower:
            return "kraken"
        else:
            return "custom"
    
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

