"""
Pydantic models for API connector management-
Defines how API connectors should look, Validates user input before it reaches business logic
Enforces correct authentication configuration, Standardizes request, update, and response structures
Protects sensitive data from being exposed, Acts as a contract between UI → Backend → Database → Pipeline
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class AuthType(str, Enum):
    """Authentication type enumeration"""
    NONE = "None"
    API_KEY = "API Key"
    BEARER_TOKEN = "Bearer Token"
    HMAC = "HMAC"
    BASIC_AUTH = "Basic Auth"


class ConnectorStatus(str, Enum):
    """Connector status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    PAUSED = "paused"


class ProtocolType(str, Enum):
    """Protocol type enumeration"""
    REST = "REST"
    WEBSOCKET = "WebSocket"


class ConnectorCreate(BaseModel):
    """Model for creating a new connector"""
    name: str = Field(..., min_length=1, max_length=255, description="Connector name")
    api_url: str = Field(..., description="API URL (http/https for REST, ws/wss for WebSocket)")
    http_method: str = Field(default="GET", description="HTTP method (GET, POST, etc.)")
    headers: Optional[Dict[str, str]] = Field(default=None, description="HTTP headers")
    query_params: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")
    auth_type: AuthType = Field(default=AuthType.NONE, description="Authentication type")
    api_key: Optional[str] = Field(default=None, description="API key (for API Key auth)")
    api_secret: Optional[str] = Field(default=None, description="API secret (for HMAC auth)")
    bearer_token: Optional[str] = Field(default=None, description="Bearer token (for Bearer Token auth)")
    username: Optional[str] = Field(default=None, description="Username (for Basic Auth)")
    password: Optional[str] = Field(default=None, description="Password (for Basic Auth)")
    polling_interval: int = Field(default=1000, ge=100, le=60000, description="Polling interval in milliseconds (for REST)")
    
    @validator('api_url')
    def validate_url(cls, v):
        """Validate URL format"""
        if not v:
            raise ValueError("API URL is required")
        v_lower = v.lower()
        if not (v_lower.startswith('http://') or v_lower.startswith('https://') or 
                v_lower.startswith('ws://') or v_lower.startswith('wss://')):
            raise ValueError("URL must start with http://, https://, ws://, or wss://")
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_auth_credentials(cls, values):
        """Validate that required credentials are provided based on auth type"""
        auth_type = values.get('auth_type')
        
        # If auth_type is None or NONE, no validation needed
        if not auth_type or auth_type == AuthType.NONE:
            return values
        
        # Validate credentials based on auth type
        if auth_type == AuthType.API_KEY:
            api_key = values.get('api_key')
            if not api_key or (isinstance(api_key, str) and api_key.strip() == ''):
                raise ValueError("API key is required for API Key authentication")
        
        elif auth_type == AuthType.HMAC:
            api_key = values.get('api_key')
            api_secret = values.get('api_secret')
            if not api_key or (isinstance(api_key, str) and api_key.strip() == ''):
                raise ValueError("API key is required for HMAC authentication")
            if not api_secret or (isinstance(api_secret, str) and api_secret.strip() == ''):
                raise ValueError("API secret is required for HMAC authentication")
        
        elif auth_type == AuthType.BEARER_TOKEN:
            bearer_token = values.get('bearer_token')
            if not bearer_token or (isinstance(bearer_token, str) and bearer_token.strip() == ''):
                raise ValueError("Bearer token is required for Bearer Token authentication")
        
        elif auth_type == AuthType.BASIC_AUTH:
            username = values.get('username')
            password = values.get('password')
            if not username or (isinstance(username, str) and username.strip() == ''):
                raise ValueError("Username is required for Basic Auth")
            if not password or (isinstance(password, str) and password.strip() == ''):
                raise ValueError("Password is required for Basic Auth")
        
        return values


class ConnectorUpdate(BaseModel):
    """Model for updating a connector"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    api_url: Optional[str] = None
    http_method: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    auth_type: Optional[AuthType] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    bearer_token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    polling_interval: Optional[int] = Field(None, ge=100, le=60000)
    status: Optional[ConnectorStatus] = None


class ConnectorResponse(BaseModel):
    """Model for connector response (no sensitive data)"""
    id: int
    connector_id: str
    name: str
    api_url: str
    http_method: str
    auth_type: str
    status: str
    polling_interval: int
    protocol_type: Optional[str]
    exchange_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConnectorStatusResponse(BaseModel):
    """Model for connector status response"""
    connector_id: str
    status: str
    last_message_timestamp: Optional[datetime]
    message_count: int
    error_log: Optional[str]
    reconnect_attempts: int
    last_error: Optional[datetime]
    performance_metrics: Optional[Dict[str, Any]]
    updated_at: datetime
    
    class Config:
        from_attributes = True

