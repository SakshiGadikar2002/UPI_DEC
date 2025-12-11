# Email Alert Setup - Fixed

## Problem Identified

You were getting alerts in the terminal but **no emails were being sent** because:

1. **No Alert Rules Exist**: The alert system requires alert rules in the database to send emails
2. **Test Script Doesn't Create Rules**: `test_crypto_alerts_realtime.py` only tests the alert engine, it doesn't create database rules
3. **Email Recipients Missing**: Even if rules existed, they need `email_recipients` configured

## Solution Applied

### 1. Updated Alert System Code
- Modified `alert_manager.py` to automatically fetch user emails from the `users` table if alert rules don't have `email_recipients`
- Modified `notification_service.py` to use active user emails as fallback
- Updated `check_and_trigger_alerts()` to ensure rules have email recipients before sending

### 2. Created Helper Scripts
- **`check_alert_email_setup.py`**: Check current setup (users, rules, SMTP config)
- **`update_alert_rules_with_user_emails.py`**: Update existing rules with user emails

## How to Fix Your Setup

### Step 1: Create Alert Rules via API

When you create alert rules through the API (while logged in), your email will automatically be added:

```bash
# Make sure you're logged in first
POST http://localhost:8000/api/alerts/rules
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "name": "BTC Price Alert",
  "alert_type": "price_threshold",
  "symbol": "BTC",
  "price_threshold": 50000,
  "price_comparison": "greater",
  "enabled": true,
  "severity": "warning"
}
```

**Note**: If you don't provide `email_recipients`, the system will automatically use your logged-in email (`sakshi.gadikar@arithwise.com`).

### Step 2: Verify Setup

Run the check script:
```bash
cd backend
python check_alert_email_setup.py
```

You should see:
- ✅ Your email in active users
- ✅ Alert rules with your email as recipient
- ✅ SMTP configuration correct

### Step 3: Test Email Sending

Once you have alert rules:
1. The alert scheduler runs every 5 minutes automatically
2. Or manually trigger: `POST /api/alerts/check`
3. Check `notification_queue` table to see if emails were sent

## Current Status

✅ **User Email**: `sakshi.gadikar@arithwise.com` is in database  
✅ **SMTP Config**: Configured correctly  
❌ **Alert Rules**: Need to be created  
❌ **Email Recipients**: Will be set automatically when rules are created via API  

## Why Test Script Doesn't Send Emails

The `test_crypto_alerts_realtime.py` script:
- Tests the crypto alert engine directly
- Doesn't create database alert rules
- Doesn't use the notification service
- Only shows alerts in terminal

**To actually send emails**, you need to:
1. Create alert rules via the API (while logged in)
2. Wait for alerts to trigger (or manually trigger with `/api/alerts/check`)
3. Emails will be sent to the email addresses in the alert rules

## Next Steps

1. **Create an alert rule** via the frontend or API
2. **Verify** it has your email: `python check_alert_email_setup.py`
3. **Trigger an alert** manually or wait for scheduler
4. **Check** `notification_queue` table for email status

## Database Tables Status

- ✅ `users`: Has your email
- ✅ `alert_logs`: Has alert history
- ❌ `alert_rules`: Empty (need to create)
- ❌ `notification_queue`: Empty (will populate when rules exist)
- ❌ `alert_tracking`: Empty (will populate when rules exist)
- ❌ `price_history`: Empty (will populate when price alerts trigger)

## Email Configuration

Your SMTP settings:
- Host: `smtp.office365.com`
- Port: `587`
- User: `ariths@arithwise.com`
- Password: ✅ Set

These are correct for Office 365 email.

