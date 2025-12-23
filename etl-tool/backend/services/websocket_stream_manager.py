"""
WebSocket Stream Manager - Manages external WebSocket connections with persistence-first flow
Enforces: WebSocket → Database → Visualization
"""
import asyncio
import json
import logging
import websockets
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import uuid
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class WebSocketStreamManager:
    """Manages external WebSocket connections with persistence-first data flow"""
    
    def __init__(self, db_save_callback: Callable, broadcast_callback: Callable):
        """
        Initialize WebSocket Stream Manager
        
        Args:
            db_save_callback: Function to save data to database (must be async)
            broadcast_callback: Function to broadcast to frontend WebSocket clients (must be async)
        """
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.db_save_callback = db_save_callback
        self.broadcast_callback = broadcast_callback
        self._running = True
    
    async def connect(
        self,
        connection_id: str,
        websocket_url: str,
        exchange: str,
        subscription_message: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
        inst_id: Optional[str] = None,
        symbol: Optional[str] = None,
        stream_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Connect to external WebSocket with persistence-first flow
        
        Args:
            connection_id: Unique identifier for this connection
            websocket_url: WebSocket URL to connect to
            exchange: Exchange name (okx, binance, custom)
            subscription_message: Optional subscription message (for OKX/custom)
            channel: OKX channel (e.g., 'trades')
            inst_id: OKX instrument ID
            symbol: Binance symbol
            stream_type: Binance stream type
        
        Returns:
            Dict with connection status
        """
        if connection_id in self.active_connections:
            logger.warning(f"Connection {connection_id} already exists")
            return {
                "success": False,
                "error": "Connection already exists",
                "connection_id": connection_id
            }
        
        try:
            logger.info(f"🔌 Connecting to external WebSocket: {websocket_url} (connection_id={connection_id})")
            
            # Connect to external WebSocket
            ws = await websockets.connect(
                websocket_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            # Store connection info
            connection_info = {
                "websocket": ws,
                "connection_id": connection_id,
                "websocket_url": websocket_url,
                "exchange": exchange,
                "channel": channel,
                "inst_id": inst_id,
                "symbol": symbol,
                "stream_type": stream_type,
                "subscription_message": subscription_message,
                "message_count": 0,
                "start_time": datetime.utcnow(),
                "task": None
            }
            
            # Send subscription message if provided
            if subscription_message:
                try:
                    sub_msg_str = json.dumps(subscription_message) if isinstance(subscription_message, dict) else subscription_message
                    await ws.send(sub_msg_str)
                    logger.info(f"📤 Sent subscription message: {sub_msg_str}")
                except Exception as e:
                    logger.error(f"Error sending subscription message: {e}")
            
            # Start message processing task
            task = asyncio.create_task(
                self._process_messages(connection_info)
            )
            connection_info["task"] = task
            
            self.active_connections[connection_id] = connection_info
            
            logger.info(f"✅ External WebSocket connected: {connection_id}")
            
            return {
                "success": True,
                "connection_id": connection_id,
                "exchange": exchange,
                "websocket_url": websocket_url
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to connect external WebSocket {connection_id}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "connection_id": connection_id
            }
    
    async def disconnect(self, connection_id: str) -> Dict[str, Any]:
        """Disconnect external WebSocket connection"""
        if connection_id not in self.active_connections:
            return {
                "success": False,
                "error": "Connection not found",
                "connection_id": connection_id
            }
        
        try:
            connection_info = self.active_connections[connection_id]
            
            # Cancel message processing task
            if connection_info.get("task"):
                connection_info["task"].cancel()
                try:
                    await connection_info["task"]
                except asyncio.CancelledError:
                    pass
            
            # Close WebSocket
            if connection_info.get("websocket"):
                await connection_info["websocket"].close()
            
            # Remove from active connections
            del self.active_connections[connection_id]
            
            logger.info(f"🛑 External WebSocket disconnected: {connection_id}")
            
            return {
                "success": True,
                "connection_id": connection_id
            }
            
        except Exception as e:
            logger.error(f"Error disconnecting {connection_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "connection_id": connection_id
            }
    
    async def _process_messages(self, connection_info: Dict[str, Any]):
        """
        Process incoming WebSocket messages with persistence-first flow:
        1. Receive message from external WebSocket
        2. Save to database FIRST
        3. Then broadcast to frontend
        """
        connection_id = connection_info["connection_id"]
        ws = connection_info["websocket"]
        exchange = connection_info["exchange"]
        
        logger.info(f"🔄 Starting message processing loop for {connection_id}")
        
        try:
            while self._running and ws and not ws.closed:
                try:
                    # Receive message from external WebSocket
                    message = await asyncio.wait_for(
                        ws.recv(),
                        timeout=30.0
                    )
                    
                    # Parse message
                    try:
                        if isinstance(message, str):
                            parsed_data = json.loads(message)
                        else:
                            parsed_data = message
                    except json.JSONDecodeError:
                        parsed_data = {"raw": str(message)}
                    
                    # Skip ping/pong and subscription confirmations
                    if self._is_control_message(parsed_data):
                        continue
                    
                    # Extract instrument and price
                    instrument = self._extract_instrument(parsed_data, connection_info)
                    price = self._extract_price(parsed_data)
                    
                    # Prepare message for database
                    message_for_db = {
                        "connector_id": f"websocket_{connection_id}",
                        "exchange": exchange,
                        "instrument": instrument or "-",
                        "price": price or 0.0,
                        "data": parsed_data,
                        "message_type": self._detect_message_type(parsed_data, connection_info),
                        "timestamp": datetime.utcnow().isoformat(),
                        "raw_response": parsed_data
                    }
                    
                    # STEP 1: Save to database FIRST (persistence-first)
                    saved_record = await self.db_save_callback(message_for_db)
                    
                    if saved_record:
                        connection_info["message_count"] += 1
                        
                        # STEP 2: Broadcast to frontend WebSocket clients (only after DB save)
                        broadcast_message = {
                            **message_for_db,
                            "id": saved_record.get("id"),
                            "source_id": saved_record.get("source_id"),
                            "session_id": saved_record.get("session_id"),
                            "db_timestamp": saved_record.get("timestamp"),
                            "type": "data_update",
                            "connection_id": connection_id
                        }
                        
                        await self.broadcast_callback(broadcast_message)
                        
                        logger.debug(
                            f"[{connection_id}] Saved and broadcasted message #{connection_info['message_count']}: "
                            f"instrument={instrument}, price={price}"
                        )
                    else:
                        logger.warning(f"[{connection_id}] Failed to save message to database, skipping broadcast")
                
                except asyncio.TimeoutError:
                    # Timeout is normal, continue
                    continue
                
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"External WebSocket connection closed for {connection_id}")
                    break
                
                except Exception as e:
                    logger.error(f"Error processing message for {connection_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue processing despite errors
                    await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            logger.info(f"Message processing cancelled for {connection_id}")
        except Exception as e:
            logger.error(f"Error in message processing loop for {connection_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            logger.info(f"🛑 Message processing loop ended for {connection_id}")
    
    def _is_control_message(self, data: Dict[str, Any]) -> bool:
        """Check if message is a control message (ping/pong/subscription confirmation)"""
        if not isinstance(data, dict):
            return False
        
        # OKX subscription confirmation
        if data.get("event") in ["subscribe", "unsubscribe", "error"]:
            return True
        
        # OKX ping/pong
        if data.get("op") == "pong":
            return True
        
        # Binance subscription confirmation
        if "result" in data or "id" in data and "result" in data:
            return True
        
        return False
    
    def _extract_instrument(self, data: Dict[str, Any], connection_info: Dict[str, Any]) -> Optional[str]:
        """Extract instrument/symbol from message data"""
        if not isinstance(data, dict):
            return None
        
        exchange = connection_info.get("exchange", "")
        
        # OKX format
        if exchange == "okx":
            if "arg" in data and isinstance(data["arg"], dict):
                inst_id = data["arg"].get("instId")
                if inst_id:
                    return inst_id
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                trade = data["data"][0]
                if "instId" in trade:
                    return trade["instId"]
        
        # Binance format
        elif exchange == "binance":
            if "stream" in data:
                stream = data["stream"]
                symbol = stream.split("@")[0].upper()
                if len(symbol) == 6:
                    return f"{symbol[:3]}-{symbol[3:]}"
                return symbol
            if "data" in data and isinstance(data["data"], dict):
                symbol = data["data"].get("s")
                if symbol:
                    if len(symbol) == 6:
                        return f"{symbol[:3]}-{symbol[3:]}"
                    return symbol
            if "s" in data:
                symbol = data["s"]
                if len(symbol) == 6:
                    return f"{symbol[:3]}-{symbol[3:]}"
                return symbol
        
        return connection_info.get("inst_id") or connection_info.get("symbol")
    
    def _extract_price(self, data: Dict[str, Any]) -> Optional[float]:
        """Extract price from message data"""
        if not isinstance(data, dict):
            return None
        
        # Recursive price extraction
        def _find_price(obj, depth=0, max_depth=5):
            if not obj or depth > max_depth:
                return None
            
            if isinstance(obj, dict):
                # Try common price fields
                for price_field in ["px", "p", "last", "c", "price", "close", "lastPrice", "tradePrice"]:
                    if price_field in obj and obj[price_field] is not None:
                        try:
                            price_val = obj[price_field]
                            if isinstance(price_val, str):
                                price_val = price_val.strip()
                                if price_val and price_val not in ["null", "None"]:
                                    return float(price_val)
                            elif isinstance(price_val, (int, float)):
                                return float(price_val)
                        except (ValueError, TypeError):
                            continue
                
                # Check nested "data" field
                if "data" in obj:
                    nested_price = _find_price(obj["data"], depth + 1, max_depth)
                    if nested_price is not None:
                        return nested_price
                
                # Recursively search
                for value in obj.values():
                    nested_price = _find_price(value, depth + 1, max_depth)
                    if nested_price is not None:
                        return nested_price
            
            elif isinstance(obj, list) and len(obj) > 0:
                return _find_price(obj[0], depth + 1, max_depth)
            
            return None
        
        return _find_price(data)
    
    def _detect_message_type(self, data: Dict[str, Any], connection_info: Dict[str, Any]) -> str:
        """Detect message type from data structure"""
        if not isinstance(data, dict):
            return "unknown"
        
        exchange = connection_info.get("exchange", "")
        
        # OKX format
        if exchange == "okx":
            if "arg" in data and isinstance(data["arg"], dict):
                return data["arg"].get("channel", "trade")
        
        # Binance format
        elif exchange == "binance":
            if "e" in data:
                return data["e"]
            if "data" in data and isinstance(data["data"], dict):
                return data["data"].get("e", "trade")
        
        # Generic
        if "type" in data:
            return data["type"]
        if "event" in data:
            return data["event"]
        
        return connection_info.get("channel") or connection_info.get("stream_type") or "trade"
    
    def get_connection_status(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a connection"""
        if connection_id not in self.active_connections:
            return None
        
        conn = self.active_connections[connection_id]
        return {
            "connection_id": connection_id,
            "exchange": conn.get("exchange"),
            "websocket_url": conn.get("websocket_url"),
            "message_count": conn.get("message_count", 0),
            "start_time": conn.get("start_time").isoformat() if conn.get("start_time") else None,
            "is_connected": conn.get("websocket") and not conn.get("websocket").closed
        }
    
    def list_connections(self) -> Dict[str, Dict[str, Any]]:
        """List all active connections"""
        return {
            conn_id: self.get_connection_status(conn_id)
            for conn_id in self.active_connections.keys()
        }
    
    async def shutdown(self):
        """Shutdown all connections"""
        self._running = False
        connection_ids = list(self.active_connections.keys())
        for conn_id in connection_ids:
            await self.disconnect(conn_id)
        logger.info("WebSocket Stream Manager shut down")

