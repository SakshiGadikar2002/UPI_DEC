# Alert System Documentation

## Overview

The Alert System provides comprehensive monitoring and alerting capabilities for your ETL platform. It supports:

- **Price Threshold Alerts**: Alert when cryptocurrency prices cross specific thresholds
- **Volatility Alerts**: Alert when price changes exceed a percentage in a time window
- **Data Missing Alerts**: Alert when API data fails or stops being received
- **System Health Alerts**: Monitor database, disk space, memory, and CPU usage
- **Multiple Notification Channels**: Email and Slack notifications
- **Alert History and Tracking**: Full audit trail of all alerts
- **Configurable Rules**: User-defined alert rules with cooldown periods

## Architecture

```
[Data Collection] → [Alert Checker] → [Condition Evaluator] 
                                    ↓
                          [Alert Manager]
                                    ↓
                     [Notification Service]
                      ├─ Email Notifier
                      ├─ Slack Notifier
                      └─ Retry Queue
                                    ↓
                          [Alert Log/History]
```

## Database Schema

### Tables

#### `alert_rules`
Stores alert rule definitions with conditions and notification settings.

```sql
- id: Serial Primary Key
- name: Rule name (unique)
- alert_type: Type of alert (price_threshold, volatility, data_missing, system_health)
- enabled: Boolean flag to enable/disable rule
- description: Rule description
- symbol: Cryptocurrency symbol for price alerts
- price_threshold: Threshold price value
- price_comparison: Comparison operator (greater, less, equal)
- volatility_percentage: Percentage change threshold
- volatility_duration_minutes: Time window for volatility
- data_missing_minutes: Minutes before data is considered missing
- api_endpoint: API endpoint to monitor
- health_check_type: Type of health check (db_connection, disk_space, memory, cpu)
- threshold_value: Threshold for health checks
- notification_channels: Where to send alerts (email, slack, both)
- email_recipients: Comma-separated email list
- slack_webhook_url: Slack webhook URL
- severity: Alert severity (info, warning, critical)
- cooldown_minutes: Minutes between repeated alerts
- max_alerts_per_day: Maximum alerts per day (null = unlimited)
- created_at, updated_at: Timestamps
```

#### `alert_logs`
Stores triggered alerts with status tracking.

```sql
- id: Serial Primary Key
- rule_id: Foreign key to alert_rules
- alert_type: Type of alert triggered
- title: Alert title
- message: Alert message
- severity: Alert severity
- status: Current status (pending, sent, failed, acknowledged)
- metadata: JSON object with additional data
- created_at: When alert was triggered
- sent_at: When alert was sent
- acknowledged_at: When alert was acknowledged
```

#### `alert_tracking`
Tracks cooldown and daily alert counts for deduplication.

```sql
- id: Serial Primary Key
- rule_id: Foreign key to alert_rules (unique)
- last_alert_time: Timestamp of last triggered alert
- alert_count_today: Number of alerts today
- last_alert_date: Date of last alert
```

#### `notification_queue`
Queue for notifications with retry mechanism.

```sql
- id: Serial Primary Key
- alert_id: Foreign key to alert_logs
- channel: Notification channel (email, slack)
- recipient: Email or recipient identifier
- status: Status (pending, sent, failed)
- retry_count: Number of retries attempted
- max_retries: Maximum retries allowed
- error_message: Error message if failed
- created_at: When queued
- last_retry_at: Last retry timestamp
- sent_at: When successfully sent
```

#### `price_history`
Stores price data for volatility calculations.

```sql
- id: Serial Primary Key
- symbol: Cryptocurrency symbol
- price: Price value
- source: Data source
- timestamp: When price was recorded
```

## Configuration

### Environment Variables

Create a `.env` file in the backend directory with these settings:

```bash
# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=True
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password  # Use app-specific password for Gmail

# Slack Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Alert Settings
ALERT_CHECK_INTERVAL=1  # Minutes between checks
DEFAULT_ALERT_CHANNEL=email  # or slack, both
ALERT_RETENTION_DAYS=90

# System Monitoring
MONITOR_DB_HEALTH=True
MONITOR_DISK_SPACE=True
DISK_SPACE_THRESHOLD_GB=5
MONITOR_MEMORY=True
MEMORY_THRESHOLD_PERCENT=85
MONITOR_CPU=True
CPU_THRESHOLD_PERCENT=90
```

