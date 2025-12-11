# Crypto Alert Engine - Complete Summary

## Overview
The Crypto Alert Engine is a comprehensive alert system integrated into the Alert Manager that monitors cryptocurrency markets and system health. It detects 7 categories of alerts with real-time notifications.

---

## 7 Alert Categories

### 1. **PRICE ALERTS** (`price_alerts`)
Monitors cryptocurrency price movements

**Sub-alerts:**
- **Price Threshold Alert**: Triggers when price crosses a specified threshold
  - Example: BTC reaches $95,000
  - Severity: `warning`
  - Use Case: Track resistance/support levels

- **Price Volatility Alert**: Triggers when price change exceeds percentage threshold in a time window
  - Example: ETH increased 12.5% in 1 hour
  - Severity: `warning`
  - Use Case: Detect unusual price movements (high volatility trading opportunities)

---

### 2. **VOLUME & LIQUIDITY ALERTS** (`volume_liquidity_alerts`)
Monitors trading volume and liquidity conditions

**Sub-alerts:**
- **Volume Surge Alert**: Triggers when trading volume increases significantly
  - Example: DOGE volume increased 150% from average
  - Severity: `warning`
  - Use Case: Detect high-volume trading activity (institutional interest, breakouts)

- **Liquidity Drop Alert**: Triggers when available liquidity falls below threshold
  - Example: Liquidity dropped below 2% threshold
  - Severity: `critical`
  - Use Case: Warn about thin order books (slippage risk)

---

### 3. **TECHNICAL & TREND ALERTS** (`trend_technical_alerts`)
Monitors technical indicators and market trends

**Sub-alerts:**
- **Moving Average Crossover Alert**: Triggers when short-term MA crosses long-term MA
  - Example: BTC short-term MA crossed above long-term MA (bullish)
  - Severity: `info`
  - Use Case: Identify trend changes (momentum signals)

- **RSI Level Alert**: Triggers when RSI enters overbought (>70) or oversold (<30) conditions
  - Example: ETH RSI is 78 (overbought - potential pullback)
  - Severity: `warning`
  - Use Case: Warn of potential reversals/corrections

---

### 4. **PORTFOLIO & WATCHLIST ALERTS** (`portfolio_watchlist_alerts`)
Monitors personal portfolio performance and watchlisted assets

**Sub-alerts:**
- **Portfolio Change Alert**: Triggers when total portfolio value changes significantly
  - Example: Your portfolio lost 10.5% today
  - Severity: `warning`
  - Use Case: Monitor overall portfolio health

- **Watchlist Movement Alert**: Triggers when watched assets move beyond threshold
  - Example: SOL in your watchlist gained 12.3%
  - Severity: `info`
  - Use Case: Track specific assets of interest

---

### 5. **ETL SYSTEM & DATA QUALITY ALERTS** (`etl_system_alerts`)
Monitors ETL pipeline health, API connectivity, and data quality

**Sub-alerts:**
- **API Failure Alert**: Triggers when API stops responding or data lags
  - Example: Binance API not responding — using cached data for 45 minutes
  - Severity: `critical`
  - Use Case: Alert to data source issues

- **ETL Job Failure Alert**: Triggers when scheduled jobs fail
  - Example: ETL job 'Daily Price Aggregation' failed due to timeout
  - Severity: `critical`
  - Use Case: Monitor data pipeline operations

- **Data Anomaly Alert**: Triggers when suspicious price changes detected
  - Example: BTC price changed 40% in 1 minute (possible data issue)
  - Severity: `critical`
  - Use Case: Detect data quality problems (feed errors, bugs)

---

### 6. **SECURITY & ACCOUNT ALERTS** (`security_account_alerts`)
Monitors account security events and API key status

**Sub-alerts:**
- **New Login Alert**: Triggers when login from unrecognized device detected
  - Example: New login detected from Chrome on Windows
  - Severity: `warning`
  - Use Case: Detect unauthorized access attempts

- **API Key Expiry Alert**: Triggers when API key approaches expiration
  - Example: Your API key expires in 3 days
  - Severity: `critical`
  - Use Case: Prevent service interruptions from expired credentials

---

## Integration with Alert Manager

### Usage in Main System
```python
# In main.py or scheduler
alert_manager = AlertManager(db_pool)

# Market data structure for crypto alerts
market_data = {
    'price_data': {
        'BTC': {'price': 95000, 'threshold': 90000, 'volatility_percent': 5},
        'ETH': {'price': 3500, 'volatility_percent': 12.5}
    },
    'volume_data': {
        'DOGE': {'current_volume': 5000000, 'average_volume': 2000000}
    },
    'technical_data': {
        'BTC': {'short_ma': 48000, 'long_ma': 47000, 'rsi': 65}
    },
    'portfolio_data': {'value_change_percent': -10.5},
    'watchlist_data': {
        'SOL': {'price_change_percent': 12.3}
    },
    'api_status': {
        'api_name': 'Binance API',
        'status': 'offline',
        'minutes_without_data': 45
    },
    'etl_jobs': [
        {'name': 'Daily Price Aggregation', 'status': 'failed', 'error_type': 'timeout'}
    ],
    'security_data': {
        'new_login': True,
        'device_info': 'Chrome on Windows',
        'api_key_days_to_expiry': 3
    }
}

# Check crypto alerts
results = await alert_manager.check_crypto_alerts(market_data)
# Returns: {'checked': 9, 'triggered': 5, 'alerts': [...]}
```

