# Backend, Frontend, and Database Overview

## Backend
- FastAPI app, job scheduler, connectors, ETL helpers, alerting, and database access.
- Main files: `main.py`, `database.py`, `requirements.txt`.
- Modules: connectors, etl, job_scheduler, models, services, routes.

## Frontend
- React + Vite UI, real-time streaming charts, ETL pipeline viewer.
- Main files: `index.html`, `src/main.jsx`, `src/App.jsx`, `src/components/`, `package.json`, `vite.config.js`.

## Database
- PostgreSQL 13+, schema bootstrapped by backend.
- Main tables: `api_connector_data`, `api_connector_items`, `pipeline_runs`, `pipeline_steps`, `alert_rules`, `alert_logs`.
# Alert System - Quick Start Guide

## 1. Installation

The alert system dependencies are already included in `requirements.txt`. Install them:

```bash
pip install -r requirements.txt
```

Key new packages:
- `psutil==5.9.6` - System monitoring (disk, memory, CPU)

## 2. Configuration

### Step 1: Create `.env` file

Copy the example configuration and update with your settings:

```bash
cp backend/.env.example backend/.env
```

### Step 2: Configure Email (for email alerts)

**Using Gmail:**
1. Enable 2-Factor Authentication on your Gmail account
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Update `.env`:
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USE_TLS=True
   SENDER_EMAIL=your-email@gmail.com
   SENDER_PASSWORD=your-app-password
   ```

**Using other email providers:**
- Outlook: smtp-mail.outlook.com:587
- SendGrid: smtp.sendgrid.net:587
- AWS SES: email-smtp.{region}.amazonaws.com:587

### Step 3: Configure Slack (for Slack alerts)

1. Go to https://api.slack.com/apps
2. Create a new app or select existing workspace
3. Enable "Incoming Webhooks"
4. Create new webhook for desired channel
5. Copy webhook URL to `.env`:
   ```
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```

## 3. Database Setup

When you start the backend, alert tables will be automatically created:

```bash
cd backend
python -m uvicorn main:app --reload
```

Check logs for:
```
[OK] Initialized PostgreSQL tables with indexes
[STARTUP] Alert scheduler initialized and running
```

## 4. Create Your First Alert

### Using cURL

**Price Threshold Alert:**
```bash
curl -X POST http://localhost:8000/api/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Above 50k",
    "alert_type": "price_threshold",
    "symbol": "BTC",
    "price_threshold": 50000,
    "price_comparison": "greater",
    "notification_channels": "email",
    "email_recipients": ["your-email@example.com"],
    "severity": "warning",
    "cooldown_minutes": 5,
    "enabled": true
  }'
```

**Volatility Alert:**
```bash
curl -X POST http://localhost:8000/api/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ETH High Volatility",
    "alert_type": "volatility",
    "symbol": "ETH",
    "volatility_percentage": 5,
    "volatility_duration_minutes": 10,
    "notification_channels": "slack",
    "slack_webhook_url": "your-webhook-url",
    "severity": "warning",
    "cooldown_minutes": 10,
    "enabled": true
  }'
```

**System Health Alert:**
```bash
curl -X POST http://localhost:8000/api/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Low Disk Space",
    "alert_type": "system_health",
    "health_check_type": "disk_space",
    "threshold_value": 5,
    "notification_channels": "email",
    "email_recipients": ["your-email@example.com"],
    "severity": "critical",
    "enabled": true
  }'
```

### Using Frontend (Coming Soon)

A dedicated Alert Management UI will be added to the frontend for easier rule management.

## 5. Test Your Setup

### Manual Alert Check
```bash
curl -X POST http://localhost:8000/api/alerts/check
```

Response:
```json
{
  "checked": 5,
  "triggered": 0,
  "errors": 0,
  "alerts": []
}
```

### View Dashboard
```bash
curl http://localhost:8000/api/alerts/dashboard
```

Response:
```json
{
  "total_rules": 1,
  "active_rules": 1,
  "inactive_rules": 0,
  "total_alerts_today": 0,
  "critical_alerts": 0,
  "warning_alerts": 0,
  "recent_alerts": [],
  "triggered_rules": []
}
```

### View All Rules
```bash
curl http://localhost:8000/api/alerts/rules
```

### View Alert History
```bash
curl http://localhost:8000/api/alerts/logs
```

## 6. How It Works

### Alert Checking Process

```
Every 1 minute:
├─ Load all enabled alert rules
├─ For each rule:
│  ├─ Check cooldown (avoid duplicate alerts)
│  ├─ Evaluate condition
│  │  ├─ Price threshold: Check current price vs threshold
│  │  ├─ Volatility: Calculate price change in time window
│  │  ├─ Data missing: Check last API data received
│  │  └─ System health: Check DB, disk, memory, CPU
│  └─ If triggered:
│     ├─ Create alert log entry
│     ├─ Send email notification
│     ├─ Send Slack notification
│     └─ Update tracking (cooldown, daily count)
```

### Alert Lifecycle

```
1. PENDING: Alert created, notification queued
   ↓
