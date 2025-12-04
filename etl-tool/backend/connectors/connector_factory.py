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
        """
        Detect exchange / provider name from URL.

        Rules:
        - For well-known exchanges, return a friendly canonical name (binance, okx, coinbase, etc.)
        - For any other API, derive a name from the hostname instead of returning a generic "custom"
          e.g.:
            - https://api.coingecko.com/...    -> "coingecko"
            - https://min-api.cryptocompare.com/... -> "cryptocompare"
        """
        if not url:
            return "unknown"

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
        # Strip common prefixes (api, www, min, data) and the TLD
        parts = hostname.split(".")
        if len(parts) >= 2:
            core_parts = [p for p in parts[:-1] if p not in ("api", "www", "min", "data")]
            if core_parts:
                core = core_parts[-1]
            else:
                # If everything was stripped, fall back to second‑level domain
                core = parts[-2]
        else:
            core = parts[0]

        return core or "unknown"
    
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

