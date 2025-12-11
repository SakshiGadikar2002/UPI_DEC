# 🧪 Alert System Testing Guide

Complete testing procedures for the Alert System implementation.

---

## Phase 1: Pre-Testing Setup ✅

### Step 1.1: Verify Installation

```bash
# Navigate to backend
cd backend

# Verify requirements are installed
pip list | findstr "psutil fastapi sqlalchemy asyncpg apscheduler"
```

**Expected Output:**
```
psutil             5.9.6
fastapi            0.104.1
sqlalchemy         2.0.x
asyncpg            0.29.0
apscheduler        3.10.4
```

### Step 1.2: Check Environment Configuration

```bash
# Verify .env file exists
ls -la .env
```

**If missing**, copy from template:
```bash
cp .env.example .env
```

### Step 1.3: Verify Database

```bash
# Start PostgreSQL (if not running)
# Windows: Use pgAdmin or command line
psql -U your_user -d your_database

# Check if tables exist
\dt alert_*
\dt price_history
```

**Expected Output:**
```
           List of relations
 Schema |        Name         | Type  | Owner
--------+---------------------+-------+-------
 public | alert_logs          | table | user
 public | alert_rules         | table | user
 public | alert_tracking      | table | user
 public | notification_queue  | table | user
 public | price_history       | table | user
```

---

## Phase 2: Backend Startup Tests 🚀

### Step 2.1: Start the Backend Server

```bash
# From backend directory
cd backend
python -m uvicorn main:app --reload
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
INFO:     Alert scheduler started successfully
```

### Step 2.2: Verify API is Accessible

```bash
# In another terminal/PowerShell
curl http://localhost:8000/docs
```

**Expected Result:** Swagger UI loads successfully at `http://localhost:8000/docs`

### Step 2.3: Check Alert Endpoints

```bash
# Access Swagger UI
curl http://localhost:8000/docs

# Or check in browser: http://localhost:8000/docs
# Look for /api/alerts section with 10+ endpoints
```

**Expected:** All endpoints visible in Swagger UI with green "GET/POST/PUT/DELETE" labels

---

## Phase 3: Database Integration Tests 📊

### Test 3.1: Dashboard Endpoint

```bash
curl -X GET "http://localhost:8000/api/alerts/dashboard" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK):**
```json
{
  "total_rules": 0,
  "active_rules": 0,
  "alerts_today": 0,
  "critical_count": 0,
  "recent_alerts": [],
  "rules_by_type": {},
  "hourly_alert_distribution": []
}
```

### Test 3.2: Create Alert Rule (Price Threshold)

```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC High Price Alert",
    "description": "Alert when BTC exceeds $50,000",
    "alert_type": "price_threshold",
    "enabled": true,
    "severity": "critical",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "greater_than",
    "notification_channels": ["email"],
    "email_recipients": ["your-email@gmail.com"],
    "cooldown_minutes": 30,
    "max_alerts_per_day": 10
  }'
```

**Expected Response (201 Created):**
```json
{
  "id": 1,
  "name": "BTC High Price Alert",
  "alert_type": "price_threshold",
  "enabled": true,
  "created_at": "2025-12-09T10:30:45.123456",
  "updated_at": "2025-12-09T10:30:45.123456"
}
```

**What gets created in DB:**
- ✅ Row in `alert_rules` table with alert configuration
- ✅ Row in `alert_tracking` table for cooldown tracking

### Test 3.3: List Alert Rules

```bash
curl -X GET "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK):**
```json
{
  "total": 1,
  "rules": [
    {
      "id": 1,
      "name": "BTC High Price Alert",
      "alert_type": "price_threshold",
      "enabled": true,
      "symbol": "BTC",
      "threshold_value": 50000,
      "notification_channels": ["email"]
    }
  ]
}
```

### Test 3.4: Get Single Rule

```bash
curl -X GET "http://localhost:8000/api/alerts/rules/1" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK):**
Complete rule details with all configuration fields

---

## Phase 4: Alert Triggering Tests 🔔

### Test 4.1: Insert Price Data (Trigger Price Threshold Alert)

#### Option A: Insert via SQL

```bash
# Connect to PostgreSQL
psql -U your_user -d your_database

