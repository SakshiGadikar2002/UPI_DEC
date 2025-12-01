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
        api_key = credentials.get('api_key')
        if not api_key:
            raise ValueError("API key is required for API Key authentication")
        
        # Common header names for API keys
        if 'X-API-Key' not in headers and 'x-api-key' not in headers.lower():
            headers['X-API-Key'] = api_key
        
        return headers


class BearerTokenAuth(AuthHandler):
    """Bearer Token authentication handler"""
    
    def add_auth_headers(self, headers: Dict[str, str], credentials: Dict[str, str]) -> Dict[str, str]:
        """Add Bearer token to Authorization header"""
        bearer_token = credentials.get('bearer_token')
        if not bearer_token:
            raise ValueError("Bearer token is required for Bearer Token authentication")
        
        headers['Authorization'] = f'Bearer {bearer_token}'
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
        auth_type_lower = auth_type.lower()
        
        if auth_type_lower == 'none' or not auth_type:
            return None
        
        if 'api key' in auth_type_lower or auth_type_lower == 'apikey':
            return APIKeyAuth()
        elif 'bearer' in auth_type_lower or 'token' in auth_type_lower:
            return BearerTokenAuth()
        elif 'hmac' in auth_type_lower:
            return HMACAuth()
        elif 'basic' in auth_type_lower:
            return BasicAuth()
        else:
            raise ValueError(f"Unsupported authentication type: {auth_type}")

