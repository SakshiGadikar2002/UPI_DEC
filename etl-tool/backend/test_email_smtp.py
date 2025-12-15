#!/usr/bin/env python3
"""
Test script to verify email alert functionality
"""
import sys
import os

# Force reload of environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

from services.notification_service import EmailNotifier
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_email():
    """Test the email sending functionality"""
    print("\n=== EMAIL ALERT TEST ===\n")
    
    notifier = EmailNotifier()
    
    print(f"SMTP Configuration:")
    print(f"  Server: {notifier.smtp_server}")
    print(f"  Port: {notifier.smtp_port}")
    print(f"  From Email: {notifier.sender_email}")
    print(f"  Use TLS: {notifier.use_tls}")
    print(f"  Require Auth: {notifier.require_auth}")
    print()
    
    # Test email parameters
    test_recipients = ["aishwarya.sakharkar@arithwise.com"]
    test_subject = "[TEST] Alert Delivery Check"
    test_body_html = """
    <html>
        <body>
            <h2>Wisepipe - Alert Test</h2>
            <p>This is a test email from Wisepipe to verify SMTP functionality.</p>
            <p><strong>If you received this message, the email alert system is working correctly!</strong></p>
            <p style="color: #666; font-size: 12px;">Sent at: 2025-12-10 09:55:00</p>
        </body>
    </html>
    """
    
    print("Attempting to send test email...")
    print(f"  To: {', '.join(test_recipients)}")
    print(f"  Subject: {test_subject}")
    print()
    
    success, error = notifier.send_email(
        recipients=test_recipients,
        subject=test_subject,
        body=test_body_html,
        html=True
    )
    
    print("=" * 50)
    if success:
        print("✓ SUCCESS: Email sent successfully!")
        print("\nThe mail function is properly sending emails.")
        return 0
    else:
        print("✗ FAILURE: Failed to send email")
        print(f"Error: {error}")
        print("\nTroubleshooting:")
        print("1. Check SMTP credentials in .env file")
        print("2. Verify SMTP server is accessible")
        print("3. Check firewall/network settings")
        print("4. Ensure email account has less secure apps enabled (for Gmail)")
        return 1

if __name__ == "__main__":
    sys.exit(test_email())