# Insert a price higher than threshold
INSERT INTO price_history (symbol, price, source, created_at) 
VALUES ('BTC', 51000, 'test_api', NOW());

# Verify insertion
SELECT * FROM price_history WHERE symbol = 'BTC' ORDER BY created_at DESC LIMIT 1;
```

#### Option B: Use Python Script

Create `test_price.py`:
```python
import asyncio
import asyncpg
from datetime import datetime

async def insert_test_price():
    conn = await asyncpg.connect('postgresql://user:password@localhost/dbname')
    
    # Insert price above threshold
    await conn.execute('''
        INSERT INTO price_history (symbol, price, source, created_at)
        VALUES ('BTC', 51000, 'test_script', $1)
    ''', datetime.now())
    
    # Insert volatility test data
    await conn.execute('''
        INSERT INTO price_history (symbol, price, source, created_at)
        VALUES ('ETH', 3500, 'test_script', $1)
    ''', datetime.now())
    
    await conn.close()

asyncio.run(insert_test_price())
```

Run:
```bash
python test_price.py
```

### Test 4.2: Manually Trigger Alert Check

```bash
curl -X POST "http://localhost:8000/api/alerts/check" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK):**
```json
{
  "checked_rules": 1,
  "triggered_alerts": 1,
  "sent_notifications": 1,
  "failed_notifications": 0,
  "errors": []
}
```

**What happens in DB:**
- ✅ New row added to `alert_logs` table
- ✅ `alert_tracking` updated with new count
- ✅ Row added to `notification_queue` table

### Test 4.3: View Alert History

```bash
curl -X GET "http://localhost:8000/api/alerts/logs" \
  -H "Content-Type: application/json"
```

**Expected Response (200 OK):**
```json
{
  "total": 1,
  "alerts": [
    {
      "id": 1,
      "rule_id": 1,
      "status": "pending",
      "severity": "critical",
      "message": "Price threshold exceeded: BTC is 51000 (threshold: 50000)",
      "created_at": "2025-12-09T10:35:20.123456",
      "triggered_at": "2025-12-09T10:35:20.123456"
    }
  ]
}
```

---

## Phase 5: All Alert Type Tests 🎯

### Test 5.1: Price Threshold Alert

**Create Rule:**
```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Price High",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "greater_than",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email"],
    "email_recipients": ["test@gmail.com"],
    "cooldown_minutes": 30,
    "max_alerts_per_day": 5
  }'
```

**Trigger:**
```bash
# Insert price above threshold
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 51000, 'test', NOW());"

# Check alerts
curl -X POST "http://localhost:8000/api/alerts/check"
```

**Verify:**
- ✅ Alert created in `alert_logs`
- ✅ Notification queued
- ✅ Alert status is "pending" or "sent"

---

### Test 5.2: Volatility Alert

**Create Rule:**
```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ETH Volatility Alert",
    "alert_type": "volatility",
    "symbol": "ETH",
    "volatility_threshold": 5,
    "volatility_window_minutes": 10,
    "enabled": true,
    "severity": "warning",
    "notification_channels": ["email"],
    "email_recipients": ["test@gmail.com"],
    "cooldown_minutes": 15,
    "max_alerts_per_day": 10
  }'
```

**Trigger (insert prices with >5% change in 10 minutes):**
```bash
# In PostgreSQL:
INSERT INTO price_history (symbol, price, source, created_at) 
VALUES ('ETH', 3000, 'test', NOW() - INTERVAL '10 minutes');

INSERT INTO price_history (symbol, price, source, created_at) 
VALUES ('ETH', 3160, 'test', NOW()); -- 5.33% change
```

**Verify:**
- ✅ Volatility detected and alert created
- ✅ Percentage calculation correct: ((3160-3000)/3000)*100 = 5.33%

---

### Test 5.3: Data Missing Alert

**Create Rule:**
```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Data Missing",
    "alert_type": "data_missing",
    "data_source": "binance_api",
    "missing_minutes": 30,
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email"],
    "email_recipients": ["test@gmail.com"],
    "cooldown_minutes": 60,
    "max_alerts_per_day": 3
  }'
```

