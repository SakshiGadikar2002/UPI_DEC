"""
Alert System API Routes
"""
from fastapi import APIRouter, HTTPException, Query, Body, Depends, Request
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from models.alert import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse,
    AlertLogResponse, AlertDashboardResponse, AlertType, AlertSeverity
)
from services.alert_manager import AlertManager
from database import get_pool

logger = logging.getLogger(__name__)

# Create router
alert_router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# Dependency to get alert manager
async def get_alert_manager():
    pool = get_pool()
    return AlertManager(pool)


@alert_router.get("/dashboard", response_model=AlertDashboardResponse)
async def get_dashboard(manager: AlertManager = Depends(get_alert_manager)):
    """Get alert system dashboard data"""
    try:
        dashboard_data = await manager.get_alert_dashboard_data()
        return dashboard_data
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.get("/rules", response_model=List[AlertRuleResponse])
async def list_alert_rules(
    enabled_only: bool = Query(False, description="Only return enabled rules"),
    manager: AlertManager = Depends(get_alert_manager)
):
    """Get all alert rules"""
    try:
        rules = await manager.get_alert_rules(enabled_only=enabled_only)
        normalized_rules = []
        for rule in rules:
            # Rename 'id' to 'rule_id' and ensure email_recipients is a list
            normalized = {**rule}
            if 'id' in normalized:
                normalized['rule_id'] = normalized.pop('id')
            # Parse email_recipients if it's a string
            if normalized.get('email_recipients') and isinstance(normalized['email_recipients'], str):
                try:
                    import json
                    normalized['email_recipients'] = json.loads(normalized['email_recipients'])
                except:
                    # If parse fails, wrap in a list
                    normalized['email_recipients'] = [normalized['email_recipients']]
            normalized_rules.append(normalized)
        return [AlertRuleResponse(**rule) for rule in normalized_rules]
    except Exception as e:
        logger.error(f"Error listing alert rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.post("/rules", response_model=Dict[str, Any])
async def create_alert_rule(
    rule: AlertRuleCreate,
    manager: AlertManager = Depends(get_alert_manager),
    request: Request = None
):
    """Create a new alert rule"""
    try:
        # Validate required fields based on alert type
        rule_dict = rule.dict()

        # Default recipient to the logged-in user's email when not provided
        current_user = getattr(request.state, "current_user", None) if request else None
        if not rule_dict.get("email_recipients") and current_user and current_user.get("email"):
            rule_dict["email_recipients"] = [current_user.get("email")]
        
        if rule.alert_type == AlertType.PRICE_THRESHOLD:
            if not rule.symbol or rule.price_threshold is None:
                raise ValueError("symbol and price_threshold are required for price_threshold alerts")
        
        elif rule.alert_type == AlertType.VOLATILITY:
            if not rule.symbol or not rule.volatility_percentage or not rule.volatility_duration_minutes:
                raise ValueError("symbol, volatility_percentage, and volatility_duration_minutes are required for volatility alerts")
        
        elif rule.alert_type == AlertType.DATA_MISSING:
            if not rule.data_missing_minutes or not rule.api_endpoint:
                raise ValueError("data_missing_minutes and api_endpoint are required for data_missing alerts")
        
        elif rule.alert_type == AlertType.SYSTEM_HEALTH:
            if not rule.health_check_type or rule.threshold_value is None:
                raise ValueError("health_check_type and threshold_value are required for system_health alerts")
        
        rule_id = await manager.create_alert_rule(rule_dict)
        
        if not rule_id:
            raise ValueError("Failed to create alert rule")
        
        return {
            "id": rule_id,
            "name": rule.name,
            "alert_type": rule.alert_type,
            "message": "Alert rule created successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: int,
    manager: AlertManager = Depends(get_alert_manager)
):
    """Get a specific alert rule"""
    try:
        rules = await manager.get_alert_rules(enabled_only=False)
        rule = next((r for r in rules if r['id'] == rule_id), None)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        return AlertRuleResponse(**rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.put("/rules/{rule_id}", response_model=Dict[str, Any])
async def update_alert_rule(
    rule_id: int,
    update_data: AlertRuleUpdate,
    manager: AlertManager = Depends(get_alert_manager)
):
    """Update an alert rule"""
    try:
        # Filter out None values
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        if not update_dict:
            raise ValueError("No fields to update")
        
        success = await manager.update_alert_rule(rule_id, update_dict)
        
        if not success:
            raise ValueError("Failed to update alert rule")
        
        return {
            "id": rule_id,
            "message": "Alert rule updated successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating alert rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.delete("/rules/{rule_id}", response_model=Dict[str, Any])
async def delete_alert_rule(
    rule_id: int,
    manager: AlertManager = Depends(get_alert_manager)
):
    """Delete an alert rule"""
    try:
        success = await manager.delete_alert_rule(rule_id)
        
        if not success:
            raise ValueError("Failed to delete alert rule")
        
        return {
            "id": rule_id,
            "message": "Alert rule deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting alert rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.get("/logs", response_model=List[AlertLogResponse])
async def get_alert_logs(
    limit: int = Query(100, ge=1, le=1000, description="Number of alerts to return"),
    rule_id: Optional[int] = Query(None, description="Filter by rule ID"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    manager: AlertManager = Depends(get_alert_manager)
):
    """Get alert history"""
    try:
        alerts = await manager.get_alert_history(limit=limit, rule_id=rule_id, severity=severity.value if severity else None)
        return [AlertLogResponse(**alert) for alert in alerts]
    except Exception as e:
        logger.error(f"Error getting alert history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.post("/logs/{alert_id}/acknowledge", response_model=Dict[str, Any])
async def acknowledge_alert(
    alert_id: int,
    manager: AlertManager = Depends(get_alert_manager)
):
    """Acknowledge an alert"""
    try:
        success = await manager.acknowledge_alert(alert_id)
        
        if not success:
            raise ValueError("Failed to acknowledge alert")
        
        return {
            "id": alert_id,
            "message": "Alert acknowledged successfully"
        }
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.post("/check", response_model=Dict[str, Any])
async def check_alerts(manager: AlertManager = Depends(get_alert_manager)):
    """Manually trigger alert checking (normally done by scheduler)"""
    try:
        results = await manager.check_and_trigger_alerts()
        return results
    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@alert_router.get("/stats", response_model=Dict[str, Any])
async def get_alert_stats(
    hours: int = Query(24, ge=1, le=720, description="Number of hours to analyze"),
    manager: AlertManager = Depends(get_alert_manager)
):
    """Get alert statistics"""
    try:
        alerts = await manager.get_alert_history(limit=10000)
        
        # Filter by time period
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_alerts = [a for a in alerts if datetime.fromisoformat(a['created_at'].replace('Z', '+00:00')) >= cutoff]
        
        # Calculate stats
        severity_counts = {}
        type_counts = {}
        hourly_distribution = {}
        
        for alert in recent_alerts:
            # Count by severity
            severity = alert.get('severity', 'unknown')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by type
            alert_type = alert.get('alert_type', 'unknown')
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
            
            # Hourly distribution
            created_at = datetime.fromisoformat(alert['created_at'].replace('Z', '+00:00'))
            hour_key = created_at.strftime('%Y-%m-%d %H:00')
            hourly_distribution[hour_key] = hourly_distribution.get(hour_key, 0) + 1
        
        return {
            'period_hours': hours,
            'total_alerts': len(recent_alerts),
            'by_severity': severity_counts,
            'by_type': type_counts,
            'hourly_distribution': hourly_distribution
        }
    except Exception as e:
        logger.error(f"Error getting alert stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