### Response Format
Each triggered alert returns a standardized `CryptoAlertResponse`:
```json
{
  "message": "BTC price reached ₹95,000.00",
  "category": "price_alerts",
  "reason": "Price above threshold of ₹90,000.00",
  "severity": "warning",
  "timestamp": "2025-12-10T10:27:34.006944",
  "metadata": {
    "symbol": "BTC",
    "current_price": 95000.0,
    "threshold": 90000.0,
    "comparison": "greater"
  }
}
```

---

## Severity Levels

| Severity | Color | Meaning | Action |
|----------|-------|---------|--------|
| **info** | Blue | Informational | FYI only |
| **warning** | Yellow | Important | Review and monitor |
| **critical** | Red | Urgent | Immediate action required |

---

## Alert Filtering & Retrieval

The crypto alert manager supports filtering:

```python
# Get all alerts
all_alerts = crypto_manager.get_alerts()

# Get by category
price_alerts = crypto_manager.get_alerts(category='price_alerts')

# Get by severity
critical_alerts = crypto_manager.get_alerts(severity='critical')

# Get by both
critical_price = crypto_manager.get_alerts(
    category='price_alerts', 
    severity='critical'
)

# Clear all alerts (housekeeping)
crypto_manager.clear_alerts()
```

---

## Notification Integration

All triggered alerts can be sent to multiple channels:
- **Email**: Office 365 SMTP (ariths@arithwise.com)
- **Slack**: Via webhook URL (configurable)
- **In-App**: Logged to alert_logs table

---

## Database Storage

Alerts are stored in:
- **alert_logs** table: Full alert details and metadata
- **alert_tracking** table: Alert frequency tracking (cooldown, daily limits)

Fields:
- `rule_id`: Source rule (can be NULL for crypto alerts)
- `alert_type`: Category (price_alerts, volume_liquidity_alerts, etc.)
- `title`: Short description
- `message`: Full alert message
- `severity`: info/warning/critical
- `metadata`: JSON with alert-specific data
- `status`: pending/acknowledged/resolved
- `created_at`: Timestamp

---

## Real-World Usage Examples

### Example 1: Price Alert on High Volatility
**Goal**: Get notified when BTC moves >10% in 1 hour
```python
market_data = {
    'price_data': {
        'BTC': {
            'price': 48000,
            'volatility_percent': 12.5,  # >10% threshold
            'time_window': '1h'
        }
    }
}
# → Triggers: "BTC price increased 12.50% in 1h"
```

### Example 2: System Health Check
**Goal**: Monitor data pipeline reliability
```python
market_data = {
    'api_status': {
        'api_name': 'Binance API',
        'minutes_without_data': 45  # >30 min threshold
    },
    'etl_jobs': [
        {'name': 'Price Sync', 'status': 'failed', 'error_message': 'Timeout'}
    ]
}
# → Triggers 2 critical alerts for immediate attention
```

### Example 3: Security Watch
**Goal**: Monitor account access and key expiry
```python
market_data = {
    'security_data': {
        'new_login': True,
        'device_info': 'Safari on iPhone',
        'api_key_days_to_expiry': 2  # <7 days
    }
}
# → Triggers 2 alerts: "New login detected" + "API key expires in 2 days"
```

---

## Architecture

```
AlertManager (services/alert_manager.py)
├── CryptoAlertManager
│   ├── PriceAlertEngine
│   ├── VolumeAlertEngine
│   ├── TechnicalAlertEngine
│   ├── PortfolioAlertEngine
│   ├── ETLSystemAlertEngine
│   └── SecurityAlertEngine
├── NotificationService (email/Slack)
└── Database (PostgreSQL)
```

---

## Testing

Run the comprehensive test suite:
```bash
python backend/test_crypto_alerts.py
```

Output shows all 7 alert types in action with example data.

---

## Notes

- ⚠️ **Do NOT use example data in production** - examples are for demonstration only
- ✓ All alerts are thread-safe and async-compatible
- ✓ Supports alert filtering by category and severity
- ✓ Integrates seamlessly with existing AlertManager and notification system
- ✓ Metadata is stored as JSON for flexible querying
- ✓ Logging available for all alerts for audit trails