**Trigger (no data for 30+ minutes):**
```bash
# Stop your data collection script (if running)
# Or set last API timestamp to >30 minutes ago:

psql -U user -d db -c "
UPDATE api_connector_data 
SET last_fetch = NOW() - INTERVAL '31 minutes' 
WHERE source = 'binance_api';
"

# Check alerts
curl -X POST "http://localhost:8000/api/alerts/check"
```

**Verify:**
- ✅ Alert triggers when data is >30 minutes stale
- ✅ Alert status updates

---

### Test 5.4: System Health Alert

**Create Rule:**
```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "System Health Check",
    "alert_type": "system_health",
    "health_check_type": "disk_space",
    "health_threshold": 80,
    "enabled": true,
    "severity": "warning",
    "notification_channels": ["email"],
    "email_recipients": ["test@gmail.com"],
    "cooldown_minutes": 120,
    "max_alerts_per_day": 2
  }'
```

**Check System Health:**
```bash
# This checks:
# - Disk usage % (threshold: 80%)
# - Memory usage % (threshold: 85%)
# - CPU usage % (threshold: 90%)
# - Database connection status

curl -X POST "http://localhost:8000/api/alerts/check"
```

**Expected Behavior:**
- ✅ Alert triggers if disk usage > 80%
- ✅ Alert triggers if memory usage > 85%
- ✅ Alert triggers if CPU usage > 90%
- ✅ Alert triggers if database unreachable

---

## Phase 6: Notification Tests 📧

### Test 6.1: Email Notification

**Prerequisites:**
1. Create `.env` with SMTP credentials:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password  # Not regular password!
```

**For Gmail:**
1. Enable 2-factor authentication
2. Generate app-specific password: https://myaccount.google.com/apppasswords
3. Use that password in .env

**Test Email Send:**
```bash
# Create alert with email notification
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Email Alert",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "greater_than",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email"],
    "email_recipients": ["your-email@gmail.com"],
    "cooldown_minutes": 30,
    "max_alerts_per_day": 10
  }'

# Trigger it
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 51000, 'test', NOW());"

curl -X POST "http://localhost:8000/api/alerts/check"
```

**Verify:**
- ✅ Check your email inbox
- ✅ Email contains alert details
- ✅ Email subject includes severity level
- ✅ Notification status in `notification_queue` is "sent"

**Troubleshoot Email:**
```bash
# Check notification queue
psql -U user -d db -c "SELECT * FROM notification_queue ORDER BY created_at DESC LIMIT 5;"

# Expected columns:
# - channel: 'email'
# - status: 'sent' or 'failed'
# - error_message: (if failed)
# - retry_count: number of retries
```

---

### Test 6.2: Slack Notification

**Prerequisites:**
1. Create Slack app at https://api.slack.com/apps
2. Enable Incoming Webhooks
3. Create webhook URL
4. Add to `.env`:

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Test Slack:**
```bash
# Create alert with Slack notification
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Slack Alert",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "greater_than",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["slack"],
    "cooldown_minutes": 30,
    "max_alerts_per_day": 10
  }'

# Trigger it
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 51000, 'test', NOW());"

curl -X POST "http://localhost:8000/api/alerts/check"
```

**Verify:**
- ✅ Check your Slack channel
- ✅ Message includes alert severity (color-coded)
- ✅ Message contains alert details
- ✅ Notification status is "sent"

---

### Test 6.3: Multi-Channel (Email + Slack)

```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Multi-Channel Alert",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "greater_than",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email", "slack"],
    "email_recipients": ["your-email@gmail.com"],
    "cooldown_minutes": 30,
    "max_alerts_per_day": 10
  }'

# Trigger
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 51000, 'test', NOW());"

curl -X POST "http://localhost:8000/api/alerts/check"
```

**Verify:**
- ✅ Email received
- ✅ Slack message posted
- ✅ Both notifications queued in `notification_queue`

---

## Phase 7: API Operation Tests 🔧

### Test 7.1: Update Alert Rule

```bash
curl -X PUT "http://localhost:8000/api/alerts/rules/1" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Updated Alert",
    "threshold_value": 55000,
    "enabled": true,
    "notification_channels": ["email", "slack"]
  }'
