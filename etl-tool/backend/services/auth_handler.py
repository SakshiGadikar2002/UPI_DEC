"""
Authentication handlers for different authentication types
"""
import hmac
import hashlib
import base64
from typing import Dict, Optional
from datetime import datetime
import time


class AuthHandler:
    """Base authentication handler"""
    
    def add_auth_headers(self, headers: Dict[str, str], credentials: Dict[str, str]) -> Dict[str, str]:
        """Add authentication headers to request headers"""
        raise NotImplementedError


class APIKeyAuth(AuthHandler):
    """API Key authentication handler"""
    
    def add_auth_headers(self, headers: Dict[str, str], credentials: Dict[str, str]) -> Dict[str, str]:
        """Add API key to headers"""
        import logging
        logger = logging.getLogger(__name__)
        
        api_key = credentials.get('api_key')
        if not api_key:
            logger.error("❌ API key is missing in credentials")
            raise ValueError("API key is required for API Key authentication")
        
        # Common header names for API keys - check if already exists
        existing_api_key_headers = [k for k in headers.keys() if k.lower() in ['x-api-key', 'api-key', 'apikey']]
        
        if existing_api_key_headers:
            logger.info(f"✅ API key header already exists: {existing_api_key_headers[0]}, keeping existing")
        else:
            # Add API key to X-API-Key header (most common)
            headers['X-API-Key'] = api_key
            logger.info(f"✅ Added API key to X-API-Key header (length: {len(api_key)})")
        
        return headers


class BearerTokenAuth(AuthHandler):
    """Bearer Token authentication handler"""
    
    def add_auth_headers(self, headers: Dict[str, str], credentials: Dict[str, str]) -> Dict[str, str]:
        """Add Bearer token to Authorization header"""
        import logging
        logger = logging.getLogger(__name__)
        
        bearer_token = credentials.get('bearer_token')
        if not bearer_token:
            logger.error("❌ Bearer token is missing in credentials")
            raise ValueError("Bearer token is required for Bearer Token authentication")
        
        # Check if Authorization header already exists
        if 'Authorization' in headers:
            # If it's already a Bearer token, replace it
            if headers['Authorization'].startswith('Bearer '):
                logger.info(f"✅ Replacing existing Bearer token in Authorization header")
            else:
                logger.warning(f"⚠️ Authorization header already exists with different value, replacing with Bearer token")
        
        headers['Authorization'] = f'Bearer {bearer_token}'
        logger.info(f"✅ Added Bearer token to Authorization header (length: {len(bearer_token)})")
        return headers


class HMACAuth(AuthHandler):
    """HMAC authentication handler (for exchanges like Binance, OKX)"""
    
    def add_auth_headers(self, headers: Dict[str, str], credentials: Dict[str, str]) -> Dict[str, str]:
        """Add HMAC signature to headers"""
        api_key = credentials.get('api_key')
        api_secret = credentials.get('api_secret')
        
        if not api_key or not api_secret:
            raise ValueError("API key and secret are required for HMAC authentication")
        
        # Add API key to headers
        headers['X-MBX-APIKEY'] = api_key  # Binance format
        headers['OK-ACCESS-KEY'] = api_key  # OKX format
        
        # Generate timestamp
        timestamp = str(int(time.time() * 1000))
        headers['X-MBX-TIMESTAMP'] = timestamp  # Binance
        headers['OK-ACCESS-TIMESTAMP'] = timestamp  # OKX
        
        # For HMAC, signature is typically added to query string or request body
        # This is a simplified version - actual implementation depends on exchange
        return headers
    
    def generate_signature(self, message: str, secret: str) -> str:
        """Generate HMAC SHA256 signature"""
        return hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()


class BasicAuth(AuthHandler):
    """Basic Authentication handler"""
    
    def add_auth_headers(self, headers: Dict[str, str], credentials: Dict[str, str]) -> Dict[str, str]:
        """Add Basic Auth to Authorization header"""
        username = credentials.get('username')
        password = credentials.get('password')
        
        if not username or not password:
            raise ValueError("Username and password are required for Basic Auth")
        
        # Encode credentials in base64
        credentials_str = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials_str.encode()).decode()
        headers['Authorization'] = f'Basic {encoded_credentials}'
        
        return headers


class AuthHandlerFactory:
    """Factory for creating authentication handlers"""
    
    @staticmethod
    def create(auth_type: str) -> AuthHandler:
        """Create appropriate auth handler based on auth type"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not auth_type:
            logger.warning("Auth type is None or empty, returning None")
            return None
            
        auth_type_lower = auth_type.lower().strip()
        logger.info(f"Creating auth handler for type: '{auth_type}' (normalized: '{auth_type_lower}')")
        
        if auth_type_lower == 'none':
            logger.debug("Returning None for 'None' auth type")
            return None
        
        if 'api key' in auth_type_lower or auth_type_lower == 'apikey':
            logger.info("Creating APIKeyAuth handler")
            return APIKeyAuth()
        elif 'bearer' in auth_type_lower or 'token' in auth_type_lower:
            logger.info("Creating BearerTokenAuth handler")
            return BearerTokenAuth()
        elif 'hmac' in auth_type_lower:
            logger.info("Creating HMACAuth handler")
            return HMACAuth()
        elif 'basic' in auth_type_lower:
            logger.info("Creating BasicAuth handler")
            return BasicAuth()
        else:
            error_msg = f"Unsupported authentication type: '{auth_type}' (normalized: '{auth_type_lower}')"
            logger.error(error_msg)
            raise ValueError(error_msg)