## API Endpoints

### Alert Rules Management

#### Create Alert Rule
```
POST /api/alerts/rules

Request Body:
{
  "name": "BTC Price Alert",
  "alert_type": "price_threshold",
  "enabled": true,
  "symbol": "BTC",
  "price_threshold": 50000,
  "price_comparison": "greater",
  "notification_channels": "email",
  "email_recipients": ["admin@example.com"],
  "severity": "warning",
  "cooldown_minutes": 5
}

Response:
{
  "id": 1,
  "name": "BTC Price Alert",
  "alert_type": "price_threshold",
  "message": "Alert rule created successfully"
}
```

#### List Alert Rules
```
GET /api/alerts/rules?enabled_only=false

Response:
[
  {
    "rule_id": 1,
    "name": "BTC Price Alert",
    "alert_type": "price_threshold",
    "enabled": true,
    "symbol": "BTC",
    "price_threshold": 50000,
    ...
  }
]
```

#### Get Alert Rule
```
GET /api/alerts/rules/{rule_id}

Response:
{
  "rule_id": 1,
  "name": "BTC Price Alert",
  ...
}
```

#### Update Alert Rule
```
PUT /api/alerts/rules/{rule_id}

Request Body:
{
  "price_threshold": 55000,
  "enabled": false
}

Response:
{
  "id": 1,
  "message": "Alert rule updated successfully"
}
```

#### Delete Alert Rule
```
DELETE /api/alerts/rules/{rule_id}

Response:
{
  "id": 1,
  "message": "Alert rule deleted successfully"
}
```

### Alert History & Monitoring

#### Get Alert Dashboard
```
GET /api/alerts/dashboard

Response:
{
  "total_rules": 5,
  "active_rules": 4,
  "inactive_rules": 1,
  "total_alerts_today": 12,
  "critical_alerts": 2,
  "warning_alerts": 10,
  "recent_alerts": [
    {
      "alert_id": 1,
      "rule_id": 1,
      "alert_type": "price_threshold",
      "title": "BTC Price Alert",
      "message": "BTC price $51,234 crossed threshold $50,000",
      "severity": "warning",
      "status": "sent",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "triggered_rules": [...]
}
```

#### Get Alert Logs
```
GET /api/alerts/logs?limit=100&rule_id=1&severity=warning

Response:
[
  {
    "alert_id": 1,
    "rule_id": 1,
    "alert_type": "price_threshold",
    "title": "BTC Price Alert",
    "message": "BTC price $51,234 crossed threshold $50,000",
    "severity": "warning",
    "status": "sent",
    "metadata": {"current_price": 51234, "threshold": 50000},
    "created_at": "2024-01-15T10:30:00Z",
    "sent_at": "2024-01-15T10:30:05Z",
    "acknowledged_at": null
  }
]
```

#### Acknowledge Alert
```
POST /api/alerts/logs/{alert_id}/acknowledge

Response:
{
  "id": 1,
  "message": "Alert acknowledged successfully"
}
```

#### Get Alert Statistics
```
GET /api/alerts/stats?hours=24

Response:
{
  "period_hours": 24,
  "total_alerts": 45,
  "by_severity": {
    "info": 10,
    "warning": 30,
    "critical": 5
  },
  "by_type": {
    "price_threshold": 20,
    "volatility": 15,
    "data_missing": 5,
    "system_health": 5
  },
  "hourly_distribution": {
    "2024-01-15 10:00": 3,
    "2024-01-15 11:00": 5,
    ...
  }
}
```

#### Manually Check Alerts
```
POST /api/alerts/check

Response:
{
  "checked": 5,
  "triggered": 2,
  "errors": 0,
  "alerts": [
    {
      "alert_id": 1,
      "rule_id": 1,
      "message": "BTC price crossed threshold"
    }
  ]
}
```

## Alert Types