```

**Expected:** Rule updated in database

**Verify:**
```bash
curl -X GET "http://localhost:8000/api/alerts/rules/1"
# Should show updated values
```

---

### Test 7.2: Disable/Enable Alert

```bash
# Disable
curl -X PUT "http://localhost:8000/api/alerts/rules/1" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Enable
curl -X PUT "http://localhost:8000/api/alerts/rules/1" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

**Verify:**
- ✅ Disabled rules don't trigger alerts
- ✅ Enabled rules do trigger alerts

---

### Test 7.3: Acknowledge Alert

```bash
# Create and trigger an alert first
# Then acknowledge it
curl -X POST "http://localhost:8000/api/alerts/logs/1/acknowledge" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "id": 1,
  "status": "acknowledged",
  "acknowledged_at": "2025-12-09T10:40:00.123456"
}
```

**Verify:**
- ✅ Alert status changed to "acknowledged"
- ✅ Timestamp updated in database

---

### Test 7.4: Delete Alert Rule

```bash
curl -X DELETE "http://localhost:8000/api/alerts/rules/1"
```

**Expected:** 
- ✅ Rule deleted from `alert_rules`
- ✅ Tracking entry deleted from `alert_tracking`
- ✅ Response is 204 No Content or 200 OK

**Verify:**
```bash
curl -X GET "http://localhost:8000/api/alerts/rules/1"
# Should return 404 Not Found
```

---

## Phase 8: Scheduler & Cooldown Tests ⏰

### Test 8.1: Automatic Alert Checking (Scheduler)

**Setup:**
1. Create an alert rule (from Test 5.1)
2. Insert test price data
3. Wait for scheduler to run (every 1 minute)

**Monitor in Backend Console:**
```
INFO:     Alert scheduler checking rules at 2025-12-09 10:45:00
INFO:     Checked 3 rules, triggered 1 alert
INFO:     Sending notifications for alert ID: 123
```

**Verify:**
- ✅ Alert created without manual `/check` call
- ✅ Check logs in `alert_logs` table
- ✅ Notifications queued

---

### Test 8.2: Cooldown Period (30 minute gap)

**Setup:**
```bash
# Create alert with 30-minute cooldown
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cooldown Test",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "greater_than",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email"],
    "email_recipients": ["test@gmail.com"],
    "cooldown_minutes": 30,
    "max_alerts_per_day": 5
  }'
```

**Test Cooldown:**
```bash
# Insert first price (triggers alert)
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 51000, 'test', NOW());"
curl -X POST "http://localhost:8000/api/alerts/check"
# Result: Alert created ✅

# Immediately insert second price
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 52000, 'test', NOW());"
curl -X POST "http://localhost:8000/api/alerts/check"
# Result: Alert NOT created (cooldown active) ✅

# Check alert_tracking table
psql -U user -d db -c "SELECT rule_id, last_alert_time FROM alert_tracking WHERE rule_id = 1;"
```

**Expected Behavior:**
- ✅ First check triggers alert
- ✅ Second check within 30 min doesn't trigger
- ✅ `last_alert_time` shows timestamp of first alert

---

### Test 8.3: Daily Limit (max_alerts_per_day)

**Create rule with low daily limit:**
```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Limit Test",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "greater_than",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email"],
    "email_recipients": ["test@gmail.com"],
    "cooldown_minutes": 0,
    "max_alerts_per_day": 2
  }'
```

**Test:**
```bash
# First alert
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 51000, 'test', NOW() - INTERVAL '10 minutes');"
curl -X POST "http://localhost:8000/api/alerts/check"
# Result: Alert 1 created ✅

# Second alert
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 52000, 'test', NOW() - INTERVAL '5 minutes');"
curl -X POST "http://localhost:8000/api/alerts/check"
# Result: Alert 2 created ✅

# Third alert
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', 53000, 'test', NOW());"
curl -X POST "http://localhost:8000/api/alerts/check"
# Result: Alert NOT created (daily limit reached) ✅
```

**Verify:**
```bash
psql -U user -d db -c "SELECT COUNT(*) FROM alert_logs WHERE rule_id = 2 AND created_at::date = CURRENT_DATE;"
# Should show 2 (not 3)
```

