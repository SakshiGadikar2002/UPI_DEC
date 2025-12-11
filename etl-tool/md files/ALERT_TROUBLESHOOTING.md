# Alert System Troubleshooting Guide

## Common Issues and Solutions

### Issue 1: No Data in Database Tables

#### Problem: `alert_rules`, `alert_tracking`, `price_history`, `notification_queue` are empty

**Solution:**
1. **Create Alert Rules First:**
   ```bash
   # Use the API to create an alert rule
   POST http://localhost:8000/api/alerts/rules
   {
     "name": "BTC Price Alert",
     "alert_type": "price_threshold",
     "symbol": "BTC",
     "price_threshold": 50000,
     "price_comparison": "greater",
     "email_recipients": ["your-email@example.com"],
     "enabled": true
   }
   ```

2. **Verify Tables Are Created:**
   ```sql
   -- Check if tables exist
   SELECT table_name FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name IN ('alert_rules', 'alert_tracking', 'price_history', 'notification_queue');
   ```

3. **Initialize Missing Tracking Entries:**
   ```sql
   -- This is done automatically on startup, but you can run manually:
   INSERT INTO alert_tracking (rule_id, last_alert_time, alert_count_today)
   SELECT id, NULL, 0
   FROM alert_rules
   WHERE id NOT IN (SELECT rule_id FROM alert_tracking)
   ON CONFLICT (rule_id) DO NOTHING;
   ```

### Issue 2: Not Receiving Emails

#### Problem: Alerts are triggered but no emails are sent

**Checklist:**
1. **Verify Email Configuration:**
   ```bash
   # Check .env file has:
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_FROM_EMAIL=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SMTP_USE_TLS=true
   SMTP_REQUIRE_AUTH=true
   ```

2. **Check Alert Rule Has Email Recipients:**
   ```sql
   SELECT id, name, email_recipients, enabled 
   FROM alert_rules 
   WHERE enabled = TRUE;
   ```

3. **Check Notification Queue:**
   ```sql
   SELECT id, alert_id, channel, recipient, status, error_message, created_at
   FROM notification_queue
   ORDER BY created_at DESC
   LIMIT 10;
   ```

4. **Check Alert Logs Status:**
   ```sql
   SELECT id, rule_id, title, message, severity, status, sent_at
   FROM alert_logs
   ORDER BY created_at DESC
   LIMIT 10;
   ```

5. **Verify Email Service is Working:**
   ```python
   # Test email directly
   from services.notification_service import EmailNotifier
   notifier = EmailNotifier()
   success, error = notifier.send_email(
       recipients=["your-email@example.com"],
       subject="Test Alert",
       body="This is a test email"
   )
   print(f"Success: {success}, Error: {error}")
   ```

### Issue 3: No Data in `price_history`

#### Problem: `price_history` table is empty

**Solution:**
1. **Prices are automatically recorded when:**
   - Alert rules are checked (price_threshold or volatility alerts)
   - Market data is processed through `check_crypto_alerts_and_email`

2. **Manually Record Price (for testing):**
   ```python
   from services.alert_checker import AlertChecker
   from database import get_pool
   
   pool = get_pool()
   checker = AlertChecker(pool)
   await checker.record_price("BTC", 50000.0, "manual_test")
   ```

3. **Check if prices are being fetched:**
   ```sql
   -- Check if there's price data in api_connector_items
   SELECT coin_symbol, price, timestamp
   FROM api_connector_items
   WHERE coin_symbol = 'BTC'
   ORDER BY timestamp DESC
   LIMIT 5;
   ```

### Issue 4: No Data in `alert_tracking`

#### Problem: `alert_tracking` table is empty

**Solution:**
1. **Tracking is automatically created when:**
   - A new alert rule is created
   - Database is initialized (for existing rules)

2. **Manually Initialize Tracking:**
   ```sql
   INSERT INTO alert_tracking (rule_id, last_alert_time, alert_count_today)
   SELECT id, NULL, 0
   FROM alert_rules
   WHERE id NOT IN (SELECT rule_id FROM alert_tracking)
   ON CONFLICT (rule_id) DO NOTHING;
   ```

3. **Verify Tracking After Alert:**
   ```sql
   SELECT rule_id, last_alert_time, alert_count_today, last_alert_date
   FROM alert_tracking
   WHERE rule_id IN (SELECT id FROM alert_rules);
   ```

### Issue 5: No Data in `notification_queue`

#### Problem: `notification_queue` table is empty

**Solution:**
1. **Queue is populated when:**
   - `notification_service.send_alert()` is called
   - This happens automatically when alerts are triggered

2. **Check if notifications are being sent:**
   ```sql
   SELECT id, alert_id, channel, recipient, status, error_message, retry_count
   FROM notification_queue
   ORDER BY created_at DESC;
   ```

3. **Verify Alert Logs Have Corresponding Notifications:**
   ```sql
   SELECT 
     al.id as alert_id,
     al.title,
     nq.id as notification_id,
     nq.status,
     nq.error_message
   FROM alert_logs al
   LEFT JOIN notification_queue nq ON al.id = nq.alert_id
   ORDER BY al.created_at DESC
   LIMIT 10;
   ```