### 1. Price Threshold Alerts

Triggers when a cryptocurrency price crosses a specified threshold.

**Required Parameters:**
- `symbol`: Cryptocurrency symbol (e.g., "BTC", "ETH")
- `price_threshold`: Price value to monitor
- `price_comparison`: "greater", "less", or "equal"

**Example:**
```json
{
  "name": "BTC Above 50k Alert",
  "alert_type": "price_threshold",
  "symbol": "BTC",
  "price_threshold": 50000,
  "price_comparison": "greater",
  "severity": "critical"
}
```

### 2. Volatility Alerts

Triggers when price changes exceed a percentage within a time window.

**Required Parameters:**
- `symbol`: Cryptocurrency symbol
- `volatility_percentage`: Percentage change threshold (e.g., 5 for 5%)
- `volatility_duration_minutes`: Time window in minutes

**Example:**
```json
{
  "name": "ETH High Volatility Alert",
  "alert_type": "volatility",
  "symbol": "ETH",
  "volatility_percentage": 5,
  "volatility_duration_minutes": 10,
  "severity": "warning"
}
```

### 3. Data Missing Alerts

Triggers when API fails to send data for a specified duration.

**Required Parameters:**
- `api_endpoint`: API endpoint/connector to monitor
- `data_missing_minutes`: Minutes of no data before alerting

**Example:**
```json
{
  "name": "Binance API Down Alert",
  "alert_type": "data_missing",
  "api_endpoint": "binance_prices",
  "data_missing_minutes": 5,
  "severity": "critical"
}
```

### 4. System Health Alerts

Monitors system resources and database health.

**Required Parameters:**
- `health_check_type`: "db_connection", "disk_space", "memory", or "cpu"
- `threshold_value`: Threshold for the check

**Example - Low Disk Space:**
```json
{
  "name": "Low Disk Space Alert",
  "alert_type": "system_health",
  "health_check_type": "disk_space",
  "threshold_value": 5,  # Alert if < 5 GB available
  "severity": "critical"
}
```

**Example - High Memory Usage:**
```json
{
  "name": "High Memory Alert",
  "alert_type": "system_health",
  "health_check_type": "memory",
  "threshold_value": 85,  # Alert if > 85% used
  "severity": "warning"
}
```

## Notification Configuration

### Email Notifications

1. **Gmail Setup:**
   - Enable 2-Factor Authentication
   - Generate App Password: https://myaccount.google.com/apppasswords
   - Use app password in `SENDER_PASSWORD`

2. **Other Email Providers:**
   - Update `SMTP_SERVER` and `SMTP_PORT`
   - Example for Outlook: smtp-mail.outlook.com:587

### Slack Notifications

1. **Create Incoming Webhook:**
   - Go to your Slack workspace
   - Create new app at https://api.slack.com/apps
   - Enable "Incoming Webhooks"
   - Create new webhook for a channel
   - Copy webhook URL to `SLACK_WEBHOOK_URL`

