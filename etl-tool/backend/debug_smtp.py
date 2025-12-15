#!/usr/bin/env python3
"""
Debug SMTP connection
"""
import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

smtp_host = os.getenv("SMTP_HOST", "smtp.office365.com")
smtp_port = int(os.getenv("SMTP_PORT", "587"))
smtp_user = os.getenv("SMTP_USER", "")
smtp_password = os.getenv("SMTP_PASSWORD", "")

print(f"🔍 SMTP Debug")
print(f"Host: {smtp_host}")
print(f"Port: {smtp_port}")
print(f"User: {smtp_user}")
print(f"Password: {'*' * len(smtp_password) if smtp_password else 'NOT SET'}")

try:
    print(f"\n1️⃣  Creating SMTP connection...")
    server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
    print(f"✓ Connected")
    
    print(f"\n2️⃣  Sending EHLO...")
    server.ehlo()
    print(f"✓ EHLO sent")
    
    print(f"\n3️⃣  Starting TLS...")
    server.starttls()
    print(f"✓ TLS started")
    
    print(f"\n4️⃣  Sending EHLO again...")
    server.ehlo()
    print(f"✓ EHLO sent")
    
    print(f"\n5️⃣  Checking AUTH...")
    has_auth = server.has_extn("auth")
    print(f"AUTH supported: {has_auth}")
    
    if has_auth:
        print(f"\n6️⃣  Authenticating...")
        server.login(smtp_user, smtp_password)
        print(f"✓ Authenticated")
    
    print(f"\n✅ All steps successful!")
    server.quit()
    
except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}")
    print(f"Message: {e}")
    import traceback
    traceback.print_exc()
