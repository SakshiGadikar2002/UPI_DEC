"""
WebSocket connector for real-time streaming
"""
import websockets
import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from connectors.base_connector import BaseConnector
from services.auth_handler import AuthHandlerFactory


logger = logging.getLogger(__name__)


class WebSocketConnector(BaseConnector):
    """WebSocket connector for real-time data streaming"""
    
    def __init__(
        self,
        connector_id: str,
        api_url: str,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, str]] = None,
        auth_type: str = "None"
    ):
        super().__init__(connector_id, api_url, headers, query_params, credentials, auth_type)
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.auth_handler = AuthHandlerFactory.create(auth_type) if auth_type != "None" else None
        self._ping_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> bool:
        """Establish WebSocket connection"""
        try:
            # Prepare headers
            extra_headers = self._prepare_headers()
            
            # Build URL with query params
            url = self._build_url()
            
            logger.info(f"🔌 Connecting to WebSocket: {url}")
            
            self.websocket = await websockets.connect(
                url,
                extra_headers=extra_headers,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            logger.info(f"✅ WebSocket connected: {self.connector_id}")
            
            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to connect WebSocket {self.connector_id}: {e}")
            return False
    
    async def disconnect(self):
        """Close WebSocket connection"""
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            self.websocket = None
            logger.info(f"🛑 WebSocket disconnected: {self.connector_id}")
    
    def _build_url(self) -> str:
        """Build URL with query parameters"""
        from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
        
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
    
    async def _ping_loop(self):
        """Send periodic ping to keep connection alive"""
        try:
            while self._running and self.websocket:
                await asyncio.sleep(20)  # Ping every 20 seconds
                if self.websocket and not self.websocket.closed:
                    try:
                        await self.websocket.ping()
                    except Exception as e:
                        logger.warning(f"Ping failed: {e}")
                        break
        except asyncio.CancelledError:
            pass
    
    async def process_message(self, message: Any) -> Dict[str, Any]:
        """Process incoming WebSocket message"""
        try:
            # Parse JSON if string
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message
            
            # Normalize data structure
            return {
                "exchange": self._detect_exchange(),
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
                "connector_id": self.connector_id,
                "message_type": self._detect_message_type(data)
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
            return {
                "exchange": self._detect_exchange(),
                "data": {"raw": str(message)},
                "timestamp": datetime.utcnow().isoformat(),
                "connector_id": self.connector_id,
                "message_type": "unknown"
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
    
    def _detect_message_type(self, data: Dict[str, Any]) -> str:
        """Detect message type from data structure"""
        if isinstance(data, dict):
            # Binance format
            if "e" in data:
                return data.get("e", "unknown")
            # OKX format
            if "arg" in data and "data" in data:
                arg = data.get("arg", {})
                if isinstance(arg, dict):
                    channel = arg.get("channel", "unknown")
                    return channel
            # Generic
            if "type" in data:
                return data["type"]
            if "event" in data:
                return data["event"]
        
        return "trade"  # Default
    
    async def _run_loop(self):
        """Main WebSocket message loop"""
        logger.info(f"🔄 Starting WebSocket message loop for {self.connector_id}")
        
        try:
            while self._running and self.websocket:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=30.0
                    )
                    await self._on_message(message)
                
                except asyncio.TimeoutError:
                    # Timeout is normal, just continue
                    continue
                
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"WebSocket connection closed for {self.connector_id}")
                    if self._running:
                        await self.reconnect()
                    break
                
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    await self.handle_error(e)
        
        except Exception as e:
            logger.error(f"Error in WebSocket loop: {e}")
            await self.handle_error(e)