## Database Table Status Queries

### Check All Alert Tables Status:
```sql
-- Count records in each table
SELECT 
  'alert_rules' as table_name, COUNT(*) as count FROM alert_rules
UNION ALL
SELECT 'alert_tracking', COUNT(*) FROM alert_tracking
UNION ALL
SELECT 'alert_logs', COUNT(*) FROM alert_logs
UNION ALL
SELECT 'price_history', COUNT(*) FROM price_history
UNION ALL
SELECT 'notification_queue', COUNT(*) FROM notification_queue;
```

### Check Recent Activity:
```sql
-- Recent alert logs
SELECT id, rule_id, title, severity, status, created_at, sent_at
FROM alert_logs
ORDER BY created_at DESC
LIMIT 10;

-- Recent price history
SELECT symbol, price, source, timestamp
FROM price_history
ORDER BY timestamp DESC
LIMIT 10;

-- Recent notifications
SELECT id, alert_id, channel, status, error_message, created_at
FROM notification_queue
ORDER BY created_at DESC
LIMIT 10;
```

## Testing the Alert System

### Step 1: Create an Alert Rule
```bash
curl -X POST http://localhost:8000/api/alerts/rules \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "BTC Price Test",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "price_threshold": 10000,
    "price_comparison": "greater",
    "email_recipients": ["your-email@example.com"],
    "enabled": true,
    "severity": "warning"
  }'
```

### Step 2: Verify Rule Was Created
```sql
SELECT * FROM alert_rules WHERE name = 'BTC Price Test';
SELECT * FROM alert_tracking WHERE rule_id = (SELECT id FROM alert_rules WHERE name = 'BTC Price Test');
```

### Step 3: Manually Trigger Alert Check
```bash
curl -X POST http://localhost:8000/api/alerts/check \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Step 4: Check Results
```sql
-- Check if alert was logged
SELECT * FROM alert_logs ORDER BY created_at DESC LIMIT 1;

-- Check if notification was queued
SELECT * FROM notification_queue ORDER BY created_at DESC LIMIT 1;

-- Check if price was recorded
SELECT * FROM price_history WHERE symbol = 'BTC' ORDER BY timestamp DESC LIMIT 1;
```

## Email Configuration Checklist

1. **Gmail Setup:**
   - Enable 2-factor authentication
   - Generate App Password (not regular password)
   - Use App Password in `SMTP_PASSWORD`

2. **Environment Variables:**
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_FROM_EMAIL=your-email@gmail.com
   SMTP_PASSWORD=your-16-char-app-password
   SMTP_USE_TLS=true
   SMTP_REQUIRE_AUTH=true
   ALERT_EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
   ```

3. **Test Email Configuration:**
   ```python
   python backend/check_email_config.py
   ```

## Alert Scheduler Status

### Check if Alert Scheduler is Running:
```python
# Look for these logs on startup:
# [STARTUP] Alert scheduler initialized and running
# Alert scheduler started with jobs
```

### Check Scheduler Jobs:
```python
# The scheduler runs every 5 minutes
# Check logs for:
# "Alert check: X checked, Y triggered, Z emails sent"
```

## Common Error Messages and Fixes

### "No market data available for alert checking"
- **Cause:** No recent data in `websocket_messages` or `api_connector_data`
- **Fix:** Ensure job scheduler is running and collecting data

### "Failed to create alert log"
- **Cause:** Foreign key constraint (rule_id doesn't exist)
- **Fix:** Ensure alert rule exists before checking

### "Email sender address not configured"
- **Cause:** `SMTP_FROM_EMAIL` not set
- **Fix:** Set `SMTP_FROM_EMAIL` in `.env` file

### "Email credentials not configured"
- **Cause:** `SMTP_PASSWORD` not set
- **Fix:** Set `SMTP_PASSWORD` in `.env` file

### "Rule X not found for alert"
- **Cause:** Alert was created but rule was deleted
- **Fix:** Recreate the alert rule

## Database Maintenance

### Clean Up Old Data:
```sql
-- Delete old price history (older than 90 days)
DELETE FROM price_history 
WHERE timestamp < NOW() - INTERVAL '90 days';

-- Delete old alert logs (older than 90 days)
DELETE FROM alert_logs 
WHERE created_at < NOW() - INTERVAL '90 days';

-- Delete old notifications (older than 30 days)
DELETE FROM notification_queue 
WHERE created_at < NOW() - INTERVAL '30 days';
```

### Reset Alert Tracking:
```python
# Run reset script
python backend/reset_alert_limits.py
```

## Verification Steps

1. ✅ Alert rules exist in `alert_rules` table
2. ✅ Alert tracking exists for all rules in `alert_tracking` table
3. ✅ Prices are being recorded in `price_history` table
4. ✅ Alert logs are created in `alert_logs` table
5. ✅ Notifications are queued in `notification_queue` table
6. ✅ Emails are being sent (check `notification_queue.status = 'sent'`)
7. ✅ Email configuration is correct (test with `check_email_config.py`)

