"""
Pydantic models for Alert System
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class AlertType(str, Enum):
    """Alert type enumeration"""
    PRICE_THRESHOLD = "price_threshold"
    VOLATILITY = "volatility"
    DATA_MISSING = "data_missing"
    SYSTEM_HEALTH = "system_health"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status enumeration"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class NotificationChannel(str, Enum):
    """Notification channel enumeration"""
    EMAIL = "email"
    SLACK = "slack"
    BOTH = "both"
    NONE = "none"


class AlertRuleCreate(BaseModel):
    """Model for creating alert rules"""
    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    alert_type: AlertType = Field(..., description="Type of alert")
    enabled: bool = Field(default=True, description="Whether rule is enabled")
    description: Optional[str] = Field(default=None, description="Rule description")
    
    # Price threshold alert parameters
    symbol: Optional[str] = Field(default=None, description="Symbol (e.g., BTC, ETH)")
    price_threshold: Optional[float] = Field(default=None, ge=0, description="Price threshold")
    price_comparison: Optional[str] = Field(default="greater", description="Comparison: greater, less, equal")
    
    # Volatility alert parameters
    volatility_percentage: Optional[float] = Field(default=None, ge=0, description="Volatility percentage (e.g., 5 for 5%)")
    volatility_duration_minutes: Optional[int] = Field(default=None, ge=1, description="Duration window in minutes")
    
    # Data missing alert parameters
    data_missing_minutes: Optional[int] = Field(default=None, ge=1, description="Minutes before data is considered missing")
    api_endpoint: Optional[str] = Field(default=None, description="API endpoint to monitor")
    
    # System health alert parameters
    health_check_type: Optional[str] = Field(default=None, description="Type: db_connection, disk_space, api_health")
    threshold_value: Optional[float] = Field(default=None, description="Threshold value for health check")
    
    # Notification settings
    notification_channels: NotificationChannel = Field(default=NotificationChannel.EMAIL, description="Where to send alerts")
    email_recipients: Optional[List[str]] = Field(default=None, description="Email addresses to notify")
    slack_webhook_url: Optional[str] = Field(default=None, description="Slack webhook URL")
    
    # Alert settings
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING, description="Alert severity")
    cooldown_minutes: int = Field(default=5, ge=1, description="Cooldown period before next alert (in minutes)")
    max_alerts_per_day: Optional[int] = Field(default=None, description="Max alerts per day (None = unlimited)")


class AlertRuleUpdate(BaseModel):
    """Model for updating alert rules"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    enabled: Optional[bool] = None
    description: Optional[str] = None
    price_threshold: Optional[float] = Field(None, ge=0)
    price_comparison: Optional[str] = None
    volatility_percentage: Optional[float] = Field(None, ge=0)
    volatility_duration_minutes: Optional[int] = Field(None, ge=1)
    data_missing_minutes: Optional[int] = Field(None, ge=1)
    notification_channels: Optional[NotificationChannel] = None
    email_recipients: Optional[List[str]] = None
    slack_webhook_url: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1)
    max_alerts_per_day: Optional[int] = None


class AlertRuleResponse(BaseModel):
    """Model for alert rule response"""
    rule_id: int
    name: str
    alert_type: AlertType
    enabled: bool
    description: Optional[str]
    symbol: Optional[str]
    price_threshold: Optional[float]
    price_comparison: Optional[str]
    volatility_percentage: Optional[float]
    volatility_duration_minutes: Optional[int]
    data_missing_minutes: Optional[int]
    api_endpoint: Optional[str]
    health_check_type: Optional[str]
    threshold_value: Optional[float]
    notification_channels: NotificationChannel
    email_recipients: Optional[List[str]]
    severity: AlertSeverity
    cooldown_minutes: int
    max_alerts_per_day: Optional[int]
    created_at: datetime
    updated_at: datetime


class AlertLogCreate(BaseModel):
    """Model for creating alert logs"""
    rule_id: int = Field(..., description="Rule ID that triggered")
    alert_type: AlertType = Field(..., description="Type of alert")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING)
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")


class AlertLogResponse(BaseModel):
    """Model for alert log response"""
    alert_id: int
    rule_id: int
    alert_type: AlertType
    title: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    sent_at: Optional[datetime]
    acknowledged_at: Optional[datetime]


class AlertThresholdResponse(BaseModel):
    """Model for viewing alert thresholds"""
    rule_id: int
    symbol: Optional[str]
    current_price: Optional[float]
    threshold_price: Optional[float]
    last_checked: datetime
    alert_status: str


class AlertDashboardResponse(BaseModel):
    """Model for alert dashboard data"""
    total_rules: int
    active_rules: int
    inactive_rules: int
    total_alerts_today: int
    critical_alerts: int
    warning_alerts: int
    recent_alerts: List[AlertLogResponse]
    triggered_rules: List[AlertRuleResponse]
    system_health: Optional[Dict[str, Any]]