2. **Test Webhook:**
   Use curl to test:
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test message"}' \
     YOUR_WEBHOOK_URL
   ```

## Cooldown and Rate Limiting

### Cooldown Period
Once an alert is triggered, the same rule won't trigger again for `cooldown_minutes` to avoid alert fatigue.

### Max Alerts Per Day
Optionally limit alerts to a maximum number per day. When limit is reached, no more alerts are sent until the next day.

**Example with Cooldown:**
```json
{
  "name": "Price Alert",
  "alert_type": "price_threshold",
  "symbol": "BTC",
  "price_threshold": 50000,
  "severity": "warning",
  "cooldown_minutes": 30,      # Wait 30 min before next alert
  "max_alerts_per_day": 5       # Max 5 alerts per day
}
```

## Alert Metadata

Alerts can include metadata for context:

```json
{
  "current_price": 51234.50,
  "threshold": 50000,
  "change_percent": 2.47,
  "last_data_received": "2024-01-15T10:29:30Z",
  "available_disk_gb": 2.5,
  "cpu_percent": 92.5
}
```

## Scheduler

The alert system runs on APScheduler with the following jobs:

1. **Alert Check Job** (Every 1 minute)
   - Evaluates all enabled alert rules
   - Triggers alerts when conditions are met
   - Sends notifications

2. **Alert Cleanup Job** (Daily)
   - Removes alerts older than 90 days
   - Configured in `.env`: `ALERT_RETENTION_DAYS`

## Error Handling & Retries

### Notification Retry Mechanism
Failed notifications are queued for retry:
- Max retries per notification: 3
- Notifications are cleaned up after successful send
- Failed notifications are logged for manual review

### Database Connection
- Uses connection pool for reliability
- Automatic reconnection on failure
- Health checks prevent stale connections

## Best Practices

1. **Avoid Alert Fatigue**
   - Set appropriate cooldown periods
   - Use reasonable thresholds
   - Limit max alerts per day if needed

2. **Name Rules Clearly**
   - Use descriptive names: "BTC Price > $50k"
   - Include thresholds in name where applicable

3. **Test Notifications**
   - Create test rule to verify Email/Slack setup
   - Check notification recipient addresses
   - Verify webhook URLs before deploying

4. **Monitor Alert History**
   - Regularly review triggered alerts
   - Adjust thresholds based on false positives
   - Archive old alerts for compliance

5. **Severity Levels**
   - INFO: Informational alerts
   - WARNING: Requires attention
   - CRITICAL: Immediate action needed

6. **Cooldown Strategy**
   - Short (5 min): High-frequency monitoring
   - Medium (30 min): Standard alerts
   - Long (1-2 hours): Stable trend alerts

## Troubleshooting

### Email Not Sending
- Check SMTP credentials in `.env`
- Verify email account allows app passwords
- Check logs for SMTP errors
- Test with manual check: `POST /api/alerts/check`

### Slack Not Receiving
- Verify webhook URL is correct
- Check Slack workspace permissions
- Test webhook with curl
- Ensure channel hasn't been deleted

### Alerts Not Triggering
- Verify rule is enabled
- Check alert conditions are met
- Review alert logs for errors
- Manually check with: `POST /api/alerts/check`

### High Memory Usage
- Reduce `ALERT_CHECK_INTERVAL`
- Clean up old alerts (increase `ALERT_RETENTION_DAYS`)
- Reduce price history retention

## Examples

### Example 1: Create Price Alert
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
    "email_recipients": ["admin@example.com"],
    "severity": "critical",
    "cooldown_minutes": 60,
    "enabled": true
  }'
```

### Example 2: Create Volatility Alert
```bash
curl -X POST http://localhost:8000/api/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ETH 5% in 10min",
    "alert_type": "volatility",
    "symbol": "ETH",
    "volatility_percentage": 5,
    "volatility_duration_minutes": 10,
    "notification_channels": "both",
    "email_recipients": ["admin@example.com"],
    "slack_webhook_url": "https://hooks.slack.com/services/...",
    "severity": "warning",
    "enabled": true
  }'
```

### Example 3: Create System Health Alert
```bash
curl -X POST http://localhost:8000/api/alerts/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Low Disk Space",
    "alert_type": "system_health",
    "health_check_type": "disk_space",
    "threshold_value": 5,
    "notification_channels": "email",
    "email_recipients": ["admin@example.com"],
    "severity": "critical",
    "enabled": true
  }'
```

## API Response Codes

- `200 OK`: Request successful
- `201 Created`: Resource created
- `204 No Content`: Successful deletion
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Performance Considerations

- Alert checks run every minute (configurable)
- Price history stored for volatility calculations
- Old alerts auto-cleanup daily
- Notification queue handles retries asynchronously
- Alert tracking prevents duplicate notifications

## Future Enhancements

- [ ] Custom alert conditions/expressions
- [ ] Webhook notifications
- [ ] SMS notifications
- [ ] Alert escalation policies
- [ ] Alert grouping/correlation
- [ ] Machine learning-based threshold suggestions
- [ ] WebSocket real-time alert updates
- [ ] Alert templates for common scenarios
- [ ] PagerDuty/OpsGenie integration
- [ ] Alert analytics and dashboards
