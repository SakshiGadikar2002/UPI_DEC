"""
Pydantic models for WebSocket data storage
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class WebSocketMessage(BaseModel):
    """Model for a single WebSocket message"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    exchange: str  # 'okx', 'binance', 'custom'
    instrument: Optional[str] = None
    price: Optional[float] = None
    data: Dict[str, Any]
    message_type: str = "trade"  # 'trade', 'system', 'error'
    latency_ms: Optional[float] = None


class WebSocketBatch(BaseModel):
    """Model for batch WebSocket data"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    exchange: str
    total_messages: int
    messages_per_second: float
    instruments: List[str]
    messages: List[Dict[str, Any]]
    metrics: Dict[str, Any]  # latency, throughput, etc.


