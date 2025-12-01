"""
Base connector class for API connections
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import asyncio
import logging


logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Abstract base class for all connectors"""
    
    def __init__(
        self,
        connector_id: str,
        api_url: str,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, str]] = None,
        auth_type: str = "None"
    ):
        self.connector_id = connector_id
        self.api_url = api_url
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.credentials = credentials or {}
        self.auth_type = auth_type
        self.status = "stopped"
        self.message_count = 0
        self.last_message_timestamp: Optional[datetime] = None
        self.error_log: Optional[str] = None
        self.reconnect_attempts = 0
        self.last_error: Optional[datetime] = None
        self.message_callback: Optional[Callable] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to API"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection to API"""
        pass
    
    @abstractmethod
    async def process_message(self, message: Any) -> Dict[str, Any]:
        """Process incoming message and return normalized data"""
        pass
    
    async def start(self, message_callback: Callable):
        """Start the connector"""
        if self._running:
            logger.warning(f"Connector {self.connector_id} is already running")
            return
        
        self.message_callback = message_callback
        self.status = "running"
        self._running = True
        self.reconnect_attempts = 0
        
        try:
            connected = await self.connect()
            if connected:
                self._task = asyncio.create_task(self._run())
                logger.info(f"✅ Connector {self.connector_id} started successfully")
            else:
                self.status = "error"
                self._running = False
                logger.error(f"❌ Failed to connect {self.connector_id}")
        except Exception as e:
            self.status = "error"
            self._running = False
            self.error_log = str(e)
            self.last_error = datetime.utcnow()
            logger.error(f"❌ Error starting connector {self.connector_id}: {e}")
            raise
    
    async def stop(self):
        """Stop the connector"""
        if not self._running:
            return
        
        self._running = False
        self.status = "stopped"
        
        try:
            await self.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting {self.connector_id}: {e}")
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"🛑 Connector {self.connector_id} stopped")
    
    async def _run(self):
        """Main run loop (to be implemented by subclasses)"""
        try:
            await self._run_loop()
        except asyncio.CancelledError:
            logger.info(f"Connector {self.connector_id} task cancelled")
        except Exception as e:
            self.status = "error"
            self.error_log = str(e)
            self.last_error = datetime.utcnow()
            logger.error(f"❌ Error in connector {self.connector_id} run loop: {e}")
            await self.handle_error(e)
    
    @abstractmethod
    async def _run_loop(self):
        """Main processing loop (implemented by subclasses)"""
        pass
    
    async def handle_error(self, error: Exception):
        """Handle errors and attempt reconnection"""
        self.last_error = datetime.utcnow()
        self.error_log = str(error)
        logger.error(f"Error in connector {self.connector_id}: {error}")
        
        # Attempt reconnection with exponential backoff
        if self._running:
            await self.reconnect()
    
    async def reconnect(self):
        """Reconnect with exponential backoff"""
        max_attempts = 5
        base_delay = 1  # seconds
        
        while self.reconnect_attempts < max_attempts and self._running:
            self.reconnect_attempts += 1
            delay = base_delay * (2 ** (self.reconnect_attempts - 1))
            
            logger.info(f"Reconnecting {self.connector_id} (attempt {self.reconnect_attempts}/{max_attempts}) in {delay}s...")
            await asyncio.sleep(delay)
            
            try:
                await self.disconnect()
                connected = await self.connect()
                if connected:
                    self.reconnect_attempts = 0
                    self.status = "running"
                    logger.info(f"✅ Reconnected {self.connector_id} successfully")
                    return
            except Exception as e:
                logger.error(f"Reconnection attempt {self.reconnect_attempts} failed: {e}")
        
        if self.reconnect_attempts >= max_attempts:
            self.status = "error"
            self._running = False
            logger.error(f"❌ Max reconnection attempts reached for {self.connector_id}")
    
    async def _on_message(self, message: Any):
        """Handle incoming message"""
        try:
            processed = await self.process_message(message)
            self.message_count += 1
            self.last_message_timestamp = datetime.utcnow()
            
            if self.message_callback:
                await self.message_callback(processed)
        except Exception as e:
            logger.error(f"Error processing message in {self.connector_id}: {e}")
            await self.handle_error(e)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current connector status"""
        return {
            "connector_id": self.connector_id,
            "status": self.status,
            "message_count": self.message_count,
            "last_message_timestamp": self.last_message_timestamp.isoformat() if self.last_message_timestamp else None,
            "error_log": self.error_log,
            "reconnect_attempts": self.reconnect_attempts,
            "last_error": self.last_error.isoformat() if self.last_error else None
        }

