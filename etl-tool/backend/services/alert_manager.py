"""
Alert Manager - Orchestrates alert checking and logging
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal
import json

from services.alert_checker import AlertConditionEvaluator
from services.notification_service import NotificationService
from services.crypto_alert_engine import CryptoAlertManager

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert rules, checking, and triggering"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.evaluator = AlertConditionEvaluator(db_pool)
        self.notification_service = NotificationService(db_pool)
        self.crypto_alert_manager = CryptoAlertManager()
    
    async def get_alert_rules(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get alert rules from database
        
        Args:
            enabled_only: Only return enabled rules
        
        Returns:
            List of alert rules
        """
        try:
            async with self.db_pool.acquire() as conn:
                query = "SELECT * FROM alert_rules"
                if enabled_only:
                    query += " WHERE enabled = TRUE"
                query += " ORDER BY created_at DESC"
                
                rules = await conn.fetch(query)
                return [dict(r) for r in rules]
        except Exception as e:
            logger.error(f"Error getting alert rules: {e}")
            return []
    
    async def create_alert_rule(self, rule_data: Dict[str, Any]) -> Optional[int]:
        """
        Create a new alert rule
        
        Args:
            rule_data: Rule data dictionary
        
        Returns:
            Rule ID or None
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Parse email_recipients if it's a list
                email_recipients = rule_data.get('email_recipients')
                if isinstance(email_recipients, list):
                    email_recipients = ','.join(email_recipients)
                
                rule_id = await conn.fetchval("""
                    INSERT INTO alert_rules (
                        name, alert_type, enabled, description,
                        symbol, price_threshold, price_comparison,
                        volatility_percentage, volatility_duration_minutes,
                        data_missing_minutes, api_endpoint,
                        health_check_type, threshold_value,
                        notification_channels, email_recipients, slack_webhook_url,
                        severity, cooldown_minutes, max_alerts_per_day,
                        created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                        $12, $13, $14, $15, $16, $17, $18, $19, NOW(), NOW()
                    )
                    RETURNING id
                """,
                    rule_data.get('name'),
                    rule_data.get('alert_type'),
                    rule_data.get('enabled', True),
                    rule_data.get('description'),
                    rule_data.get('symbol'),
                    Decimal(str(rule_data.get('price_threshold', 0))) if rule_data.get('price_threshold') else None,
                    rule_data.get('price_comparison'),
                    Decimal(str(rule_data.get('volatility_percentage', 0))) if rule_data.get('volatility_percentage') else None,
                    rule_data.get('volatility_duration_minutes'),
                    rule_data.get('data_missing_minutes'),
                    rule_data.get('api_endpoint'),
                    rule_data.get('health_check_type'),
                    Decimal(str(rule_data.get('threshold_value', 0))) if rule_data.get('threshold_value') else None,
                    rule_data.get('notification_channels', 'email'),
                    email_recipients,
                    rule_data.get('slack_webhook_url'),
                    rule_data.get('severity', 'warning'),
                    rule_data.get('cooldown_minutes', 5),
                    rule_data.get('max_alerts_per_day')
                )
                
                # Initialize alert tracking
                await conn.execute("""
                    INSERT INTO alert_tracking (rule_id, last_alert_time, alert_count_today)
                    VALUES ($1, NULL, 0)
                """, rule_id)
                
                logger.info(f"Created alert rule {rule_id}: {rule_data.get('name')}")
                return rule_id
        except Exception as e:
            logger.error(f"Error creating alert rule: {e}")
            return None
    
    async def update_alert_rule(self, rule_id: int, rule_data: Dict[str, Any]) -> bool:
        """
        Update an alert rule
        
        Args:
            rule_id: Rule ID
            rule_data: Updated rule data
        
        Returns:
            Success status
        """
        try:
            # Build dynamic update query
            updates = []
            params = []
            param_idx = 1
            
            for key, value in rule_data.items():
                if key == 'email_recipients' and isinstance(value, list):
                    value = ','.join(value)
                
                if key in [
                    'name', 'alert_type', 'enabled', 'description',
                    'symbol', 'price_comparison', 'api_endpoint',
                    'health_check_type', 'notification_channels',
                    'email_recipients', 'slack_webhook_url', 'severity'
                ]:
                    updates.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
                elif key in [
                    'price_threshold', 'volatility_percentage', 'threshold_value'
                ] and value is not None:
                    updates.append(f"{key} = ${param_idx}")
                    params.append(Decimal(str(value)))
                    param_idx += 1
                elif key in [
                    'volatility_duration_minutes', 'data_missing_minutes',
                    'cooldown_minutes', 'max_alerts_per_day'
                ] and value is not None:
                    updates.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1
            
            if not updates:
                return True
            
            updates.append(f"updated_at = NOW()")
            params.append(rule_id)
            
            query = f"UPDATE alert_rules SET {', '.join(updates)} WHERE id = ${param_idx}"
            
            async with self.db_pool.acquire() as conn:
                await conn.execute(query, *params)
            
            logger.info(f"Updated alert rule {rule_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating alert rule {rule_id}: {e}")
            return False
    
    async def delete_alert_rule(self, rule_id: int) -> bool:
        """
        Delete an alert rule
        
        Args:
            rule_id: Rule ID
        
        Returns:
            Success status
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("DELETE FROM alert_rules WHERE id = $1", rule_id)
            
            logger.info(f"Deleted alert rule {rule_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting alert rule {rule_id}: {e}")
            return False
    
    async def check_and_trigger_alerts(self) -> Dict[str, Any]:
        """
        Check all enabled alert rules and trigger alerts if conditions are met
        
        Returns:
            Dictionary with check results
        """
        results = {
            'checked': 0,
            'triggered': 0,
            'errors': 0,
            'alerts': []
        }
        
        try:
            rules = await self.get_alert_rules(enabled_only=True)
            
            for rule in rules:
                try:
                    # Check if we should skip based on cooldown
                    should_trigger, skip_reason = await self._check_cooldown(rule['id'])
                    if not should_trigger:
                        logger.debug(f"Skipping rule {rule['id']}: {skip_reason}")
                        continue
                    
                    results['checked'] += 1
                    
                    # Evaluate rule condition
                    triggered, message, metadata = await self.evaluator.evaluate_rule(rule)
                    logger.debug(f"Evaluation result for rule {rule.get('id')}: triggered={triggered}, message={message}, metadata={metadata}")
                    
                    if triggered:
                        # Create alert log
                        try:
                            alert_id = await self._create_alert_log(
                                rule['id'],
                                rule['alert_type'],
                                rule.get('name', 'Alert'),
                                message or 'Alert triggered',
                                rule.get('severity', 'warning'),
                                metadata
                            )
                        except Exception as e:
                            logger.exception(f"Failed to create alert log for rule {rule.get('id')}: {e}")
                            alert_id = None

                        logger.debug(f"_create_alert_log returned alert_id={alert_id} for rule {rule.get('id')}")

                        if alert_id:
                            results['triggered'] += 1
                            results['alerts'].append({
                                'alert_id': alert_id,
                                'rule_id': rule['id'],
                                'message': message
                            })

                            # Send notifications (guarded)
                            try:
                                notification_result = await self.notification_service.send_alert(
                                    alert_id,
                                    rule,
                                    title=rule.get('name', 'Alert'),
                                    message=message or 'Alert triggered',
                                    severity=rule.get('severity', 'warning'),
                                    metadata=metadata
                                )
                            except Exception as e:
                                logger.exception(f"Failed to send notification for alert {alert_id}: {e}")

                            logger.info(f"Alert triggered: {rule['name']} (ID: {alert_id})")
                
                except Exception as e:
                    logger.error(f"Error checking rule {rule.get('id')}: {e}")
                    results['errors'] += 1
            
            logger.info(f"Alert check completed: {results['checked']} checked, {results['triggered']} triggered")
            return results
        except Exception as e:
            logger.error(f"Error in alert checking: {e}")
            results['errors'] += 1
            return results
    
    async def _check_cooldown(self, rule_id: int) -> tuple[bool, Optional[str]]:
        """
        Check if rule is in cooldown period
        
        Args:
            rule_id: Rule ID
        
        Returns:
            Tuple of (should_check: bool, reason: Optional[str])
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get rule and tracking info
                rule = await conn.fetchrow("""
                    SELECT cooldown_minutes, max_alerts_per_day
                    FROM alert_rules
                    WHERE id = $1
                """, rule_id)
                
                tracking = await conn.fetchrow("""
                    SELECT last_alert_time, alert_count_today, last_alert_date
                    FROM alert_tracking
                    WHERE rule_id = $1
                """, rule_id)
                
                if not rule or not tracking:
                    return True, None
                
                # Check max alerts per day
                if rule['max_alerts_per_day']:
                    today = datetime.utcnow().date()
                    if tracking['last_alert_date'] == today and tracking['alert_count_today'] >= rule['max_alerts_per_day']:
                        return False, f"Max alerts per day ({rule['max_alerts_per_day']}) reached"
                
                # Check cooldown
                if tracking['last_alert_time']:
                    cooldown_until = tracking['last_alert_time'] + timedelta(minutes=rule['cooldown_minutes'])
                    if datetime.utcnow() < cooldown_until:
                        return False, f"In cooldown until {cooldown_until}"
                
                return True, None
        except Exception as e:
            logger.error(f"Error checking cooldown: {e}")
            return True, None
    
    async def _create_alert_log(self, rule_id: int, alert_type: str, title: str,
                               message: str, severity: str, metadata: Optional[Dict] = None) -> Optional[int]:
        """
        Create alert log entry
        
        Args:
            rule_id: Rule ID
            alert_type: Alert type
            title: Alert title
            message: Alert message
            severity: Alert severity
            metadata: Additional metadata
        
        Returns:
            Alert ID or None
        """
        try:
            async with self.db_pool.acquire() as conn:
                alert_id = await conn.fetchval("""
                    INSERT INTO alert_logs
                    (rule_id, alert_type, title, message, severity, status, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, 'pending', $6, NOW())
                    RETURNING id
                """,
                    rule_id, alert_type, title, message, severity,
                    None if metadata is None else json.dumps(metadata, default=str)
                )

                logger.debug(f"Inserted alert_logs record id={alert_id} for rule_id={rule_id}")

                # Update alert tracking
                today = datetime.utcnow().date()
                await conn.execute("""
                    UPDATE alert_tracking
                    SET last_alert_time = NOW(),
                        alert_count_today = CASE
                            WHEN last_alert_date = $2 THEN alert_count_today + 1
                            ELSE 1
                        END,
                        last_alert_date = $2
                    WHERE rule_id = $1
                """, rule_id, today)
                
                return alert_id
        except Exception as e:
            logger.error(f"Error creating alert log: {e}")
            return None
    
    async def acknowledge_alert(self, alert_id: int) -> bool:
        """
        Acknowledge an alert
        
        Args:
            alert_id: Alert ID
        
        Returns:
            Success status
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE alert_logs
                    SET status = 'acknowledged', acknowledged_at = NOW()
                    WHERE id = $1
                """, alert_id)
                return True
        except Exception as e:
            logger.error(f"Error acknowledging alert {alert_id}: {e}")
            return False
    
    async def get_alert_history(self, limit: int = 100, rule_id: Optional[int] = None,
                               severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get alert history
        
        Args:
            limit: Maximum number of alerts to return
            rule_id: Filter by rule ID
            severity: Filter by severity
        
        Returns:
            List of alerts
        """
        try:
            async with self.db_pool.acquire() as conn:
                query = "SELECT * FROM alert_logs WHERE 1=1"
                params = []
                
                if rule_id:
                    query += f" AND rule_id = ${len(params) + 1}"
                    params.append(rule_id)
                
                if severity:
                    query += f" AND severity = ${len(params) + 1}"
                    params.append(severity)
                
                query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1)
                params.append(limit)
                
                alerts = await conn.fetch(query, *params)

                normalized = []
                for a in alerts:
                    # Ensure metadata is a dict (JSONB may be returned as str)
                    md = a.get('metadata')
                    if isinstance(md, str):
                        try:
                            md = json.loads(md)
                        except Exception:
                            md = None

                    normalized.append({
                        'alert_id': a.get('id'),
                        'rule_id': a.get('rule_id'),
                        'alert_type': a.get('alert_type'),
                        'title': a.get('title'),
                        'message': a.get('message'),
                        'severity': a.get('severity'),
                        'status': a.get('status'),
                        'metadata': md,
                        'created_at': a.get('created_at'),
                        'sent_at': a.get('sent_at'),
                        'acknowledged_at': a.get('acknowledged_at')
                    })

                return normalized
        except Exception as e:
            logger.error(f"Error getting alert history: {e}")
            return []
    
    async def get_alert_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for alert dashboard
        
        Returns:
            Dashboard data
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Count rules
                total_rules = await conn.fetchval("SELECT COUNT(*) FROM alert_rules")
                active_rules = await conn.fetchval("SELECT COUNT(*) FROM alert_rules WHERE enabled = TRUE")
                
                # Count alerts today
                today = datetime.utcnow().date()
                alerts_today = await conn.fetchval("""
                    SELECT COUNT(*) FROM alert_logs
                    WHERE DATE(created_at) = $1
                """, today)
                
                # Count critical alerts
                critical_alerts = await conn.fetchval("""
                    SELECT COUNT(*) FROM alert_logs
                    WHERE severity = 'critical' AND created_at >= NOW() - INTERVAL '24 hours'
                """)
                
                # Count warning alerts
                warning_alerts = await conn.fetchval("""
                    SELECT COUNT(*) FROM alert_logs
                    WHERE severity = 'warning' AND created_at >= NOW() - INTERVAL '24 hours'
                """)
                
                # Recent alerts
                recent_alerts = await conn.fetch("""
                    SELECT id, rule_id, alert_type, title, message, severity, status, created_at, sent_at, acknowledged_at
                    FROM alert_logs
                    ORDER BY created_at DESC
                    LIMIT 10
                """)

                # Normalize recent alerts to AlertLogResponse shape
                recent_normalized = []
                for a in recent_alerts:
                    recent_normalized.append({
                        'alert_id': a.get('id'),
                        'rule_id': a.get('rule_id'),
                        'alert_type': a.get('alert_type'),
                        'title': a.get('title'),
                        'message': a.get('message'),
                        'severity': a.get('severity'),
                        'status': a.get('status'),
                        'metadata': None,
                        'created_at': a.get('created_at'),
                        'sent_at': a.get('sent_at'),
                        'acknowledged_at': a.get('acknowledged_at')
                    })

                # Triggered rules (recent)
                # Use aggregation to get most-recent trigger time per rule and order by that
                triggered_rules = await conn.fetch("""
                    SELECT r.id, r.name, r.alert_type, r.severity, MAX(l.created_at) as last_created
                    FROM alert_rules r
                    INNER JOIN alert_logs l ON r.id = l.rule_id
                    WHERE l.created_at >= NOW() - INTERVAL '1 hour'
                    GROUP BY r.id, r.name, r.alert_type, r.severity
                    ORDER BY last_created DESC
                    LIMIT 5
                """)

                # Normalize triggered rules to AlertRuleResponse shape (partial fields)
                triggered_normalized = []
                for r in triggered_rules:
                    triggered_normalized.append({
                        'rule_id': r.get('id'),
                        'name': r.get('name'),
                        'alert_type': r.get('alert_type'),
                        'enabled': True,
                        'description': None,
                        'symbol': None,
                        'price_threshold': None,
                        'price_comparison': None,
                        'volatility_percentage': None,
                        'volatility_duration_minutes': None,
                        'data_missing_minutes': None,
                        'api_endpoint': None,
                        'health_check_type': None,
                        'threshold_value': None,
                        'notification_channels': 'email',
                        'email_recipients': None,
                        'severity': r.get('severity'),
                        'cooldown_minutes': 0,
                        'max_alerts_per_day': None,
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    })

                return {
                    'total_rules': total_rules,
                    'active_rules': active_rules,
                    'inactive_rules': total_rules - active_rules,
                    'total_alerts_today': alerts_today,
                    'critical_alerts': critical_alerts,
                    'warning_alerts': warning_alerts,
                    'recent_alerts': recent_normalized,
                    'triggered_rules': triggered_normalized,
                    'system_health': None
                }
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {
                'total_rules': 0,
                'active_rules': 0,
                'inactive_rules': 0,
                'total_alerts_today': 0,
                'critical_alerts': 0,
                'warning_alerts': 0,
                'recent_alerts': [],
                'triggered_rules': []
            }
    
    async def check_crypto_alerts(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check cryptocurrency market alerts using the crypto alert engine
        
        Args:
            market_data: Market data containing:
                - price_data: Dict with symbol -> {price, volatility_percent, timestamp}
                - volume_data: Dict with symbol -> {current_volume, average_volume}
                - technical_data: Dict with symbol -> {short_ma, long_ma, rsi}
                - portfolio_data: Dict with {value_change_percent}
                - watchlist_data: Dict with symbol -> {price_change_percent}
                - api_status: Dict with {api_name, status, minutes_without_data}
                - etl_jobs: List of jobs with {name, status, error_message}
        
        Returns:
            Dictionary with triggered alerts
        """
        results = {
            'checked': 0,
            'triggered': 0,
            'alerts': []
        }
        
        try:
            # Check price alerts
            if 'price_data' in market_data:
                for symbol, data in market_data['price_data'].items():
                    # Price threshold check
                    threshold_alert = self.crypto_alert_manager.price_engine.check_price_threshold(
                        symbol=symbol,
                        current_price=float(data.get('price', 0)),
                        threshold=float(data.get('threshold', 0)) if data.get('threshold') else 0
                    )
                    
                    if threshold_alert:
                        self._log_crypto_alert(threshold_alert, results)
                        results['triggered'] += 1
                    
                    # Price volatility check
                    volatility_alert = self.crypto_alert_manager.price_engine.check_price_volatility(
                        symbol=symbol,
                        price_change_percent=float(data.get('volatility_percent', 0)),
                        time_window='1h'
                    )
                    
                    if volatility_alert:
                        self._log_crypto_alert(volatility_alert, results)
                        results['triggered'] += 1
                    
                    results['checked'] += 1
            
            # Check volume alerts
            if 'volume_data' in market_data:
                for symbol, data in market_data['volume_data'].items():
                    volume_alert = self.crypto_alert_manager.volume_engine.check_volume_surge(
                        symbol=symbol,
                        current_volume=float(data.get('current_volume', 0)),
                        average_volume=float(data.get('average_volume', 0))
                    )
                    
                    if volume_alert:
                        self._log_crypto_alert(volume_alert, results)
                        results['triggered'] += 1
                    
                    results['checked'] += 1
            
            # Check technical alerts
            if 'technical_data' in market_data:
                for symbol, data in market_data['technical_data'].items():
                    ma_alert = self.crypto_alert_manager.technical_engine.check_moving_average_crossover(
                        symbol=symbol,
                        ma_short=float(data.get('short_ma', 0)),
                        ma_long=float(data.get('long_ma', 0))
                    )
                    
                    if ma_alert:
                        self._log_crypto_alert(ma_alert, results)
                        results['triggered'] += 1
                    
                    rsi_alert = self.crypto_alert_manager.technical_engine.check_rsi_levels(
                        symbol=symbol,
                        rsi_value=float(data.get('rsi', 50))
                    )
                    
                    if rsi_alert:
                        self._log_crypto_alert(rsi_alert, results)
                        results['triggered'] += 1
                    
                    results['checked'] += 1
            
            # Check portfolio alerts
            if 'portfolio_data' in market_data:
                portfolio_alert = self.crypto_alert_manager.portfolio_engine.check_portfolio_change(
                    portfolio_change_percent=float(market_data['portfolio_data'].get('value_change_percent', 0))
                )
                
                if portfolio_alert:
                    self._log_crypto_alert(portfolio_alert, results)
                    results['triggered'] += 1
                
                results['checked'] += 1
            
            # Check watchlist alerts
            if 'watchlist_data' in market_data:
                for symbol, data in market_data['watchlist_data'].items():
                    watchlist_alert = self.crypto_alert_manager.portfolio_engine.check_watchlist_movement(
                        symbol=symbol,
                        price_change_percent=float(data.get('price_change_percent', 0))
                    )
                    
                    if watchlist_alert:
                        self._log_crypto_alert(watchlist_alert, results)
                        results['triggered'] += 1
                    
                    results['checked'] += 1
            
            # Check ETL system alerts
            if 'api_status' in market_data:
                from datetime import datetime, timedelta
                api_data = market_data['api_status']
                minutes_down = int(api_data.get('minutes_without_data', 0))
                last_data_time = datetime.utcnow() - timedelta(minutes=minutes_down)
                api_alert = self.crypto_alert_manager.etl_engine.check_api_failure(
                    api_name=api_data.get('api_name', 'Unknown'),
                    last_data_time=last_data_time,
                    timeout_minutes=30
                )
                
                if api_alert:
                    self._log_crypto_alert(api_alert, results)
                    results['triggered'] += 1
                
                results['checked'] += 1
            
            if 'etl_jobs' in market_data:
                for job in market_data['etl_jobs']:
                    if job.get('status') == 'failed':
                        job_alert = self.crypto_alert_manager.etl_engine.check_etl_job_failure(
                            job_name=job.get('name', 'Unknown'),
                            error_type=job.get('error_type', 'unknown'),
                            error_message=job.get('error_message', '')
                        )
                        
                        if job_alert:
                            self._log_crypto_alert(job_alert, results)
                            results['triggered'] += 1
                    
                    results['checked'] += 1
            
            # Check security alerts
            if 'security_data' in market_data:
                security_data = market_data['security_data']
                
                if security_data.get('new_login'):
                    login_alert = self.crypto_alert_manager.security_engine.check_new_login(
                        login_device=security_data.get('device_info', 'Unknown Device'),
                        is_new_device=True
                    )
                    
                    if login_alert:
                        self._log_crypto_alert(login_alert, results)
                        results['triggered'] += 1
                
                if security_data.get('api_key_days_to_expiry'):
                    expiry_alert = self.crypto_alert_manager.security_engine.check_api_key_expiry(
                        days_until_expiry=int(security_data.get('api_key_days_to_expiry', 30))
                    )
                    
                    if expiry_alert:
                        self._log_crypto_alert(expiry_alert, results)
                        results['triggered'] += 1
                
                results['checked'] += 1
            
            logger.info(f"Crypto alert check completed: {results['checked']} checked, {results['triggered']} triggered")
            return results
        
        except Exception as e:
            logger.error(f"Error checking crypto alerts: {e}", exc_info=True)
            return results
    
    def _log_crypto_alert(self, alert_response, results: Dict[str, Any]) -> None:
        """
        Log a crypto alert to results
        
        Args:
            alert_response: CryptoAlertResponse object
            results: Results dictionary to append to
        """
        try:
            alert_dict = alert_response.to_dict()
            results['alerts'].append(alert_dict)
            logger.info(f"Crypto Alert [{alert_dict['category']}] - {alert_dict['message']}")
        except Exception as e:
            logger.error(f"Error logging crypto alert: {e}")
    
    async def check_crypto_alerts_and_email(self, market_data: Dict[str, Any], 
                                            email_recipients: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Check crypto alerts AND automatically send emails for triggered alerts
        
        Args:
            market_data: Market data to check
            email_recipients: List of email addresses to send alerts to
        
        Returns:
            Dictionary with alerts and email sending results
        """
        if not email_recipients:
            email_recipients = ["aishwarya.sakharkar@arithwise.com"]
        
        email_results = {
            'alerts_triggered': 0,
            'emails_sent': 0,
            'failed': 0,
            'email_list': email_recipients
        }
        
        try:
            # Check alerts
            alert_results = await self.check_crypto_alerts(market_data)
            email_results['alerts_triggered'] = alert_results['triggered']
            
            # Send email for each triggered alert (warning and critical only)
            for alert in alert_results['alerts']:
                if alert['severity'] in ['warning', 'critical']:
                    try:
                        # Skip INFO level alerts - only send WARNING and CRITICAL
                        if alert['severity'] not in ['warning', 'critical']:
                            logger.debug(f"Skipping {alert['severity']} alert: {alert['message']}")
                            continue
                        
                        # Build email subject
                        severity_icon = {
                            'warning': '⚠️',
                            'critical': '🚨'
                        }.get(alert['severity'], '📨')
                        
                        subject = f"{severity_icon} [{alert['severity'].upper()}] {alert['message'][:60]}"
                        
                        # Use new professional HTML email format
                        html_body = self.notification_service.email_notifier.format_alert_email(
                            alert_message=alert['message'],
                            alert_category=alert['category'],
                            alert_reason=alert['reason'],
                            severity=alert['severity'],
                            metadata=alert.get('metadata', {})
                        )
                        
                        # Send email (via email notifier)
                        success, error = self.notification_service.email_notifier.send_email(
                            recipients=email_recipients,
                            subject=subject,
                            body=html_body,
                            html=True
                        )
                        
                        if success:
                            email_results['emails_sent'] += 1
                            logger.info(f"✓ Email sent for: {alert['message']}")
                        else:
                            logger.error(f"Failed to send email: {error}")
                            email_results['failed'] += 1
                    
                    except Exception as e:
                        logger.error(f"Failed to send email for alert: {e}")
                        email_results['failed'] += 1
            
            return {
                **alert_results,
                'email_info': email_results
            }
        
        except Exception as e:
            logger.error(f"Error in check_crypto_alerts_and_email: {e}")
            return {
                'checked': 0,
                'triggered': 0,
                'alerts': [],
                'email_info': email_results
            }
