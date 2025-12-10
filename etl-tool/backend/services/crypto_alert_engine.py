"""
Comprehensive Crypto Alert Engine
Handles multiple alert types: price, volume, technical, portfolio, news, ETL system, and security alerts
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Tuple, Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class AlertCategory(str, Enum):
    """Alert categories"""
    PRICE = "price_alerts"
    VOLUME = "volume_liquidity_alerts"
    TECHNICAL = "trend_technical_alerts"
    PORTFOLIO = "portfolio_watchlist_alerts"
    NEWS = "news_fundamental_alerts"
    ETL_SYSTEM = "etl_system_alerts"
    SECURITY = "security_account_alerts"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CryptoAlertResponse:
    """Standard alert response format"""
    
    def __init__(self, message: str, category: AlertCategory, reason: str, severity: AlertSeverity, metadata: Optional[Dict[str, Any]] = None):
        self.message = message
        self.category = category.value
        self.reason = reason
        self.severity = severity.value
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "category": self.category,
            "reason": self.reason,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class PriceAlertEngine:
    """Detects price-based alerts"""
    
    @staticmethod
    def check_price_threshold(
        symbol: str,
        current_price: float,
        threshold: float,
        comparison: str = "greater"
    ) -> Optional[CryptoAlertResponse]:
        """
        Check if price crossed a threshold
        
        Args:
            symbol: Cryptocurrency symbol (BTC, ETH, etc.)
            current_price: Current market price
            threshold: Price threshold
            comparison: 'greater', 'less', or 'equal'
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            threshold_f = float(threshold)
            current_f = float(current_price)
            
            triggered = False
            operator_text = ""
            
            if comparison == "greater" and current_f > threshold_f:
                triggered = True
                operator_text = "above"
            elif comparison == "less" and current_f < threshold_f:
                triggered = True
                operator_text = "below"
            elif comparison == "equal" and abs(current_f - threshold_f) < 0.01:
                triggered = True
                operator_text = "at"
            
            if triggered:
                message = f"{symbol} price reached ₹{current_f:,.2f}"
                reason = f"Price {operator_text} threshold of ₹{threshold_f:,.2f}"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.PRICE,
                    reason=reason,
                    severity=AlertSeverity.WARNING,
                    metadata={
                        "symbol": symbol,
                        "current_price": current_f,
                        "threshold": threshold_f,
                        "comparison": comparison
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking price threshold for {symbol}: {e}")
            return None
    
    @staticmethod
    def check_price_volatility(
        symbol: str,
        price_change_percent: float,
        time_window: str = "1h"
    ) -> Optional[CryptoAlertResponse]:
        """
        Check if price volatility exceeds threshold
        
        Args:
            symbol: Cryptocurrency symbol
            price_change_percent: Percentage change (e.g., 5 for 5%)
            time_window: Time window ('1h', '24h', '7d')
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            # Define volatility thresholds
            thresholds = {
                "1h": 5,      # 5% change in 1 hour
                "24h": 15,    # 15% change in 24 hours
                "7d": 30      # 30% change in 7 days
            }
            
            threshold = thresholds.get(time_window, 5)
            
            if abs(price_change_percent) > threshold:
                direction = "increased" if price_change_percent > 0 else "decreased"
                message = f"{symbol} price {direction} {abs(price_change_percent):.2f}% in {time_window}"
                reason = f"Price volatility exceeded {threshold}% threshold in {time_window}"
                
                severity = AlertSeverity.WARNING if abs(price_change_percent) < 20 else AlertSeverity.CRITICAL
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.PRICE,
                    reason=reason,
                    severity=severity,
                    metadata={
                        "symbol": symbol,
                        "price_change_percent": price_change_percent,
                        "time_window": time_window,
                        "threshold": threshold
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking volatility for {symbol}: {e}")
            return None


class VolumeAlertEngine:
    """Detects volume and liquidity-based alerts"""
    
    @staticmethod
    def check_volume_surge(
        symbol: str,
        current_volume: float,
        average_volume: float,
        surge_percent: float = 50
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when trading volume surges
        
        Args:
            symbol: Cryptocurrency symbol
            current_volume: Current trading volume
            average_volume: Average trading volume
            surge_percent: Surge threshold percentage
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            if average_volume <= 0:
                return None
            
            volume_increase = ((current_volume - average_volume) / average_volume) * 100
            
            if volume_increase > surge_percent:
                message = f"{symbol} volume increased by {volume_increase:.2f}%"
                reason = f"Trading volume surge detected - exceeds {surge_percent}% threshold"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.VOLUME,
                    reason=reason,
                    severity=AlertSeverity.WARNING,
                    metadata={
                        "symbol": symbol,
                        "current_volume": current_volume,
                        "average_volume": average_volume,
                        "increase_percent": volume_increase
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking volume surge for {symbol}: {e}")
            return None
    
    @staticmethod
    def check_liquidity_drop(
        symbol: str,
        current_liquidity: float,
        previous_liquidity: float,
        drop_percent: float = 30
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when liquidity drops significantly
        
        Args:
            symbol: Cryptocurrency symbol
            current_liquidity: Current liquidity
            previous_liquidity: Previous liquidity
            drop_percent: Drop threshold percentage
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            if previous_liquidity <= 0:
                return None
            
            liquidity_decrease = ((previous_liquidity - current_liquidity) / previous_liquidity) * 100
            
            if liquidity_decrease > drop_percent:
                message = f"{symbol} liquidity dropped by {liquidity_decrease:.2f}%"
                reason = f"Liquidity drop may cause high slippage - exceeds {drop_percent}% threshold"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.VOLUME,
                    reason=reason,
                    severity=AlertSeverity.CRITICAL,
                    metadata={
                        "symbol": symbol,
                        "current_liquidity": current_liquidity,
                        "previous_liquidity": previous_liquidity,
                        "decrease_percent": liquidity_decrease
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking liquidity drop for {symbol}: {e}")
            return None


class TechnicalAlertEngine:
    """Detects technical indicator-based alerts"""
    
    @staticmethod
    def check_moving_average_crossover(
        symbol: str,
        ma_short: float,
        ma_long: float,
        previous_ma_short: Optional[float] = None,
        previous_ma_long: Optional[float] = None
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when moving averages cross over
        
        Args:
            symbol: Cryptocurrency symbol
            ma_short: Current short-term MA (e.g., 50-day)
            ma_long: Current long-term MA (e.g., 200-day)
            previous_ma_short: Previous short-term MA
            previous_ma_long: Previous long-term MA
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            # Check for bullish crossover (short MA crosses above long MA)
            if previous_ma_short and previous_ma_long:
                was_below = previous_ma_short <= previous_ma_long
                is_above = ma_short > ma_long
                
                if was_below and is_above:
                    message = f"{symbol} short-term MA crossed above long-term MA"
                    reason = "Bullish trend change detected - short MA above long MA"
                    
                    return CryptoAlertResponse(
                        message=message,
                        category=AlertCategory.TECHNICAL,
                        reason=reason,
                        severity=AlertSeverity.INFO,
                        metadata={
                            "symbol": symbol,
                            "short_ma": ma_short,
                            "long_ma": ma_long,
                            "crossover_type": "bullish"
                        }
                    )
                
                # Check for bearish crossover (short MA crosses below long MA)
                was_above = previous_ma_short >= previous_ma_long
                is_below = ma_short < ma_long
                
                if was_above and is_below:
                    message = f"{symbol} short-term MA crossed below long-term MA"
                    reason = "Bearish trend change detected - short MA below long MA"
                    
                    return CryptoAlertResponse(
                        message=message,
                        category=AlertCategory.TECHNICAL,
                        reason=reason,
                        severity=AlertSeverity.WARNING,
                        metadata={
                            "symbol": symbol,
                            "short_ma": ma_short,
                            "long_ma": ma_long,
                            "crossover_type": "bearish"
                        }
                    )
            
            return None
        except Exception as e:
            logger.error(f"Error checking MA crossover for {symbol}: {e}")
            return None
    
    @staticmethod
    def check_rsi_levels(
        symbol: str,
        rsi_value: float,
        overbought_threshold: float = 70,
        oversold_threshold: float = 30
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when RSI indicates overbought/oversold conditions
        
        Args:
            symbol: Cryptocurrency symbol
            rsi_value: Current RSI value (0-100)
            overbought_threshold: Overbought threshold (default 70)
            oversold_threshold: Oversold threshold (default 30)
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            if rsi_value > overbought_threshold:
                message = f"{symbol} RSI is {rsi_value:.2f} (overbought)"
                reason = f"RSI above {overbought_threshold} indicates overbought condition - potential pullback"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.TECHNICAL,
                    reason=reason,
                    severity=AlertSeverity.WARNING,
                    metadata={
                        "symbol": symbol,
                        "rsi_value": rsi_value,
                        "condition": "overbought"
                    }
                )
            
            elif rsi_value < oversold_threshold:
                message = f"{symbol} RSI is {rsi_value:.2f} (oversold)"
                reason = f"RSI below {oversold_threshold} indicates oversold condition - potential bounce"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.TECHNICAL,
                    reason=reason,
                    severity=AlertSeverity.INFO,
                    metadata={
                        "symbol": symbol,
                        "rsi_value": rsi_value,
                        "condition": "oversold"
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking RSI for {symbol}: {e}")
            return None


class PortfolioAlertEngine:
    """Detects portfolio and watchlist-based alerts"""
    
    @staticmethod
    def check_portfolio_change(
        portfolio_change_percent: float,
        change_threshold: float = 10
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when portfolio value changes significantly
        
        Args:
            portfolio_change_percent: Portfolio value change percentage
            change_threshold: Change threshold percentage
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            if abs(portfolio_change_percent) > change_threshold:
                direction = "gained" if portfolio_change_percent > 0 else "lost"
                message = f"Your portfolio {direction} {abs(portfolio_change_percent):.2f}% today"
                reason = f"Portfolio value change of {abs(portfolio_change_percent):.2f}% exceeds {change_threshold}% threshold"
                
                severity = AlertSeverity.WARNING if portfolio_change_percent < 0 else AlertSeverity.INFO
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.PORTFOLIO,
                    reason=reason,
                    severity=severity,
                    metadata={
                        "portfolio_change_percent": portfolio_change_percent,
                        "threshold": change_threshold
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking portfolio change: {e}")
            return None
    
    @staticmethod
    def check_watchlist_movement(
        symbol: str,
        price_change_percent: float,
        movement_threshold: float = 10
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when watchlist coin moves significantly
        
        Args:
            symbol: Cryptocurrency symbol in watchlist
            price_change_percent: Price change percentage
            movement_threshold: Movement threshold percentage
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            if abs(price_change_percent) > movement_threshold:
                direction = "gained" if price_change_percent > 0 else "lost"
                message = f"{symbol} in your watchlist {direction} {abs(price_change_percent):.2f}%"
                reason = f"{symbol} movement of {abs(price_change_percent):.2f}% exceeds {movement_threshold}% threshold"
                
                severity = AlertSeverity.INFO
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.PORTFOLIO,
                    reason=reason,
                    severity=severity,
                    metadata={
                        "symbol": symbol,
                        "price_change_percent": price_change_percent,
                        "threshold": movement_threshold
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking watchlist movement for {symbol}: {e}")
            return None


class ETLSystemAlertEngine:
    """Detects ETL pipeline and data quality alerts"""
    
    @staticmethod
    def check_api_failure(
        api_name: str,
        last_data_time: datetime,
        timeout_minutes: int = 30
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when API fails or times out
        
        Args:
            api_name: Name of the API
            last_data_time: Last successful data retrieval time
            timeout_minutes: Timeout threshold in minutes
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            time_since_last_data = datetime.utcnow() - last_data_time
            minutes_elapsed = time_since_last_data.total_seconds() / 60
            
            if minutes_elapsed > timeout_minutes:
                message = f"{api_name} not responding — using cached data"
                reason = f"No data received from {api_name} for {int(minutes_elapsed)} minutes"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.ETL_SYSTEM,
                    reason=reason,
                    severity=AlertSeverity.CRITICAL,
                    metadata={
                        "api_name": api_name,
                        "minutes_without_data": int(minutes_elapsed),
                        "timeout_threshold": timeout_minutes
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking API failure for {api_name}: {e}")
            return None
    
    @staticmethod
    def check_etl_job_failure(
        job_name: str,
        error_message: str,
        error_type: str = "timeout"
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when ETL job fails
        
        Args:
            job_name: Name of the ETL job
            error_message: Error message from the job
            error_type: Type of error (timeout, exception, validation, etc.)
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            message = f"ETL job '{job_name}' failed due to {error_type}"
            reason = f"Error: {error_message[:100]}"  # Truncate long messages
            
            return CryptoAlertResponse(
                message=message,
                category=AlertCategory.ETL_SYSTEM,
                reason=reason,
                severity=AlertSeverity.CRITICAL,
                metadata={
                    "job_name": job_name,
                    "error_type": error_type,
                    "error_message": error_message
                }
            )
        except Exception as e:
            logger.error(f"Error creating ETL failure alert for {job_name}: {e}")
            return None
    
    @staticmethod
    def check_data_anomaly(
        symbol: str,
        price_change_percent: float,
        max_allowed_change: float = 30
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when data shows anomalies (impossible price changes)
        
        Args:
            symbol: Cryptocurrency symbol
            price_change_percent: Sudden price change percentage
            max_allowed_change: Maximum allowed change percentage
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            if abs(price_change_percent) > max_allowed_change:
                message = f"{symbol} price changed {price_change_percent:.2f}% in 1 minute (possible data issue)"
                reason = f"Detected anomalous price change - exceeds {max_allowed_change}% threshold"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.ETL_SYSTEM,
                    reason=reason,
                    severity=AlertSeverity.CRITICAL,
                    metadata={
                        "symbol": symbol,
                        "price_change_percent": price_change_percent,
                        "anomaly_type": "price_spike"
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking data anomaly for {symbol}: {e}")
            return None


class SecurityAlertEngine:
    """Detects security and account-related alerts"""
    
    @staticmethod
    def check_new_login(
        login_device: str,
        is_new_device: bool
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert on new device login
        
        Args:
            login_device: Device identifier/name
            is_new_device: Whether this is a new/unrecognized device
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            if is_new_device:
                message = f"New login detected from {login_device}"
                reason = "Login from unrecognized device - verify if this was you"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.SECURITY,
                    reason=reason,
                    severity=AlertSeverity.WARNING,
                    metadata={
                        "login_device": login_device,
                        "is_new_device": is_new_device
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking new login: {e}")
            return None
    
    @staticmethod
    def check_api_key_expiry(
        days_until_expiry: int,
        warning_days: int = 7
    ) -> Optional[CryptoAlertResponse]:
        """
        Alert when API key is about to expire
        
        Args:
            days_until_expiry: Days until API key expires
            warning_days: Days before expiry to alert
        
        Returns:
            CryptoAlertResponse or None
        """
        try:
            if 0 < days_until_expiry <= warning_days:
                message = f"Your API key expires in {days_until_expiry} days"
                reason = "API key expiration approaching - renew before expiry to avoid service interruption"
                
                severity = AlertSeverity.WARNING if days_until_expiry > 3 else AlertSeverity.CRITICAL
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.SECURITY,
                    reason=reason,
                    severity=severity,
                    metadata={
                        "days_until_expiry": days_until_expiry,
                        "warning_days": warning_days
                    }
                )
            
            elif days_until_expiry <= 0:
                message = "Your API key has expired"
                reason = "API key is no longer valid - renew immediately"
                
                return CryptoAlertResponse(
                    message=message,
                    category=AlertCategory.SECURITY,
                    reason=reason,
                    severity=AlertSeverity.CRITICAL,
                    metadata={
                        "days_until_expiry": days_until_expiry,
                        "status": "expired"
                    }
                )
            
            return None
        except Exception as e:
            logger.error(f"Error checking API key expiry: {e}")
            return None


class CryptoAlertManager:
    """Main alert manager that coordinates all alert engines"""
    
    def __init__(self):
        self.price_engine = PriceAlertEngine()
        self.volume_engine = VolumeAlertEngine()
        self.technical_engine = TechnicalAlertEngine()
        self.portfolio_engine = PortfolioAlertEngine()
        self.etl_engine = ETLSystemAlertEngine()
        self.security_engine = SecurityAlertEngine()
        self.alerts: List[CryptoAlertResponse] = []
    
    def add_alert(self, alert: CryptoAlertResponse) -> None:
        """Add alert to the list"""
        if alert:
            self.alerts.append(alert)
            logger.info(f"Alert generated: {alert.message}")
    
    def get_alerts(self, category: Optional[AlertCategory] = None, severity: Optional[AlertSeverity] = None) -> List[Dict[str, Any]]:
        """
        Get alerts filtered by category and/or severity
        
        Args:
            category: Filter by alert category
            severity: Filter by alert severity
        
        Returns:
            List of alert dictionaries
        """
        filtered_alerts = self.alerts
        
        if category:
            filtered_alerts = [a for a in filtered_alerts if a.category == category.value]
        
        if severity:
            filtered_alerts = [a for a in filtered_alerts if a.severity == severity.value]
        
        return [alert.to_dict() for alert in filtered_alerts]
    
    def clear_alerts(self) -> None:
        """Clear all alerts"""
        self.alerts.clear()
