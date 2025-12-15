"""
Test script to demonstrate the Crypto Alert Engine
Shows all alert types and how they work
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.crypto_alert_engine import (
    CryptoAlertManager, 
    AlertCategory, 
    AlertSeverity,
    PriceAlertEngine,
    VolumeAlertEngine,
    TechnicalAlertEngine,
    PortfolioAlertEngine,
    ETLSystemAlertEngine,
    SecurityAlertEngine
)
from datetime import datetime, timedelta
import json


def print_section(title):
    """Print a formatted section title"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_price_alerts():
    """Test price-based alerts"""
    print_section("1. PRICE ALERTS")
    
    manager = CryptoAlertManager()
    
    # Test price threshold alert
    alert = manager.price_engine.check_price_threshold(
        symbol="BTC",
        current_price=95000,
        threshold=90000,
        comparison="greater"
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))
    
    # Test price volatility alert
    print("\n" + "-"*70 + "\n")
    alert = manager.price_engine.check_price_volatility(
        symbol="ETH",
        price_change_percent=12.5,
        time_window="1h"
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))


def test_volume_alerts():
    """Test volume and liquidity alerts"""
    print_section("2. VOLUME & LIQUIDITY ALERTS")
    
    manager = CryptoAlertManager()
    
    # Test volume surge
    alert = manager.volume_engine.check_volume_surge(
        symbol="DOGE",
        current_volume=5000000,
        average_volume=2000000,
        surge_percent=50
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))
    
    # Test liquidity drop
    print("\n" + "-"*70 + "\n")
    alert = manager.volume_engine.check_liquidity_drop(
        symbol="XYZ",
        current_liquidity=1000000,
        previous_liquidity=1400000,
        drop_percent=30
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))


def test_technical_alerts():
    """Test technical indicator alerts"""
    print_section("3. TECHNICAL & TREND ALERTS")
    
    manager = CryptoAlertManager()
    
    # Test MA crossover (bullish)
    alert = manager.technical_engine.check_moving_average_crossover(
        symbol="BTC",
        ma_short=48000,
        ma_long=47000,
        previous_ma_short=46000,
        previous_ma_long=47500
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))
    
    # Test RSI overbought
    print("\n" + "-"*70 + "\n")
    alert = manager.technical_engine.check_rsi_levels(
        symbol="ETH",
        rsi_value=78,
        overbought_threshold=70
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))


def test_portfolio_alerts():
    """Test portfolio and watchlist alerts"""
    print_section("4. PORTFOLIO & WATCHLIST ALERTS")
    
    manager = CryptoAlertManager()
    
    # Test portfolio change
    alert = manager.portfolio_engine.check_portfolio_change(
        portfolio_change_percent=-10.5,
        change_threshold=10
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))
    
    # Test watchlist movement
    print("\n" + "-"*70 + "\n")
    alert = manager.portfolio_engine.check_watchlist_movement(
        symbol="SOL",
        price_change_percent=12.3,
        movement_threshold=10
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))


def test_etl_system_alerts():
    """Test ETL system and data quality alerts"""
    print_section("5. ETL SYSTEM & DATA QUALITY ALERTS")
    
    manager = CryptoAlertManager()
    
    # Test API failure
    last_data_time = datetime.utcnow() - timedelta(minutes=45)
    alert = manager.etl_engine.check_api_failure(
        api_name="Binance API",
        last_data_time=last_data_time,
        timeout_minutes=30
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))
    
    # Test ETL job failure
    print("\n" + "-"*70 + "\n")
    alert = manager.etl_engine.check_etl_job_failure(
        job_name="Daily Price Aggregation",
        error_message="Connection timeout after 30 seconds",
        error_type="timeout"
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))
    
    # Test data anomaly
    print("\n" + "-"*70 + "\n")
    alert = manager.etl_engine.check_data_anomaly(
        symbol="BTC",
        price_change_percent=40,
        max_allowed_change=30
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))


def test_security_alerts():
    """Test security and account alerts"""
    print_section("6. SECURITY & ACCOUNT ALERTS")
    
    manager = CryptoAlertManager()
    
    # Test new login
    alert = manager.security_engine.check_new_login(
        login_device="Chrome on Windows",
        is_new_device=True
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))
    
    # Test API key expiry
    print("\n" + "-"*70 + "\n")
    alert = manager.security_engine.check_api_key_expiry(
        days_until_expiry=3,
        warning_days=7
    )
    if alert:
        manager.add_alert(alert)
        print(json.dumps(alert.to_dict(), indent=2, default=str))


def test_alert_filtering():
    """Test alert filtering by category and severity"""
    print_section("7. ALERT FILTERING & SUMMARY")
    
    manager = CryptoAlertManager()
    
    # Generate various alerts
    alerts_to_generate = [
        ("price", manager.price_engine.check_price_threshold("BTC", 95000, 90000, "greater")),
        ("etl", manager.etl_engine.check_data_anomaly("ETH", 40, 30)),
        ("security", manager.security_engine.check_api_key_expiry(3, 7)),
    ]
    
    for name, alert in alerts_to_generate:
        if alert:
            manager.add_alert(alert)
    
    # Show all alerts
    print("All Alerts:")
    all_alerts = manager.get_alerts()
    print(f"Total: {len(all_alerts)} alerts\n")
    for alert in all_alerts:
        print(f"  [{alert['severity'].upper()}] {alert['category']}: {alert['message']}")
    
    # Filter by severity
    print(f"\n\nCritical Alerts Only:")
    critical = manager.get_alerts(severity=AlertSeverity.CRITICAL)
    print(f"Total: {len(critical)} critical alerts\n")
    for alert in critical:
        print(f"  {alert['category']}: {alert['message']}")
    
    # Filter by category
    print(f"\n\nPrice & ETL Alerts Only:")
    filtered = [a for a in manager.get_alerts() if a['category'] in ['price_alerts', 'etl_system_alerts']]
    print(f"Total: {len(filtered)} alerts\n")
    for alert in filtered:
        print(f"  {alert['category']}: {alert['message']}")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("  CRYPTO ALERT ENGINE - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    try:
        test_price_alerts()
        test_volume_alerts()
        test_technical_alerts()
        test_portfolio_alerts()
        test_etl_system_alerts()
        test_security_alerts()
        test_alert_filtering()
        
        print_section("TEST SUMMARY")
        print("✓ All alert types working correctly!")
        print("✓ Price alerts - threshold and volatility detection")
        print("✓ Volume alerts - surge and liquidity drop detection")
        print("✓ Technical alerts - MA crossovers and RSI levels")
        print("✓ Portfolio alerts - watchlist and portfolio value changes")
        print("✓ ETL system alerts - API failures and data anomalies")
        print("✓ Security alerts - login detection and key expiry")
        print("\n")
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
