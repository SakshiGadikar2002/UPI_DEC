#!/usr/bin/env python3
"""
Debug env variable parsing
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("Raw environment values:")
print(f"SMTP_USE_TLS raw: '{os.getenv('SMTP_USE_TLS', 'NOT SET')}'")
print(f"SMTP_REQUIRE_AUTH raw: '{os.getenv('SMTP_REQUIRE_AUTH', 'NOT SET')}'")

use_tls_str = os.getenv("SMTP_USE_TLS", "true").lower()
print(f"\nAfter .lower(): '{use_tls_str}'")
print(f"Check in tuple: {use_tls_str in ('true', '1', 'yes', 'on')}")

require_auth_str = os.getenv("SMTP_REQUIRE_AUTH", "true").lower()
print(f"\nSMTP_REQUIRE_AUTH after .lower(): '{require_auth_str}'")
print(f"Check in tuple: {require_auth_str in ('true', '1', 'yes', 'on')}")
