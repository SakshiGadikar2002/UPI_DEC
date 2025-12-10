# Quick Reference: 7 Crypto Alerts at a Glance

## 1. 📈 PRICE ALERTS
- **Price Threshold**: Stock/support level breached
- **Price Volatility**: Sudden sharp moves (5%+ in 1h)

## 2. 📊 VOLUME & LIQUIDITY ALERTS
- **Volume Surge**: Trading activity jumps (50%+ increase)
- **Liquidity Drop**: Order book thins out (slippage risk)

## 3. 🔧 TECHNICAL ALERTS
- **Moving Average Crossover**: Bullish/bearish trend signal
- **RSI Levels**: Overbought (>70) or oversold (<30)

## 4. 💼 PORTFOLIO ALERTS
- **Portfolio Change**: Total holdings up/down (10%+ in a day)
- **Watchlist Movement**: Tracked assets move (10%+ change)

## 5. ⚙️ ETL SYSTEM ALERTS
- **API Failure**: Data feed offline (30+ minutes without data)
- **Job Failure**: Scheduled tasks crash (timeout/error)
- **Data Anomaly**: Suspicious price spike (40%+ in 1 minute)

## 6. 🔒 SECURITY ALERTS
- **New Login**: Unrecognized device accessing account
- **API Key Expiry**: Credentials expire soon (7-day warning)

---

## Severity Levels

🔵 **INFO** - Informational (FYI)
🟡 **WARNING** - Important (Monitor)
🔴 **CRITICAL** - Urgent (Action Required)

---

## Integration Code Example

```python
# Quick integration in main.py
market_data = {
    'price_data': {'BTC': {'price': 95000, 'threshold': 90000}},
    'volume_data': {'DOGE': {'current_volume': 5M, 'average_volume': 2M}},
    'technical_data': {'ETH': {'short_ma': 3500, 'long_ma': 3400, 'rsi': 78}},
    'portfolio_data': {'value_change_percent': -10.5},
    'api_status': {'api_name': 'Binance', 'minutes_without_data': 45},
    'security_data': {'new_login': True, 'api_key_days_to_expiry': 3}
}

results = await alert_manager.check_crypto_alerts(market_data)
# Returns: {triggered: 5, alerts: [...], checked: 9}
```

---

## Alert Response Format

```json
{
  "message": "BTC price reached ₹95,000.00",
  "category": "price_alerts",
  "reason": "Price above threshold",
  "severity": "warning",
  "timestamp": "2025-12-10T10:27:34",
  "metadata": {
    "symbol": "BTC",
    "current_price": 95000.0,
    "threshold": 90000.0
  }
}
```

---

**For full details, see `CRYPTO_ALERTS_SUMMARY.md`**