---

## Phase 9: Error Handling & Edge Cases 🚨

### Test 9.1: Invalid Alert Configuration

**Test 1: Missing Required Fields**
```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Incomplete Alert"
    # Missing alert_type, enabled, etc.
  }'
```

**Expected:** 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "loc": ["body", "alert_type"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

### Test 9.2: Invalid Operator

```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Invalid Operator",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "invalid_op",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email"],
    "email_recipients": ["test@gmail.com"]
  }'
```

**Expected:** 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "loc": ["body", "operator"],
      "msg": "unexpected value; permitted: 'greater_than', 'less_than', 'equal_to'",
      "type": "enum"
    }
  ]
}
```

---

### Test 9.3: Missing Email When Email Notification Selected

```bash
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "No Email",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "threshold_value": 50000,
    "operator": "greater_than",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email"]
    # Missing email_recipients!
  }'
```

**Expected:** 422 Unprocessable Entity with message about missing email

---

### Test 9.4: Database Connection Failure

**Simulate by stopping PostgreSQL:**
```bash
# Stop PostgreSQL
# On Windows: services.msc → PostgreSQL → Stop
# Or: pg_ctl stop

# Try to create alert
curl -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

**Expected:** 500 Internal Server Error
```json
{
  "detail": "Database connection failed"
}
```

---

### Test 9.5: Non-existent Alert Rule

```bash
curl -X GET "http://localhost:8000/api/alerts/rules/99999"
```

**Expected:** 404 Not Found
```json
{
  "detail": "Alert rule not found"
}
```

---

## Phase 10: Database Verification Tests 🔍

### Test 10.1: Verify All Tables Created

```bash
psql -U user -d db -c "\dt alert_* price_*"
```

**Expected:**
```
            List of relations
 Schema |        Name         | Type  | Owner
--------+---------------------+-------+-------
 public | alert_logs          | table | user
 public | alert_rules         | table | user
 public | alert_tracking      | table | user
 public | notification_queue  | table | user
 public | price_history       | table | user
```

---

### Test 10.2: Verify Table Structure

```bash
# Check alert_rules columns
psql -U user -d db -c "\d alert_rules"

# Check alert_logs columns
psql -U user -d db -c "\d alert_logs"

# Check indexes
psql -U user -d db -c "\di alert_*"
```

**Expected:** All columns present with correct types

---

### Test 10.3: Verify Data Integrity

```bash
# Check foreign keys
psql -U user -d db -c "
SELECT constraint_name, table_name 
FROM information_schema.table_constraints 
WHERE constraint_type = 'FOREIGN KEY' 
AND table_name LIKE 'alert%';"

# Check indexes
psql -U user -d db -c "
SELECT indexname FROM pg_indexes 
WHERE tablename LIKE 'alert%' OR tablename = 'price_history';"
```

---

### Test 10.4: View Alert History

```bash
# Most recent alerts
psql -U user -d db -c "
SELECT id, rule_id, severity, status, created_at 
FROM alert_logs 
ORDER BY created_at DESC LIMIT 10;"

# Alert statistics
psql -U user -d db -c "
SELECT severity, COUNT(*) as count 
FROM alert_logs 
GROUP BY severity;"

# Alerts by rule
psql -U user -d db -c "
SELECT r.name, COUNT(l.id) as alert_count 
FROM alert_rules r 
LEFT JOIN alert_logs l ON r.id = l.rule_id 
GROUP BY r.id, r.name;"
```

---

## Phase 11: Performance & Load Tests 📈

### Test 11.1: Create Multiple Rules

```bash
# Create 10 different alert rules
for i in {1..10}; do
  curl -X POST "http://localhost:8000/api/alerts/rules" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"Alert Rule $i\",
      \"alert_type\": \"price_threshold\",
      \"symbol\": \"BTC\",
      \"threshold_value\": $((50000 + i*1000)),
      \"operator\": \"greater_than\",
      \"enabled\": true,
      \"severity\": \"warning\",
      \"notification_channels\": [\"email\"],
      \"email_recipients\": [\"test@gmail.com\"],
      \"cooldown_minutes\": 30,
      \"max_alerts_per_day\": 10
    }"
done
```

