"""
Connector manager for managing lifecycle of all connectors
"""
from typing import Dict, Optional
import asyncio
import logging
from datetime import datetime
import uuid

from connectors.base_connector import BaseConnector
from connectors.connector_factory import ConnectorFactory
from services.message_processor import MessageProcessor
from database import get_pool
import json

logger = logging.getLogger(__name__)


class ConnectorManager:
    """Manages all active connectors"""
    
    def __init__(self, message_processor: MessageProcessor):
        self.connectors: Dict[str, BaseConnector] = {}
        self.message_processor = message_processor
        self._lock = asyncio.Lock()
    
    async def create_connector(
        self,
        connector_id: str,
        api_url: str,
        http_method: str = "GET",
        headers: Optional[dict] = None,
        query_params: Optional[dict] = None,
        credentials: Optional[dict] = None,
        auth_type: str = "None",
        polling_interval: int = 1000
    ) -> BaseConnector:
        """Create a new connector instance"""
        async with self._lock:
            if connector_id in self.connectors:
                raise ValueError(f"Connector {connector_id} already exists")
            
            connector = ConnectorFactory.create_connector(
                connector_id=connector_id,
                api_url=api_url,
                http_method=http_method,
                headers=headers,
                query_params=query_params,
                credentials=credentials,
                auth_type=auth_type,
                polling_interval=polling_interval
            )
            
            self.connectors[connector_id] = connector
            logger.info(f"✅ Created connector: {connector_id}")
            return connector
    
    async def start_connector(self, connector_id: str) -> bool:
        """Start a connector"""
        async with self._lock:
            if connector_id not in self.connectors:
                raise ValueError(f"Connector {connector_id} not found")
            
            connector = self.connectors[connector_id]
            
            if connector.status == "running":
                logger.warning(f"Connector {connector_id} is already running")
                return True
            
            try:
                await connector.start(self._on_message)
                await self._update_status_in_db(connector_id, "running")
                return True
            except Exception as e:
                logger.error(f"Failed to start connector {connector_id}: {e}")
                await self._update_status_in_db(connector_id, "error", str(e))
                raise
    
    async def stop_connector(self, connector_id: str) -> bool:
        """Stop a connector"""
        async with self._lock:
            if connector_id not in self.connectors:
                raise ValueError(f"Connector {connector_id} not found")
            
            connector = self.connectors[connector_id]
            
            try:
                await connector.stop()
                await self._update_status_in_db(connector_id, "stopped")
                return True
            except Exception as e:
                logger.error(f"Failed to stop connector {connector_id}: {e}")
                raise
    
    async def delete_connector(self, connector_id: str) -> bool:
        """Delete a connector"""
        async with self._lock:
            if connector_id in self.connectors:
                connector = self.connectors[connector_id]
                if connector.status == "running":
                    await connector.stop()
                del self.connectors[connector_id]
            
            logger.info(f"🗑️ Deleted connector: {connector_id}")
            return True
    
    async def get_connector(self, connector_id: str) -> Optional[BaseConnector]:
        """Get connector by ID"""
        return self.connectors.get(connector_id)
    
    async def get_all_connectors(self) -> Dict[str, BaseConnector]:
        """Get all connectors"""
        return self.connectors.copy()
    
    async def get_connector_status(self, connector_id: str) -> Optional[Dict]:
        """Get connector status"""
        if connector_id not in self.connectors:
            return None
        
        connector = self.connectors[connector_id]
        return connector.get_status()
    
    async def _on_message(self, message: Dict):
        """Handle message from connector"""
        try:
            logger.info(f"Connector {message.get('connector_id', 'unknown')} received message")
            await self.message_processor.process(message)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
    
    async def _update_status_in_db(self, connector_id: str, status: str, error_log: Optional[str] = None):
        """Update connector status in database"""
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                # Check if status record exists
                existing = await conn.fetchrow(
                    "SELECT id FROM connector_status WHERE connector_id = $1",
                    connector_id
                )
                
                if existing:
                    # Update existing
                    await conn.execute("""
                        UPDATE connector_status 
                        SET status = $1, error_log = $2, updated_at = $3
                        WHERE connector_id = $4
                    """, status, error_log, datetime.utcnow(), connector_id)
                else:
                    # Create new
                    await conn.execute("""
                        INSERT INTO connector_status 
                        (connector_id, status, error_log, updated_at)
                        VALUES ($1, $2, $3, $4)
                    """, connector_id, status, error_log, datetime.utcnow())
        except Exception as e:
            logger.error(f"Error updating status in DB: {e}")


# Global connector manager instance
_connector_manager: Optional[ConnectorManager] = None


def get_connector_manager(message_processor: Optional[MessageProcessor] = None) -> ConnectorManager:
    """Get or create global connector manager"""
    global _connector_manager
    if _connector_manager is None:
        # Message processor will be initialized with callbacks later
        if message_processor is None:
            message_processor = MessageProcessor()
        _connector_manager = ConnectorManager(message_processor)
    elif message_processor is not None:
        # Update message processor if provided
        _connector_manager.message_processor = message_processor
    return _connector_manager

