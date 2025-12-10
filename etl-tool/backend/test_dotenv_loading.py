#!/usr/bin/env python3
"""
Minimal test to check env variable loading
"""
import os
import sys

# Print Python version and path
print(f"Python: {sys.version}")
print(f"Working dir: {os.getcwd()}")

# Print all env before loading dotenv
print(f"\nBefore dotenv load:")
print(f"SMTP_USE_TLS={os.getenv('SMTP_USE_TLS', 'NOT IN ENV')}")

# Now load dotenv
from dotenv import load_dotenv
load_dotenv(verbose=True)

print(f"\nAfter dotenv load:")
print(f"SMTP_USE_TLS={os.getenv('SMTP_USE_TLS', 'NOT IN ENV')}")
print(f"SMTP_REQUIRE_AUTH={os.getenv('SMTP_REQUIRE_AUTH', 'NOT IN ENV')}")
print(f"SMTP_HOST={os.getenv('SMTP_HOST', 'NOT IN ENV')}")

# Try to find .env
print(f"\n.env file exists: {os.path.exists('.env')}")
print(f".env full path: {os.path.abspath('.env')}")
