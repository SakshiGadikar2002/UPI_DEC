# 📊 ALERTS IMPLEMENTED IN MAIN SYSTEM

## Overview
Your system has **6 major alert categories** with **11+ specific alert types**. Only **WARNING** and **CRITICAL** severity alerts trigger emails (INFO alerts are logged but not emailed).

---

## 🔔 Alert Categories & Types

### 1. **💰 PRICE ALERTS** (Price Tracking)
**Purpose**: Monitor cryptocurrency price movements

- **Price Threshold Alert**: Alert when price reaches/exceeds a target level
  - Example: "BTC price reached ₹95,000"
  - Severity: WARNING
  
- **Price Volatility Alert**: Alert when price changes significantly in short timeframe
  - Example: "BTC price increased 8% in 1 hour"
  - Severity: WARNING

---

### 2. **📊 VOLUME & LIQUIDITY ALERTS** (Trading Activity)
**Purpose**: Monitor trading volume and market liquidity

- **Volume Surge Alert**: Alert when trading volume spikes dramatically
  - Example: "ETH volume increased by 150%"
  - Severity: WARNING
  
- **Liquidity Drop Alert**: Alert when market liquidity decreases significantly
  - Example: "DOGE liquidity dropped below threshold"
  - Severity: WARNING

---

### 3. **📈 TECHNICAL ALERTS** (Price Patterns)
**Purpose**: Monitor technical indicators and market patterns

- **Moving Average Crossover Alert**: Alert when price crosses moving averages
  - Example: "Price crossed 200-day moving average"
  - Severity: WARNING
  
- **RSI Level Alert** (Overbought/Oversold): Alert when momentum indicators show extreme levels
  - Example: "ETH RSI is 78 (overbought)"
  - Example: "BTC RSI is 25 (oversold)"
  - Severity: WARNING

---

### 4. **💼 PORTFOLIO ALERTS** (Investment Tracking)
**Purpose**: Monitor portfolio performance and holdings

- **Portfolio Change Alert**: Alert when portfolio value changes significantly
  - Example: "Your portfolio lost 10.5% today"
  - Severity: WARNING
  
- **Watchlist Movement Alert**: Alert when watchlisted assets move significantly
  - Example: "Watched asset XRP up 25%"
  - Severity: WARNING

---

### 5. **⚙️ ETL SYSTEM ALERTS** (Data Integrity)
**Purpose**: Monitor data collection and system health

- **API Failure Alert**: Alert when exchange API connection fails
  - Example: "Binance not responding — using cached data"
  - Severity: CRITICAL ⚠️
  
- **ETL Job Failure Alert**: Alert when data pipeline job fails
  - Example: "ETL job failed: Connection timeout"
  - Severity: CRITICAL ⚠️
  
- **Data Anomaly Alert**: Alert when unusual data patterns detected
  - Example: "Unusual data spike: 500% volume increase"
  - Severity: WARNING

---

### 6. **🔒 SECURITY ALERTS** (Account Safety)
**Purpose**: Monitor account security and access

- **New Login Alert**: Alert when account accessed from new device/location
  - Example: "New login detected from Chrome on Windows"
  - Severity: WARNING
  
- **API Key Expiry Alert**: Alert when API credentials expiring soon
  - Example: "Your API key expires in 3 days"
  - Severity: CRITICAL ⚠️

---

## 📧 Email Alert Behavior

### What Gets Emailed?
✅ **WARNING severity alerts** - Moderate importance, needs attention  
✅ **CRITICAL severity alerts** - High importance, immediate attention needed  
❌ **INFO severity alerts** - Logged to database but not emailed  

### Email Format
- **Professional HTML format** with color-coded severity indicators
- **IST Timezone** - All timestamps in Indian Standard Time
- **Clear sections** - Alert message, Details, Category, Time
- **Color-coded** - Red for critical, Orange for warning, Blue for info

### Email Frequency
- Checked every **5 minutes**
- One email per triggered alert
- All recipients receive all important alerts

---

## 🎯 Example Alerts You'll Receive

### 🔴 CRITICAL (Immediate Action Needed)
1. **"Binance API offline"** - Data source unavailable
2. **"ETL job failed"** - Data collection stopped
3. **"Your API key expires in 3 days"** - Credentials expiring soon

### 🟡 WARNING (Review & Monitor)
1. **"BTC price reached ₹95,000"** - Price milestone hit
2. **"ETH volume increased 150%"** - Unusual trading activity
3. **"Portfolio lost 10.5% today"** - Significant portfolio change
4. **"RSI 78 (overbought)"** - Technical indicator extreme
5. **"New login from Chrome on Windows"** - Account access from new device

---

## 📋 Alert Summary Table

| Category | Alert Type | Severity | Email? | Example |
|----------|-----------|----------|--------|---------|
| Price | Threshold | WARNING | ✅ | Price reached ₹95,000 |
| Price | Volatility | WARNING | ✅ | Price +8% in 1h |
| Volume | Surge | WARNING | ✅ | Volume +150% |
| Volume | Liquidity Drop | WARNING | ✅ | Liquidity below threshold |
| Technical | MA Crossover | WARNING | ✅ | Price crossed MA |
| Technical | RSI Level | WARNING | ✅ | RSI 78 (overbought) |
| Portfolio | Value Change | WARNING | ✅ | Portfolio -10.5% |
| Portfolio | Watchlist | WARNING | ✅ | Watched asset +25% |
| ETL | API Failure | **CRITICAL** | ✅ | API offline |
| ETL | Job Failure | **CRITICAL** | ✅ | Job failed |
| ETL | Anomaly | WARNING | ✅ | Data spike 500% |
| Security | New Login | WARNING | ✅ | Login from new device |
| Security | Key Expiry | **CRITICAL** | ✅ | Key expires in 3 days |

---

## 🔧 Configuration

### Email Recipients
Set in `.env`:
```
ALERT_EMAIL_RECIPIENTS=aishwarya.sakharkar@arithwise.com
# Or multiple:
ALERT_EMAIL_RECIPIENTS=user1@company.com,user2@company.com
```

### Alert Thresholds (Optional)
Customize in `.env`:
```
ALERT_PRICE_CHANGE=5              # Alert if price changes 5%
ALERT_VOLUME_SPIKE=100            # Alert if volume increases 100%
ALERT_RSI_OVERBOUGHT=70           # Alert if RSI > 70
ALERT_RSI_OVERSOLD=30             # Alert if RSI < 30
ALERT_PORTFOLIO_LOSS=10           # Alert if portfolio drops 10%
```

---

## 📱 Sample Email

```
Subject: 🔴 [CRITICAL] Binance not responding — using cached data

[Professional HTML Email with:]
- Red header for CRITICAL severity
- Alert category: ⚙️ System Alert
- Clear message about what happened
- Details/Reason section
- Time in IST format
- Footer with automated alert note
```

---

## ✅ Key Features

✅ **Real-time Detection** - Checks every 5 minutes  
✅ **Smart Filtering** - Only important alerts (WARNING/CRITICAL)  
✅ **Professional Format** - Beautiful, easy-to-read emails  
✅ **IST Timezone** - All times in Indian Standard Time  
✅ **Color Coded** - Visual severity indicators  
✅ **Detailed Info** - Full context in each alert  
✅ **Database Logged** - All alerts stored in `alert_logs` table  
✅ **Auto-Triggered** - No manual setup needed  

---

**Status**: ✅ Fully Implemented & Ready to Use
