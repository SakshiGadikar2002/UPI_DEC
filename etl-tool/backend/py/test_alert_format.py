#!/usr/bin/env python3
"""
Generate sample alert email HTML for WARNING and CRITICAL alerts
"""
import os
from dotenv import load_dotenv
load_dotenv(override=True)

from services.notification_service import EmailNotifier
from services.crypto_alert_engine import CryptoAlertResponse, AlertCategory

notifier = EmailNotifier()

# Sample WARNING alert
warning_alert = CryptoAlertResponse(
    message="BTC price reached ₹95,000.00",
    category=AlertCategory.PRICE,
    reason="Price above threshold of ₹95,000.00",
    severity="warning",
    metadata={"price": "95,000.00", "change_1h": "8%"}
)

# Sample CRITICAL alert
critical_alert = CryptoAlertResponse(
    message="Binance not responding — using cached data",
    category=AlertCategory.ETL_SYSTEM,
    reason="API connection failure to Binance returned timeout",
    severity="critical",
    metadata={"endpoint": "https://api.binance.com", "error": "timeout"}
)

print("\n--- WARNING ALERT HTML (truncated) ---\n")
html_warn = notifier.format_alert_email(
    alert_message=warning_alert.message,
    alert_category=warning_alert.category,
    alert_reason=warning_alert.reason,
    severity=warning_alert.severity,
    metadata=warning_alert.metadata
)
print(html_warn[:1500])

print("\n--- CRITICAL ALERT HTML (truncated) ---\n")
html_crit = notifier.format_alert_email(
    alert_message=critical_alert.message,
    alert_category=critical_alert.category,
    alert_reason=critical_alert.reason,
    severity=critical_alert.severity,
    metadata=critical_alert.metadata
)
print(html_crit[:1500])

print("\n(Printed first 1500 characters of each email HTML.)\n")