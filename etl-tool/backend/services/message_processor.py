"""
Message processor for transforming and routing incoming data
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Processes incoming messages from connectors"""
    
    def __init__(self, db_callback=None, websocket_callback=None):
        """
        Initialize message processor
        
        Args:
            db_callback: Async function to save data to database
            websocket_callback: Async function to broadcast to WebSocket clients
        """
        self.db_callback = db_callback
        self.websocket_callback = websocket_callback
    
    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming message
        
        Args:
            message: Raw message from connector
            
        Returns:
            Normalized message data
        """
        try:
            # Extract and normalize data
            normalized = self._normalize(message)
            
            # Save to database if callback provided
            if self.db_callback:
                try:
                    await self.db_callback(normalized)
                except Exception as e:
                    logger.error(f"Error saving to database: {e}")
            
            # Broadcast to WebSocket clients if callback provided
            if self.websocket_callback:
                try:
                    await self.websocket_callback(normalized)
                except Exception as e:
                    logger.error(f"Error broadcasting to WebSocket: {e}")
            
            return normalized
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            raise
    
    def _normalize(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize message to standard format"""
        exchange = message.get("exchange", "custom")
        data = message.get("data", {})
        connector_id = message.get("connector_id", "unknown")
        timestamp = message.get("timestamp", datetime.utcnow().isoformat())
        message_type = message.get("message_type", "trade")
        
        # Extract instrument and price
        instrument = self._extract_instrument(data, exchange)
        price = self._extract_price(data, exchange)
        
        return {
            "exchange": exchange,
            "instrument": instrument,
            "price": price,
            "data": data,
            "message_type": message_type,
            "timestamp": timestamp,
            "connector_id": connector_id
        }
    
    def _extract_instrument(self, data: Any, exchange: str) -> Optional[str]:
        """Extract instrument/symbol from data"""
        if not data or not isinstance(data, dict):
            return None
        
        # Binance format
        if exchange == "binance":
            if "s" in data:
                symbol = data["s"]
                # Format BTCUSDT -> BTC-USDT
                if len(symbol) == 6:
                    return f"{symbol[:3]}-{symbol[3:]}"
                return symbol
            if "stream" in data:
                symbol = data["stream"].split("@")[0].upper()
                if len(symbol) == 6:
                    return f"{symbol[:3]}-{symbol[3:]}"
                return symbol
        
        # OKX format
        elif exchange == "okx":
            if "arg" in data and isinstance(data["arg"], dict):
                inst_id = data["arg"].get("instId")
                if inst_id:
                    return inst_id
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                trade = data["data"][0]
                if isinstance(trade, dict) and "instId" in trade:
                    return trade["instId"]
        
        # Generic formats
        for key in ["instrument", "symbol", "pair", "instId", "inst_id"]:
            if key in data:
                return str(data[key])
        
        return None
    
    def _extract_price(self, data: Any, exchange: str) -> Optional[float]:
        """Extract price from data"""
        if not data:
            return None
        
        def find_price(obj, depth=0, max_depth=5):
            """Recursively find price in nested structure"""
            if not obj or depth > max_depth:
                return None
            
            if isinstance(obj, dict):
                # Try common price field names
                for price_field in ["px", "p", "last", "c", "price", "close", "lastPrice", "tradePrice"]:
                    if price_field in obj and obj[price_field] is not None:
                        try:
                            price_val = obj[price_field]
                            if isinstance(price_val, str):
                                price_val = price_val.strip()
                                if price_val and price_val not in ["null", "None", ""]:
                                    return float(price_val)
                            elif isinstance(price_val, (int, float)):
                                return float(price_val)
                        except (ValueError, TypeError):
                            continue
                
                # Recursively search nested structures
                if "data" in obj:
                    nested_price = find_price(obj["data"], depth + 1, max_depth)
                    if nested_price is not None:
                        return nested_price
                
                for key, value in obj.items():
                    if key not in ["arg", "stream", "event", "op", "id"]:
                        nested_price = find_price(value, depth + 1, max_depth)
                        if nested_price is not None:
                            return nested_price
            
            elif isinstance(obj, list) and len(obj) > 0:
                # Check first element
                nested_price = find_price(obj[0], depth + 1, max_depth)
                if nested_price is not None:
                    return nested_price
        
        return find_price(data)

