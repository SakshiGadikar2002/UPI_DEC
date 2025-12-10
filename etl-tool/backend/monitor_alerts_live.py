"""
Live Crypto Alert Monitor - Real-time dashboard showing alerts as they trigger
Usage: python monitor_alerts_live.py
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List
import sys
sys.path.insert(0, '.')

from services.alert_manager import AlertManager


class LiveAlertMonitor:
    """Monitor alerts in real-time with live dashboard"""
    
    def __init__(self):
        self.alert_manager = AlertManager(None)
        self.alerts_history: List[Dict[str, Any]] = []
        self.stats = {
            'total_checked': 0,
            'total_triggered': 0,
            'by_severity': {'info': 0, 'warning': 0, 'critical': 0},
            'by_category': {}
        }
    
    def print_dashboard(self):
        """Print live alert dashboard"""
        print("\033[2J\033[H")  # Clear screen
        
        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║          🚀 CRYPTO ALERTS - LIVE MONITORING DASHBOARD              ║")
        print("╚════════════════════════════════════════════════════════════════════╝\n")
        
        # Stats
        print("📊 STATISTICS:")
        print(f"  Total Checked: {self.stats['total_checked']}")
        print(f"  Total Triggered: {self.stats['total_triggered']}")
        print(f"  Severity Breakdown:")
        print(f"    🔵 Info: {self.stats['by_severity']['info']}")
        print(f"    🟡 Warning: {self.stats['by_severity']['warning']}")
        print(f"    🔴 Critical: {self.stats['by_severity']['critical']}\n")
        
        # Recent alerts
        print("⚡ RECENT ALERTS:")
        if self.alerts_history:
            for i, alert in enumerate(self.alerts_history[-10:], 1):
                severity_icon = {
                    'info': '🔵',
                    'warning': '🟡',
                    'critical': '🔴'
                }.get(alert['severity'], '⚪')
                
                timestamp = alert['timestamp']
                message = alert['message'][:60]
                category = alert['category']
                
                print(f"  {i}. {severity_icon} [{timestamp}] {message}...")
                print(f"     Category: {category}\n")
        else:
            print("  No alerts yet. Waiting for market events...\n")
        
        print("╔════════════════════════════════════════════════════════════════════╗")
        print(f"  Last Updated: {datetime.now().strftime('%H:%M:%S')}")
        print("  Status: 🟢 MONITORING ACTIVE")
        print("╚════════════════════════════════════════════════════════════════════╝")
    
    async def simulate_market_events(self):
        """Simulate realistic market events"""
        
        events = [
            {
                'name': 'Price Surge',
                'data': {
                    'price_data': {
                        'BTC': {'price': 95000, 'threshold': 90000, 'volatility_percent': 8}
                    }
                }
            },
            {
                'name': 'Volume Spike',
                'data': {
                    'volume_data': {
                        'DOGE': {'current_volume': 5000000, 'average_volume': 2000000}
                    }
                }
            },
            {
                'name': 'Technical Crossover',
                'data': {
                    'technical_data': {
                        'ETH': {'short_ma': 3500, 'long_ma': 3400, 'rsi': 78}
                    }
                }
            },
            {
                'name': 'API Issue',
                'data': {
                    'api_status': {
                        'api_name': 'Binance',
                        'minutes_without_data': 45
                    }
                }
            },
            {
                'name': 'Security Alert',
                'data': {
                    'security_data': {
                        'new_login': True,
                        'device_info': 'Unknown Device',
                        'api_key_days_to_expiry': 3
                    }
                }
            }
        ]
        
        return events
    
    async def check_market_conditions(self, market_data: Dict[str, Any]):
        """Check market conditions and update dashboard"""
        results = await self.alert_manager.check_crypto_alerts(market_data)
        
        self.stats['total_checked'] += results['checked']
        self.stats['total_triggered'] += results['triggered']
        
        for alert in results['alerts']:
            self.alerts_history.append(alert)
            severity = alert.get('severity', 'info')
            self.stats['by_severity'][severity] += 1
            
            category = alert.get('category', 'unknown')
            if category not in self.stats['by_category']:
                self.stats['by_category'][category] = 0
            self.stats['by_category'][category] += 1
        
        self.print_dashboard()
    
    async def run_live_monitoring(self, duration_seconds: int = 60, interval: int = 5):
        """Run live monitoring for specified duration"""
        
        start_time = datetime.now()
        events = await self.simulate_market_events()
        event_idx = 0
        
        print(f"🟢 Starting live monitoring for {duration_seconds} seconds...")
        print(f"   New market event every {interval} seconds")
        
        while (datetime.now() - start_time).total_seconds() < duration_seconds:
            # Get next event
            event = events[event_idx % len(events)]
            event_idx += 1
            
            # Check alerts
            await self.check_market_conditions(event['data'])
            
            # Wait before next check
            await asyncio.sleep(interval)
        
        print("\n\n✅ Monitoring completed!")


async def main():
    """Main entry point"""
    monitor = LiveAlertMonitor()
    
    # Run for 60 seconds with 5-second intervals
    await monitor.run_live_monitoring(duration_seconds=60, interval=5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⛔ Monitoring stopped by user")
