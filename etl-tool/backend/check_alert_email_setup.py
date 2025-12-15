"""
Check alert email setup, ensure alert tables are populated, and send a test email
"""
import asyncio
import sys
from typing import Optional, List, Dict, Any

sys.path.insert(0, ".")

from database import get_pool, connect_to_postgres
from services.notification_service import NotificationService


async def ensure_test_rule(conn, recipients: List[str]) -> Dict[str, Any]:
    """
    Ensure a test alert rule exists with the given recipients.
    Returns the rule as a dict.
    """
    recipients_str = ",".join(recipients)

    rule_row = await conn.fetchrow(
        """
        INSERT INTO alert_rules (
            name, alert_type, enabled, description,
            notification_channels, email_recipients,
            severity, cooldown_minutes, max_alerts_per_day
        )
        VALUES ($1, 'system_health', TRUE, 'Test email alert rule',
                'email', $2, 'warning', 0, 10)
        ON CONFLICT (name) DO UPDATE
        SET email_recipients = EXCLUDED.email_recipients,
            enabled = TRUE,
            severity = EXCLUDED.severity,
            notification_channels = EXCLUDED.notification_channels
        RETURNING id, name, alert_type, enabled, email_recipients, severity, notification_channels
        """,
        "Email Test Alert",
        recipients_str,
    )

    rule = dict(rule_row)

    # Ensure alert_tracking entry exists
    await conn.execute(
        """
        INSERT INTO alert_tracking (rule_id, last_alert_time, alert_count_today)
        VALUES ($1, NOW(), 0)
        ON CONFLICT (rule_id) DO NOTHING
        """,
        rule["id"],
    )

    return rule


async def create_test_alert_log(conn, rule: Dict[str, Any]) -> int:
    """
    Create a test alert log entry and return its id.
    """
    alert_id = await conn.fetchval(
        """
        INSERT INTO alert_logs (
            rule_id, alert_type, title, message, severity, status, metadata, created_at
        )
        VALUES ($1, $2, $3, $4, $5, 'open', $6, NOW())
        RETURNING id
        """,
        rule["id"],
        rule["alert_type"],
        "Test Email Alert",
        "This is a test alert email triggered by check_alert_email_setup.py",
        rule.get("severity", "warning"),
        "{}",
    )
    return alert_id


async def send_test_email(pool, recipient_email: str) -> Dict[str, Any]:
    """
    Ensure a rule exists, create an alert log, and send an email using notification_service.
    Returns the send_alert result.
    """
    async with pool.acquire() as conn:
        rule = await ensure_test_rule(conn, [recipient_email])
        alert_id = await create_test_alert_log(conn, rule)

    service = NotificationService(pool)
    result = await service.send_alert(
        alert_id=alert_id,
        rule=rule,
        title="Test Email Alert",
        message="This is a test alert email triggered by check_alert_email_setup.py",
        severity=rule.get("severity", "warning"),
        metadata={"source": "check_alert_email_setup"},
    )
    return {"alert_id": alert_id, "result": result}


async def check_setup():
    """Check alert email setup and send a test email to the first active user"""
    await connect_to_postgres()
    pool = get_pool()

    print("=" * 80)
    print("ALERT EMAIL SETUP CHECK")
    print("=" * 80)

    async with pool.acquire() as conn:
        # Check active users
        users = await conn.fetch(
            """
            SELECT id, email, full_name, is_active FROM users WHERE is_active = TRUE
            """
        )

        print(f"\n[EMAIL] Active Users ({len(users)}):")
        if users:
            for user in users:
                print(f"  [OK] {user['email']} ({user['full_name'] or 'No name'})")
        else:
            print("  [WARN] No active users found!")

        # Check alert rules
        rules = await conn.fetch(
            """
            SELECT id, name, alert_type, enabled, email_recipients
            FROM alert_rules
            """
        )

        print(f"\n[RULES] Alert Rules ({len(rules)}):")
        if rules:
            for rule in rules:
                status = "[ENABLED]" if rule["enabled"] else "[DISABLED]"
                emails = rule["email_recipients"] or "No email recipients"
                print(f"  {status} Rule {rule['id']}: {rule['name']} ({rule['alert_type']})")
                print(f"         Email recipients: {emails}")
        else:
            print("  [WARN] No alert rules found!")

        # Check recent alert logs
        recent_alerts = await conn.fetch(
            """
            SELECT id, rule_id, title, severity, status, created_at
            FROM alert_logs
            ORDER BY created_at DESC
            LIMIT 5
            """
        )

        print(f"\n[ALERTS] Recent Alert Logs ({len(recent_alerts)}):")
        if recent_alerts:
            for alert in recent_alerts:
                print(f"  [{alert['severity'].upper()}] {alert['title']} (Status: {alert['status']})")
                print(f"         Created: {alert['created_at']}")
        else:
            print("  [INFO] No recent alerts")

        # Check notification queue
        notifications = await conn.fetch(
            """
            SELECT id, alert_id, channel, recipient, status, error_message, created_at
            FROM notification_queue
            ORDER BY created_at DESC
            LIMIT 5
            """
        )

        print(f"\n[NOTIFICATIONS] Recent Notifications ({len(notifications)}):")
        if notifications:
            for notif in notifications:
                status_icon = "[OK]" if notif["status"] == "sent" else "[FAIL]"
                print(
                    f"  {status_icon} [{notif['status'].upper()}] Channel: {notif['channel']}, Recipient: {notif['recipient']}"
                )
                if notif["error_message"]:
                    print(f"         Error: {notif['error_message']}")
        else:
            print("  [INFO] No notifications in queue")

        # Recommendations
        print("\n[RECOMMENDATIONS]:")
        if not users:
            print("  [WARN] Create at least one active user account")
        if not rules:
            print("  [WARN] Create alert rules via API: POST /api/alerts/rules")
        else:
            rules_without_emails = [r for r in rules if not r["email_recipients"]]
            if rules_without_emails:
                print(f"  [WARN] {len(rules_without_emails)} alert rules don't have email recipients")
                print("     Run: python update_alert_rules_with_user_emails.py")
            else:
                print("  [OK] All alert rules have email recipients")

        # Check SMTP config
        import os
        from dotenv import load_dotenv

        load_dotenv()

        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = os.getenv("SMTP_PORT")
        smtp_user = os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_USER")
        smtp_password = "***" if os.getenv("SMTP_PASSWORD") else "NOT SET"

        print(f"\n[SMTP] SMTP Configuration:")
        print(f"  Host: {smtp_host or 'NOT SET'}")
        print(f"  Port: {smtp_port or 'NOT SET'}")
        print(f"  User: {smtp_user or 'NOT SET'}")
        print(f"  Password: {smtp_password}")

        if not smtp_host or not smtp_user or not os.getenv("SMTP_PASSWORD"):
            print("  [WARN] SMTP configuration incomplete - emails will not be sent!")
        else:
            print("  [OK] SMTP configuration looks good")

    # Send a test email to the first active user
    if users:
        recipient = users[0]["email"]
        print(f"\n[SEND] Sending test alert email to {recipient} ...")
        send_result = await send_test_email(pool, recipient)
        print(f"  Alert ID: {send_result['alert_id']}")
        print(f"  Email sent: {send_result['result'].get('email_sent')}")
        errors = send_result['result'].get('errors')
        if errors:
            print(f"  Errors: {errors}")
    else:
        print("\n[SEND] Skipping test email: no active users found.")


if __name__ == "__main__":
    asyncio.run(check_setup())