**Expected:**
- ✅ 10 rules created successfully
- ✅ Each has unique ID
- ✅ All visible in `GET /api/alerts/rules`

---

### Test 11.2: High Volume Alert Triggering

```bash
# Insert 50 price points
for i in {1..50}; do
  psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('BTC', $((50000 + RANDOM % 5000)), 'test', NOW());"
done

# Run check
curl -X POST "http://localhost:8000/api/alerts/check"

# Monitor response time and alert creation count
```

**Expected:**
- ✅ Completes in < 5 seconds
- ✅ Multiple alerts created
- ✅ All logged properly

---

### Test 11.3: List Rules with Many Records

```bash
# Get all rules
curl -X GET "http://localhost:8000/api/alerts/rules?limit=100" \
  -H "Content-Type: application/json" \
  -w "\nResponse Time: %{time_total}s\n"

# Get logs with filtering
curl -X GET "http://localhost:8000/api/alerts/logs?limit=100&severity=critical" \
  -w "\nResponse Time: %{time_total}s\n"
```

**Expected:**
- ✅ Response time < 1 second
- ✅ All records retrieved correctly
- ✅ Filtering works properly

---

## Phase 12: Integration Tests 🔗

### Test 12.1: Full Workflow Test

**Complete test from rule creation to notification:**

```bash
# Step 1: Create alert rule
RULE_ID=$(curl -s -X POST "http://localhost:8000/api/alerts/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Integration Test Alert",
    "alert_type": "price_threshold",
    "symbol": "TEST",
    "threshold_value": 100,
    "operator": "greater_than",
    "enabled": true,
    "severity": "critical",
    "notification_channels": ["email"],
    "email_recipients": ["test@gmail.com"],
    "cooldown_minutes": 30,
    "max_alerts_per_day": 10
  }' | grep -o '"id":[0-9]*' | grep -o '[0-9]*')

echo "Created rule: $RULE_ID"

# Step 2: Insert trigger data
psql -U user -d db -c "INSERT INTO price_history (symbol, price, source, created_at) VALUES ('TEST', 150, 'integration_test', NOW());"

# Step 3: Check alerts
curl -X POST "http://localhost:8000/api/alerts/check"

# Step 4: Verify alert was created
curl -X GET "http://localhost:8000/api/alerts/logs?rule_id=$RULE_ID"

# Step 5: Acknowledge alert
ALERT_ID=$(psql -U user -d db -t -c "SELECT id FROM alert_logs WHERE rule_id = $RULE_ID LIMIT 1;")
curl -X POST "http://localhost:8000/api/alerts/logs/$ALERT_ID/acknowledge"

# Step 6: Verify acknowledgment
curl -X GET "http://localhost:8000/api/alerts/logs/$ALERT_ID"

echo "✅ Integration test completed successfully!"
```

---

### Test 12.2: Multiple Concurrent Requests

```bash
# Simulate concurrent API calls
for i in {1..5}; do
  (
    curl -X GET "http://localhost:8000/api/alerts/dashboard" &
    curl -X GET "http://localhost:8000/api/alerts/rules" &
    curl -X GET "http://localhost:8000/api/alerts/logs" &
    curl -X GET "http://localhost:8000/api/alerts/stats" &
  )
done

wait
echo "✅ All concurrent requests completed!"
```

**Expected:**
- ✅ All requests return 200 OK
- ✅ No database lock errors
- ✅ Response times reasonable

---

## Testing Checklist ✅

- [ ] Phase 1: Pre-testing setup complete
  - [ ] Requirements installed
  - [ ] Environment configured
  - [ ] Database tables created
- [ ] Phase 2: Backend startup successful
  - [ ] Server starts without errors
  - [ ] API accessible
  - [ ] Endpoints visible in Swagger
- [ ] Phase 3: Database operations working
  - [ ] Dashboard endpoint responds
  - [ ] Can create rules
  - [ ] Can list rules
  - [ ] Can get single rule
- [ ] Phase 4: Alerts triggering properly
  - [ ] Price data insertable
  - [ ] Manual check endpoint works
  - [ ] Alerts created in database
  - [ ] History logged correctly
