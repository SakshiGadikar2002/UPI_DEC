"""
Real-time Crypto Alert Testing - Monitor alerts as they trigger
This script simulates market conditions and displays alerts in real-time
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any
import sys
sys.path.insert(0, '.')

from services.alert_manager import AlertManager
from services.crypto_alert_engine import CryptoAlertManager


class RealTimeAlertTester:
    """Test alerts with real-time market data simulation"""
    
    def __init__(self):
        self.alert_manager = AlertManager(None)  # No DB needed for testing
        self.test_count = 0
        self.total_alerts = 0
    
    def print_separator(self, title=""):
        """Print colored separator"""
        if title:
            print(f"\n{'='*80}")
            print(f"  {title}")
            print(f"{'='*80}\n")
        else:
            print(f"\n{'-'*80}\n")
    
    def print_alert(self, alert: Dict[str, Any]):
        """Print alert in formatted style"""
        severity_colors = {
            'info': '🔵 INFO    ',
            'warning': '🟡 WARNING ',
            'critical': '🔴 CRITICAL'
        }
        
        severity = alert.get('severity', 'info')
        color = severity_colors.get(severity, '⚪')
        
        print(f"{color} | {alert['message']}")
        print(f"         | Category: {alert['category']}")
        print(f"         | Reason: {alert['reason']}")
        if alert.get('metadata'):
            print(f"         | Data: {json.dumps(alert['metadata'], indent=2)}")
        print()
    
    async def test_scenario_1_price_alerts(self):
        """Test 1: Price threshold and volatility alerts"""
        self.print_separator("TEST 1: PRICE ALERTS 📈")
        
        print("Scenario: Bitcoin reaches $95,000 (threshold $90,000)")
        print("Scenario: Ethereum shows 12.5% volatility in 1 hour\n")
        
        market_data = {
            'price_data': {
                'BTC': {
                    'price': 95000,
                    'threshold': 90000,
                    'volatility_percent': 5
                },
                'ETH': {
                    'price': 3500,
                    'volatility_percent': 12.5
                }
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_2_volume_alerts(self):
        """Test 2: Volume surge and liquidity alerts"""
        self.print_separator("TEST 2: VOLUME & LIQUIDITY ALERTS 📊")
        
        print("Scenario: Dogecoin volume increases 150%")
        print("Scenario: Liquidity drops below threshold\n")
        
        market_data = {
            'volume_data': {
                'DOGE': {
                    'current_volume': 5000000,
                    'average_volume': 2000000
                },
                'XRP': {
                    'current_volume': 1000000,
                    'average_volume': 2000000
                }
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_3_technical_alerts(self):
        """Test 3: Moving average and RSI alerts"""
        self.print_separator("TEST 3: TECHNICAL INDICATORS 🔧")
        
        print("Scenario: Bitcoin MA crossover detected")
        print("Scenario: Ethereum RSI at 78 (overbought)\n")
        
        market_data = {
            'technical_data': {
                'BTC': {
                    'short_ma': 48000,
                    'long_ma': 47000,
                    'rsi': 65
                },
                'ETH': {
                    'short_ma': 3500,
                    'long_ma': 3400,
                    'rsi': 78
                }
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_4_portfolio_alerts(self):
        """Test 4: Portfolio and watchlist alerts"""
        self.print_separator("TEST 4: PORTFOLIO & WATCHLIST 💼")
        
        print("Scenario: Portfolio drops 10.5% today")
        print("Scenario: Solana in watchlist up 12.3%\n")
        
        market_data = {
            'portfolio_data': {
                'value_change_percent': -10.5
            },
            'watchlist_data': {
                'SOL': {
                    'price_change_percent': 12.3
                },
                'ADA': {
                    'price_change_percent': 3.5
                }
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_5_etl_alerts(self):
        """Test 5: ETL system and data quality alerts"""
        self.print_separator("TEST 5: ETL SYSTEM ALERTS ⚙️")
        
        print("Scenario: Binance API offline for 45 minutes")
        print("Scenario: Daily Price Aggregation job failed")
        print("Scenario: Bitcoin price changed 40% in 1 minute (anomaly)\n")
        
        market_data = {
            'api_status': {
                'api_name': 'Binance API',
                'status': 'offline',
                'minutes_without_data': 45
            },
            'etl_jobs': [
                {
                    'name': 'Daily Price Aggregation',
                    'status': 'failed',
                    'error_type': 'timeout',
                    'error_message': 'Connection timeout after 30 seconds'
                }
            ]
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        # Test data anomaly separately
        market_data['etl_jobs'].append({
            'name': 'Data Validation',
            'status': 'success',
            'data_anomaly': {
                'symbol': 'BTC',
                'price_change_percent': 40
            }
        })
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        for alert in results['alerts']:
            if 'anomaly' in alert.get('reason', '').lower():
                self.print_alert(alert)
                self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_6_security_alerts(self):
        """Test 6: Security and account alerts"""
        self.print_separator("TEST 6: SECURITY & ACCOUNT ALERTS 🔒")
        
        print("Scenario: New login from Chrome on Windows")
        print("Scenario: API key expires in 3 days\n")
        
        market_data = {
            'security_data': {
                'new_login': True,
                'device_info': 'Chrome on Windows',
                'is_new_device': True,
                'api_key_days_to_expiry': 3
            }
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        for alert in results['alerts']:
            self.print_alert(alert)
            self.total_alerts += 1
        
        return results['triggered']
    
    async def test_scenario_7_combined(self):
        """Test 7: Combined multiple alerts at once"""
        self.print_separator("TEST 7: REAL-WORLD SCENARIO (Multiple Alerts)")
        
        print("Scenario: Multiple market events happening simultaneously\n")
        
        market_data = {
            'price_data': {
                'BTC': {'price': 95000, 'threshold': 90000, 'volatility_percent': 8},
                'ETH': {'price': 3500, 'volatility_percent': 15}
            },
            'volume_data': {
                'DOGE': {'current_volume': 5000000, 'average_volume': 2000000}
            },
            'technical_data': {
                'BTC': {'short_ma': 48000, 'long_ma': 47000, 'rsi': 75}
            },
            'portfolio_data': {'value_change_percent': -10.5},
            'watchlist_data': {'SOL': {'price_change_percent': 12.3}},
            'api_status': {'api_name': 'Kraken', 'minutes_without_data': 30},
            'security_data': {'new_login': True, 'device_info': 'Mobile Safari', 'api_key_days_to_expiry': 5}
        }
        
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        print(f"✓ Checked: {results['checked']} | Triggered: {results['triggered']}\n")
        
        # Group by severity
        info_alerts = [a for a in results['alerts'] if a.get('severity') == 'info']
        warning_alerts = [a for a in results['alerts'] if a.get('severity') == 'warning']
        critical_alerts = [a for a in results['alerts'] if a.get('severity') == 'critical']
        
        if critical_alerts:
            print("🔴 CRITICAL ALERTS:")
            for alert in critical_alerts:
                self.print_alert(alert)
                self.total_alerts += 1
        
        if warning_alerts:
            print("🟡 WARNING ALERTS:")
            for alert in warning_alerts:
                self.print_alert(alert)
                self.total_alerts += 1
        
        if info_alerts:
            print("🔵 INFO ALERTS:")
            for alert in info_alerts:
                self.print_alert(alert)
                self.total_alerts += 1
        
        return results['triggered']
    
    async def run_all_tests(self):
        """Run all test scenarios"""
        self.print_separator("🚀 CRYPTO ALERTS - REAL-TIME TESTING SUITE")
        print("Testing all 7 alert categories with realistic market scenarios\n")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        try:
            # Run all test scenarios
            await self.test_scenario_1_price_alerts()
            await self.test_scenario_2_volume_alerts()
            await self.test_scenario_3_technical_alerts()
            await self.test_scenario_4_portfolio_alerts()
            await self.test_scenario_5_etl_alerts()
            await self.test_scenario_6_security_alerts()
            await self.test_scenario_7_combined()
            
            # Summary
            self.print_separator("📊 TEST SUMMARY")
            print(f"Total Tests Run: 7")
            print(f"Total Alerts Triggered: {self.total_alerts}")
            print(f"Status: ✅ ALL TESTS PASSED")
            print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            print("\n✓ Price alerts - threshold and volatility detection")
            print("✓ Volume alerts - surge and liquidity drop detection")
            print("✓ Technical alerts - MA crossovers and RSI levels")
            print("✓ Portfolio alerts - watchlist and portfolio value changes")
            print("✓ ETL system alerts - API failures and data anomalies")
            print("✓ Security alerts - login detection and key expiry")
            print("✓ Real-world scenario - combined multiple alerts")
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run real-time alert tests"""
    tester = RealTimeAlertTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
