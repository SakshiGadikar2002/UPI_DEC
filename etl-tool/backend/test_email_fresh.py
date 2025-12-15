#!/usr/bin/env python3
"""
Fresh email test - clears environment and reloads
"""
import sys
import os

# Clear any cached environment variables
if 'SMTP_USE_TLS' in os.environ:
    del os.environ['SMTP_USE_TLS']
if 'SMTP_REQUIRE_AUTH' in os.environ:
    del os.environ['SMTP_REQUIRE_AUTH']

# Now load dotenv fresh
from dotenv import load_dotenv
load_dotenv(override=True)

print(f"SMTP_USE_TLS: {os.getenv('SMTP_USE_TLS')}")
print(f"SMTP_REQUIRE_AUTH: {os.getenv('SMTP_REQUIRE_AUTH')}")

# Now import after env is clean
from services.notification_service import EmailNotifier

notifier = EmailNotifier()
print(f"\nEmailNotifier TLS: {notifier.use_tls}")
print(f"EmailNotifier RequireAuth: {notifier.require_auth}")

# Test send
recipient = "aishwarya.sakharkar@arithwise.com"
success, error = notifier.send_email(
    recipients=[recipient],
    subject="🔔 Test Email - Auto Trigger",
    body="Test email from email trigger system"
)

if success:
    print(f"\n✅ Email sent successfully to {recipient}!")
else:
    print(f"\n❌ Failed: {error}")
