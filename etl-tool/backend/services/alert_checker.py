"""
Alert Checker - Evaluates alert conditions and determines when to trigger alerts
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Tuple, Optional, Dict, Any, List
import asyncio
import psutil
import os

logger = logging.getLogger(__name__)


class AlertChecker:
    """Checks various alert conditions"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
    
    async def check_price_threshold(
        self,
        symbol: str,
        current_price: float,
        threshold: float,
        comparison: str = "greater"
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if price crosses a threshold
        
        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC')
            current_price: Current price
            threshold: Price threshold
            comparison: 'greater', 'less', or 'equal'
        
        Returns:
            Tuple of (triggered: bool, message: Optional[str])
        """
        try:
            threshold_f = float(threshold)
            current_f = float(current_price)
            
            triggered = False
            if comparison == "greater" and current_f > threshold_f:
                triggered = True
            elif comparison == "less" and current_f < threshold_f:
                triggered = True
            elif comparison == "equal" and current_f == threshold_f:
                triggered = True
            
            if triggered:
                message = f"{symbol} price ${current_f:,.2f} crossed threshold ${threshold_f:,.2f}"
                return True, message
            
            return False, None
        except Exception as e:
            logger.error(f"Error checking price threshold: {e}")
            return False, None
    
    async def check_volatility(
        self,
        symbol: str,
        volatility_percentage: float,
        duration_minutes: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if price volatility exceeds threshold
        
        Args:
            symbol: Cryptocurrency symbol
            volatility_percentage: Volatility threshold (e.g., 5 for 5%)
            duration_minutes: Time window in minutes
        
        Returns:
            Tuple of (triggered: bool, message: Optional[str])
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get price data for the time window
                cutoff_time = datetime.utcnow() - timedelta(minutes=duration_minutes)
                
                prices = await conn.fetch("""
                    SELECT price, timestamp
                    FROM price_history
                    WHERE symbol = $1 AND timestamp >= $2
                    ORDER BY timestamp ASC
                    LIMIT 1000
                """, symbol, cutoff_time)
                
                if len(prices) < 2:
                    logger.warning(f"Insufficient price data for {symbol} volatility check")
                    return False, None
                
                # Calculate price change percentage
                old_price = float(prices[0]['price'])
                new_price = float(prices[-1]['price'])
                
                if old_price == 0:
                    return False, None
                
                change_percent = abs((new_price - old_price) / old_price) * 100
                
                if change_percent > volatility_percentage:
                    message = (
                        f"{symbol} price volatility {change_percent:.2f}% in last {duration_minutes} min "
                        f"(threshold: {volatility_percentage}%)"
                    )
                    return True, message
                
                return False, None
        except Exception as e:
            logger.error(f"Error checking volatility for {symbol}: {e}")
            return False, None
    
    async def check_data_missing(
        self,
        api_endpoint: str,
        missing_minutes: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if API data is missing
        
        Args:
            api_endpoint: API endpoint to check
            missing_minutes: Minutes of no data before triggering alert
        
        Returns:
            Tuple of (triggered: bool, message: Optional[str])
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get last data point from API connector
                cutoff_time = datetime.utcnow() - timedelta(minutes=missing_minutes)
                
                result = await conn.fetchval("""
                    SELECT MAX(timestamp)
                    FROM api_connector_data
                    WHERE api_url = $1
                """, api_endpoint) if hasattr(conn, 'api_url') else None
                
                # Alternative: check by connector_id
                result = await conn.fetchval("""
                    SELECT MAX(timestamp)
                    FROM api_connector_data
                    WHERE connector_id = $1
                """, api_endpoint)
                
                if result is None or result < cutoff_time:
                    message = f"No data received from API endpoint {api_endpoint} for {missing_minutes} minutes"
                    return True, message
                
                return False, None
        except Exception as e:
            logger.error(f"Error checking data missing for {api_endpoint}: {e}")
            return False, None
    
    async def check_system_health(
        self,
        health_check_type: str,
        threshold: float
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check system health metrics
        
        Args:
            health_check_type: Type of check ('db_connection', 'disk_space', 'memory', 'cpu')
            threshold: Threshold value (percentage or GB)
        
        Returns:
            Tuple of (triggered: bool, message: Optional[str], metadata: Optional[Dict])
        """
        try:
            metadata = {}
            
            if health_check_type == "disk_space":
                # Check available disk space
                disk_usage = psutil.disk_usage('/')
                available_gb = disk_usage.free / (1024 ** 3)
                used_percent = disk_usage.percent
                
                metadata = {
                    'available_gb': round(available_gb, 2),
                    'used_percent': used_percent,
                    'total_gb': round(disk_usage.total / (1024 ** 3), 2)
                }
                
                if available_gb < threshold:
                    message = f"Low disk space: {available_gb:.2f} GB available (threshold: {threshold:.2f} GB)"
                    return True, message, metadata
            
            elif health_check_type == "memory":
                # Check memory usage
                memory = psutil.virtual_memory()
                available_gb = memory.available / (1024 ** 3)
                used_percent = memory.percent
                
                metadata = {
                    'available_gb': round(available_gb, 2),
                    'used_percent': used_percent,
                    'total_gb': round(memory.total / (1024 ** 3), 2)
                }
                
                if used_percent > threshold:
                    message = f"High memory usage: {used_percent:.2f}% (threshold: {threshold:.2f}%)"
                    return True, message, metadata
            
            elif health_check_type == "cpu":
                # Check CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                
                metadata = {
                    'cpu_percent': cpu_percent,
                    'core_count': psutil.cpu_count()
                }
                
                if cpu_percent > threshold:
                    message = f"High CPU usage: {cpu_percent:.2f}% (threshold: {threshold:.2f}%)"
                    return True, message, metadata
            
            elif health_check_type == "db_connection":
                # Check database connection
                try:
                    async with self.db_pool.acquire() as conn:
                        result = await conn.fetchval('SELECT 1')
                        if result == 1:
                            metadata = {'status': 'healthy'}
                            return False, None, metadata
                except Exception as db_error:
                    message = f"Database connection failed: {str(db_error)}"
                    metadata = {'error': str(db_error), 'status': 'unhealthy'}
                    return True, message, metadata
            
            return False, None, metadata
        except Exception as e:
            logger.error(f"Error checking system health ({health_check_type}): {e}")
            return False, None, {'error': str(e)}
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol from database
        
        Args:
            symbol: Cryptocurrency symbol
        
        Returns:
            Current price or None
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Get latest price from api_connector_items
                result = await conn.fetchval("""
                    SELECT price
                    FROM api_connector_items
                    WHERE coin_symbol = $1 OR coin_name = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, symbol.upper())
                
                if result is not None:
                    return float(result)
                
                # Try from api_connector_data
                result = await conn.fetchval("""
                    SELECT price
                    FROM api_connector_data
                    WHERE instrument = $1 OR exchange = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, symbol.upper())
                
                if result is not None:
                    return float(result)
                
                # Fallback: Try from price_history table
                result = await conn.fetchval("""
                    SELECT price
                    FROM price_history
                    WHERE symbol = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, symbol.upper())
                
                return float(result) if result else None
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    async def record_price(self, symbol: str, price: float, source: str = "system") -> bool:
        """
        Record price in price_history table
        
        Args:
            symbol: Cryptocurrency symbol
            price: Price value
            source: Price source
        
        Returns:
            Success status
        """
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO price_history (symbol, price, source, timestamp)
                    VALUES ($1, $2, $3, NOW())
                """, symbol.upper(), Decimal(str(price)), source)
                return True
        except Exception as e:
            logger.error(f"Error recording price for {symbol}: {e}")
            return False


class AlertConditionEvaluator:
    """Evaluates if an alert should be triggered based on rule and current state"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.checker = AlertChecker(db_pool)
    
    async def evaluate_rule(self, rule: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Evaluate if an alert rule should trigger
        
        Args:
            rule: Alert rule dictionary from database
        
        Returns:
            Tuple of (should_trigger: bool, message: Optional[str], metadata: Optional[Dict])
        """
        try:
            alert_type = rule.get('alert_type')
            
            if alert_type == 'price_threshold':
                symbol = rule.get('symbol')
                threshold = rule.get('price_threshold')
                comparison = rule.get('price_comparison', 'greater')
                
                current_price = await self.checker.get_current_price(symbol)
                if current_price is None:
                    return False, None, None
                
                # Record price to price_history
                await self.checker.record_price(
                    symbol=symbol,
                    price=float(current_price),
                    source="alert_check"
                )
                
                triggered, message = await self.checker.check_price_threshold(
                    symbol, current_price, threshold, comparison
                )
                metadata = {'current_price': current_price, 'threshold': threshold}
                return triggered, message, metadata
            
            elif alert_type == 'volatility':
                symbol = rule.get('symbol')
                volatility_pct = rule.get('volatility_percentage')
                duration_min = rule.get('volatility_duration_minutes')
                
                # Get current price and record it
                current_price = await self.checker.get_current_price(symbol)
                if current_price:
                    await self.checker.record_price(
                        symbol=symbol,
                        price=float(current_price),
                        source="alert_check"
                    )
                
                triggered, message = await self.checker.check_volatility(
                    symbol, volatility_pct, duration_min
                )
                return triggered, message, None
            
            elif alert_type == 'data_missing':
                api_endpoint = rule.get('api_endpoint')
                missing_min = rule.get('data_missing_minutes')
                
                triggered, message = await self.checker.check_data_missing(
                    api_endpoint, missing_min
                )
                return triggered, message, None
            
            elif alert_type == 'system_health':
                health_type = rule.get('health_check_type')
                threshold = rule.get('threshold_value')
                
                triggered, message, metadata = await self.checker.check_system_health(
                    health_type, float(threshold) if threshold else 0
                )
                return triggered, message, metadata
            
            return False, None, None
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.get('id')}: {e}")
            return False, None, None
