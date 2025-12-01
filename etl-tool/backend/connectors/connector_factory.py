"""
Factory for creating appropriate connector instances
"""
from typing import Optional
from urllib.parse import urlparse
import logging

from connectors.rest_connector import RESTConnector
from connectors.websocket_connector import WebSocketConnector
from connectors.base_connector import BaseConnector

logger = logging.getLogger(__name__)


class ConnectorFactory:
    """Factory for creating connector instances"""
    
    @staticmethod
    def detect_protocol(url: str) -> str:
        """Detect protocol type from URL"""
        url_lower = url.lower()
        if url_lower.startswith('ws://') or url_lower.startswith('wss://'):
            return "WebSocket"
        elif url_lower.startswith('http://') or url_lower.startswith('https://'):
            return "REST"
        else:
            raise ValueError(f"Unsupported URL protocol: {url}")
    
    @staticmethod
    def detect_exchange(url: str) -> Optional[str]:
        """Detect exchange name from URL"""
        url_lower = url.lower()
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        
        if "binance" in hostname or "binance" in url_lower:
            return "binance"
        elif "okx" in hostname or "okex" in hostname or "okx" in url_lower:
            return "okx"
        elif "coinbase" in hostname or "coinbase" in url_lower:
            return "coinbase"
        elif "kraken" in hostname or "kraken" in url_lower:
            return "kraken"
        else:
            return "custom"
    
    @staticmethod
    def create_connector(
        connector_id: str,
        api_url: str,
        http_method: str = "GET",
        headers: Optional[dict] = None,
        query_params: Optional[dict] = None,
        credentials: Optional[dict] = None,
        auth_type: str = "None",
        polling_interval: int = 1000
    ) -> BaseConnector:
        """Create appropriate connector based on URL"""
        protocol = ConnectorFactory.detect_protocol(api_url)
        exchange = ConnectorFactory.detect_exchange(api_url)
        
        logger.info(f"Creating {protocol} connector for {exchange} (ID: {connector_id})")
        
        if protocol == "WebSocket":
            return WebSocketConnector(
                connector_id=connector_id,
                api_url=api_url,
                headers=headers,
                query_params=query_params,
                credentials=credentials,
                auth_type=auth_type
            )
        elif protocol == "REST":
            return RESTConnector(
                connector_id=connector_id,
                api_url=api_url,
                http_method=http_method,
                headers=headers,
                query_params=query_params,
                credentials=credentials,
                auth_type=auth_type,
                polling_interval=polling_interval
            )
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")