2. SENT: Notification delivered successfully
   ↓
3. ACKNOWLEDGED: User acknowledges the alert
```

If notification fails:
```
PENDING → (retry up to 3 times) → FAILED (if all retries fail)
```

## 7. Common Tasks

### Disable a Rule
```bash
curl -X PUT http://localhost:8000/api/alerts/rules/{rule_id} \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### Update Rule Threshold
```bash
curl -X PUT http://localhost:8000/api/alerts/rules/{rule_id} \
  -H "Content-Type: application/json" \
  -d '{"price_threshold": 55000}'
```

### Delete a Rule
```bash
curl -X DELETE http://localhost:8000/api/alerts/rules/{rule_id}
```

### Get Recent Alerts
```bash
curl "http://localhost:8000/api/alerts/logs?limit=20&severity=critical"
```

### Get Alert Statistics
```bash
curl "http://localhost:8000/api/alerts/stats?hours=24"
```

### Acknowledge an Alert
```bash
curl -X POST http://localhost:8000/api/alerts/logs/{alert_id}/acknowledge
```

## 8. Troubleshooting

### Alert Not Sending via Email

1. Check `.env` has correct SMTP settings
2. Verify email account allows app passwords
3. Check backend logs for errors:
   ```
   grep "Email send error" logs/backend.log
   ```
4. Test SMTP connection manually:
   ```python
   import smtplib
   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login('your-email@gmail.com', 'your-app-password')
   server.quit()
   ```

### Alert Not Triggering

1. Verify rule is enabled:
   ```bash
   curl http://localhost:8000/api/alerts/rules
   ```

2. Manually trigger check:
   ```bash
   curl -X POST http://localhost:8000/api/alerts/check
   ```

3. Check alert logs:
   ```bash
   curl http://localhost:8000/api/alerts/logs
   ```

4. Check database connection:
   ```bash
   curl http://localhost:8000/api/alerts/dashboard
   ```

### High Memory Usage

1. Reduce alert check frequency in scheduler (in `alert_scheduler.py`):
   ```python
   scheduler.add_job(..., 'interval', minutes=5)  # Check every 5 min instead of 1
   ```

2. Reduce price history retention (in `database.py`):
   ```python
   # Increase retention days
   DELETE FROM price_history WHERE timestamp < NOW() - INTERVAL '30 days'
   ```

## 9. Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| SMTP_SERVER | smtp.gmail.com | Email SMTP server |
| SMTP_PORT | 587 | Email SMTP port |
| SENDER_EMAIL | "" | Email account to send from |
| SENDER_PASSWORD | "" | Email account password |
| SLACK_WEBHOOK_URL | "" | Slack incoming webhook URL |
| ALERT_CHECK_INTERVAL | 1 | Minutes between alert checks |
| DEFAULT_ALERT_CHANNEL | email | Default notification channel |
| ALERT_RETENTION_DAYS | 90 | Days to keep old alerts |
| MONITOR_DB_HEALTH | True | Monitor database health |
| MONITOR_DISK_SPACE | True | Monitor disk space |
| DISK_SPACE_THRESHOLD_GB | 5 | Disk space alert threshold |
| MONITOR_MEMORY | True | Monitor memory usage |
| MEMORY_THRESHOLD_PERCENT | 85 | Memory usage alert threshold |
| MONITOR_CPU | True | Monitor CPU usage |
| CPU_THRESHOLD_PERCENT | 90 | CPU usage alert threshold |

## 10. Next Steps

1. **Create Core Alerts**: Set up price and volatility monitoring
2. **Configure Notifications**: Set up email and Slack
3. **Monitor Dashboard**: View alert activity
4. **Tune Thresholds**: Adjust based on false positives
5. **Set Cooldowns**: Prevent alert fatigue
6. **Review Logs**: Regularly check alert history
7. **Add System Monitoring**: Enable health checks
8. **Documentation**: Share alert rules with team

## 11. API Reference

Full API documentation available in `ALERT_SYSTEM.md`

### Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/alerts/dashboard` | GET | View alert dashboard |
| `/api/alerts/rules` | GET | List all rules |
| `/api/alerts/rules` | POST | Create new rule |
| `/api/alerts/rules/{id}` | GET | Get rule details |
| `/api/alerts/rules/{id}` | PUT | Update rule |
| `/api/alerts/rules/{id}` | DELETE | Delete rule |
| `/api/alerts/logs` | GET | Get alert history |
| `/api/alerts/logs/{id}/acknowledge` | POST | Acknowledge alert |
| `/api/alerts/check` | POST | Manually check alerts |
| `/api/alerts/stats` | GET | Get statistics |

## Support

For detailed documentation, see `ALERT_SYSTEM.md`

For issues or questions, check the logs:
```bash
# View backend logs
tail -f logs/backend.log

# Check database
psql etl_tool -c "SELECT * FROM alert_logs ORDER BY created_at DESC LIMIT 10;"
```