- [ ] Phase 5: All alert types tested
  - [ ] Price threshold alerts
  - [ ] Volatility alerts
  - [ ] Data missing alerts
  - [ ] System health alerts
- [ ] Phase 6: Notifications working
  - [ ] Email notifications received
  - [ ] Slack notifications posted
  - [ ] Multi-channel works
- [ ] Phase 7: API operations complete
  - [ ] Update rule works
  - [ ] Enable/disable works
  - [ ] Acknowledge works
  - [ ] Delete works
- [ ] Phase 8: Scheduler & cooldown
  - [ ] Automatic checking works
  - [ ] Cooldown enforced
  - [ ] Daily limits enforced
- [ ] Phase 9: Error handling solid
  - [ ] Invalid configs rejected
  - [ ] Missing fields caught
  - [ ] 404s for non-existent
  - [ ] Database failures handled
- [ ] Phase 10: Database verified
  - [ ] All tables exist
  - [ ] Structure correct
  - [ ] Indexes present
  - [ ] Data integrity sound
- [ ] Phase 11: Performance acceptable
  - [ ] Bulk operations fast
  - [ ] Queries optimized
  - [ ] No timeouts
- [ ] Phase 12: Integration smooth
  - [ ] Full workflow succeeds
  - [ ] Concurrent requests OK
  - [ ] No data corruption

---

## Troubleshooting Guide 🔧

### Issue: Backend won't start

**Error:** `ModuleNotFoundError: No module named 'psutil'`
```bash
pip install psutil==5.9.6
```

**Error:** `psycopg2.OperationalError: could not translate host name`
```bash
# Check PostgreSQL is running and .env has correct credentials
psql -U user -d database -c "SELECT 1;"
```

---

### Issue: Alerts not triggering

**Check 1: Rule enabled?**
```bash
psql -U user -d db -c "SELECT id, name, enabled FROM alert_rules;"
# enabled should be true
```

**Check 2: Price data in database?**
```bash
psql -U user -d db -c "SELECT * FROM price_history ORDER BY created_at DESC LIMIT 5;"
# Should have recent entries
```

**Check 3: Condition logic**
```bash
# For price_threshold: current_price > threshold?
# For volatility: % change > threshold over time window?
# For data_missing: last_data > missing_minutes?
# For system_health: resource_usage > threshold?
```

---

### Issue: Emails not sending

**Check 1: SMTP configured?**
```bash
# Verify .env
grep SMTP .env
```

**Check 2: Credentials correct?**
- For Gmail: Must use app-specific password (not regular password)
- For other providers: Verify SMTP_SERVER and SMTP_PORT

**Check 3: Notification queue**
```bash
psql -U user -d db -c "SELECT * FROM notification_queue WHERE channel = 'email' ORDER BY created_at DESC LIMIT 5;"
# Check status column and error_message
```

---

### Issue: High response times

**Check 1: Query performance**
```bash
psql -U user -d db -c "
EXPLAIN ANALYZE
SELECT * FROM alert_logs 
WHERE created_at > NOW() - INTERVAL '1 day'
ORDER BY created_at DESC LIMIT 100;"
```

**Check 2: Database indexes**
```bash
psql -U user -d db -c "\di alert_*"
# Should see indexes on frequently queried columns
```

**Check 3: Connection pool**
```bash
# Check in backend logs for pool exhaustion warnings
```

---

## Summary

**Total Tests:** 40+ test scenarios across 12 phases

**Coverage:**
- ✅ Backend startup & API accessibility
- ✅ Database operations & integrity
- ✅ All 4 alert types
- ✅ Email & Slack notifications
- ✅ API CRUD operations
- ✅ Scheduler & cooldown logic
- ✅ Error handling & validation
- ✅ Performance & load
- ✅ Integration workflows
- ✅ Edge cases

**Recommended Order:**
1. Start with Phase 1-2 (setup & startup)
2. Run Phase 3-4 (database & basic alerts)
3. Test Phase 5 (all alert types)
4. Configure Phase 6 (notifications)
5. Verify Phase 7-8 (API & scheduler)
6. Then Phase 9-12 (advanced testing)

**Estimated Time:** 2-3 hours for complete testing

---

**Happy Testing! 🎉**
