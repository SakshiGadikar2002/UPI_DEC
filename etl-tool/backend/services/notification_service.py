"""
Notification Service - Sends alerts via Email and Slack
"""
import logging
import smtplib
import asyncio
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any, Tuple
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Sends email notifications"""
    
    def __init__(self):
        # Accept both legacy and new env names
        self.smtp_server = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT") or os.getenv("SMTP_PORT", "587"))
        self.sender_email = (
            os.getenv("SMTP_FROM_EMAIL")
            or os.getenv("SMTP_USER")
            or os.getenv("SENDER_EMAIL", "")
        )
        self.sender_password = os.getenv("SMTP_PASSWORD") or os.getenv("SENDER_PASSWORD", "")
        # Allow disabling auth when server does not advertise SMTP AUTH (e.g., local relay)
        # Parse env variables as boolean strings (case-insensitive)
        # Handle both system environment variables (which may be string "False") and dotenv
        require_auth_str = os.getenv("SMTP_REQUIRE_AUTH", "true")
        # If string "False" or "false", explicitly set to False; otherwise parse as before
        if isinstance(require_auth_str, str) and require_auth_str.lower() == "false":
            self.require_auth = False
        else:
            self.require_auth = str(require_auth_str).lower() in ("true", "1", "yes", "on")
        
        use_tls_str = os.getenv("SMTP_USE_TLS", "true")
        # If string "False" or "false", explicitly set to False; otherwise parse as before
        if isinstance(use_tls_str, str) and use_tls_str.lower() == "false":
            self.use_tls = False
        else:
            self.use_tls = str(use_tls_str).lower() in ("true", "1", "yes", "on")
        
        # Log email configuration for debugging
        logger.info(f"SMTP Config - Server: {self.smtp_server}, Port: {self.smtp_port}, User: {self.sender_email}, TLS: {self.use_tls}, RequireAuth: {self.require_auth}")
    
    def send_email(self, recipients: List[str], subject: str, body: str, html: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Send email notification
        
        Args:
            recipients: List of email addresses
            subject: Email subject
            body: Email body content
            html: Whether body is HTML
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            if not self.sender_email:
                return False, "Email sender address not configured"
            
            if self.require_auth and not self.sender_password:
                return False, "Email credentials not configured"
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = ", ".join(recipients)
            # Mark as high importance so it appears flagged in most clients
            msg['X-Priority'] = '1'
            msg['X-MSMail-Priority'] = 'High'
            msg['Importance'] = 'High'
            
            # Attach body
            mime_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, mime_type, 'utf-8'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()

                auth_supported = server.has_extn("auth")
                logger.debug(f"SMTP AUTH supported: {auth_supported}, require_auth: {self.require_auth}")
                
                if auth_supported and (self.require_auth or self.sender_password):
                    try:
                        server.login(self.sender_email, self.sender_password)
                        logger.debug(f"Authenticated with SMTP server")
                    except smtplib.SMTPAuthenticationError as e:
                        return False, f"Email authentication failed: {str(e)}"
                elif self.require_auth and not auth_supported:
                    return False, "SMTP AUTH not supported by server; set SMTP_REQUIRE_AUTH=False to send without login"

                server.send_message(msg)
            
            logger.info(f"Email sent to {recipients}")
            return True, None
        except smtplib.SMTPAuthenticationError as e:
            error = f"Email authentication failed: {str(e)}"
            logger.error(error)
            return False, error
        except smtplib.SMTPException as e:
            error = f"SMTP error: {str(e)}"
            logger.error(error)
            return False, error
        except Exception as e:
            error = f"Email send error: {str(e)}"
            logger.error(error)
            return False, error
    
    @staticmethod
    def format_alert_email(alert_message: str, alert_category: str, alert_reason: str, 
                          severity: str, metadata: Optional[Dict] = None) -> str:
        """
        Format alert as professional HTML email
        
        Args:
            alert_message: Main alert message
            alert_category: Alert category (e.g., price_alerts, volume_liquidity_alerts)
            alert_reason: Reason for alert
            severity: Alert severity (info, warning, critical)
            metadata: Additional metadata to display
        
        Returns:
            HTML email body as string
        """
        # Get current time in IST
        from datetime import datetime
        import pytz
        
        ist = pytz.timezone('Asia/Kolkata')
        current_time_ist = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Color and icon mapping for severity
        severity_config = {
            'critical': {'color': '#DC2626', 'emoji': '🔴', 'label': 'CRITICAL'},
            'warning': {'color': '#F59E0B', 'emoji': '🟡', 'label': 'WARNING'},
            'info': {'color': '#3B82F6', 'emoji': '🔵', 'label': 'INFO'}
        }
        
        severity_info = severity_config.get(severity.lower(), severity_config['info'])
        
        # Category label mapping
        category_labels = {
            'price_alerts': '💰 Price Alert',
            'volume_liquidity_alerts': '📊 Volume Alert',
            'trend_technical_alerts': '📈 Technical Alert',
            'portfolio_watchlist_alerts': '💼 Portfolio Alert',
            'etl_system_alerts': '⚙️ System Alert',
            'security_account_alerts': '🔒 Security Alert',
            'news_fundamental_alerts': '📰 News Alert'
        }
        
        category_label = category_labels.get(alert_category, alert_category)
        
        # Additional metadata HTML
        metadata_html = ""
        if metadata:
            metadata_html = '<div style="margin-top: 15px; padding: 10px; background-color: #f3f4f6; border-radius: 5px;">'
            for key, value in metadata.items():
                # Format key nicely
                formatted_key = key.replace('_', ' ').title()
                metadata_html += f'<p style="margin: 5px 0; font-size: 13px;"><strong>{formatted_key}:</strong> {value}</p>'
            metadata_html += '</div>'
        
        html_body = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #f9fafb;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background-color: #ffffff;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, {severity_info['color']} 0%, {severity_info['color']}dd 100%);
                    color: white;
                    padding: 30px 20px;
                    text-align: center;
                }}
                .header-icon {{
                    font-size: 40px;
                    margin-bottom: 10px;
                }}
                .severity-badge {{
                    display: inline-block;
                    background-color: rgba(255, 255, 255, 0.2);
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 12px;
                    margin-top: 10px;
                }}
                .content {{
                    padding: 30px;
                }}
                .alert-title {{
                    font-size: 22px;
                    font-weight: bold;
                    color: #1f2937;
                    margin-bottom: 5px;
                }}
                .alert-category {{
                    font-size: 14px;
                    color: #6b7280;
                    margin-bottom: 20px;
                }}
                .alert-message {{
                    background-color: #f0fdf4;
                    border-left: 4px solid {severity_info['color']};
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                    font-size: 16px;
                    color: #1f2937;
                }}
                .alert-reason {{
                    background-color: #eff6ff;
                    border-left: 4px solid #3b82f6;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                    font-size: 14px;
                    color: #1e40af;
                }}
                .metadata-section {{
                    margin-top: 20px;
                }}
                .footer {{
                    background-color: #f3f4f6;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #6b7280;
                    border-top: 1px solid #e5e7eb;
                }}
                .timestamp {{
                    color: #6b7280;
                    font-size: 13px;
                    margin-top: 10px;
                }}
                .divider {{
                    height: 1px;
                    background-color: #e5e7eb;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="header-icon">{severity_info['emoji']}</div>
                    <div>{severity_info['label']} ALERT</div>
                    <div class="severity-badge">{severity_info['label']}</div>
                </div>
                
                <div class="content">
                    <div class="alert-category">{category_label}</div>
                    <div class="alert-title">{alert_message}</div>
                    
                    <div class="divider"></div>
                    
                    <div class="alert-reason">
                        <strong>Details:</strong><br/>
                        {alert_reason}
                    </div>
                    
                    {f'<div class="metadata-section">{metadata_html}</div>' if metadata_html else ''}
                    
                    <div class="timestamp">
                        <strong>Time:</strong> {current_time_ist}
                    </div>
                </div>
                
                <div class="footer">
                    <p>This is an automated alert from your Crypto Monitoring System.</p>
                    <p>Please review the alert and take necessary action if required.</p>
                    <p style="margin-top: 10px; color: #9ca3af;">Do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_body


class SlackNotifier:
    """Sends Slack notifications"""
    
    @staticmethod
    async def send_slack(webhook_url: str, message: str, title: Optional[str] = None, 
                        severity: str = "warning", metadata: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """
        Send Slack notification via webhook
        
        Args:
            webhook_url: Slack webhook URL
            message: Alert message
            title: Alert title
            severity: Alert severity (info, warning, critical)
            metadata: Additional metadata to display
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Determine color based on severity
            color_map = {
                'info': '#36a64f',
                'warning': '#ff9900',
                'critical': '#ff0000'
            }
            color = color_map.get(severity, '#0099ff')
            
            # Build Slack message
            fields = [
                {
                    "title": "Severity",
                    "value": severity.upper(),
                    "short": True
                },
                {
                    "title": "Time",
                    "value": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                    "short": True
                }
            ]
            
            # Add metadata fields if present
            if metadata:
                for key, value in metadata.items():
                    fields.append({
                        "title": key.replace('_', ' ').title(),
                        "value": str(value),
                        "short": True
                    })
            
            payload = {
                "attachments": [
                    {
                        "fallback": title or message,
                        "color": color,
                        "title": title,
                        "text": message,
                        "fields": fields,
                        "footer": "Alert System",
                        "ts": int(datetime.utcnow().timestamp())
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        logger.info(f"Slack message sent successfully")
                        return True, None
                    else:
                        error = f"Slack webhook returned status {response.status}"
                        logger.error(error)
                        return False, error
        except asyncio.TimeoutError:
            error = "Slack notification timeout"
            logger.error(error)
            return False, error
        except Exception as e:
            error = f"Slack notification error: {str(e)}"
            logger.error(error)
            return False, error


class NotificationService:
    """Orchestrates notifications through multiple channels"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.email_notifier = EmailNotifier()
    
    async def send_alert(self, alert_id: int, rule: Dict[str, Any], title: str, 
                        message: str, severity: str = "warning", metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send alert through configured notification channels
        
        Args:
            alert_id: Alert log ID
            rule: Alert rule details
            title: Alert title
            message: Alert message
            severity: Alert severity
            metadata: Additional metadata
        
        Returns:
            Dictionary with notification results
        """
        results = {
            'alert_id': alert_id,
            'email_sent': False,
            'slack_sent': False,
            'errors': []
        }
        
        try:
            channels = rule.get('notification_channels', 'email')
            email_recipients = rule.get('email_recipients')
            slack_webhook = rule.get('slack_webhook_url')
            
            # Parse email_recipients if it's a JSON string
            if isinstance(email_recipients, str):
                try:
                    email_recipients = json.loads(email_recipients)
                except:
                    email_recipients = [e.strip() for e in email_recipients.split(',')]
            
            # Send email notification
            if channels in ['email', 'both'] and email_recipients:
                success, error = self.email_notifier.send_email(
                    email_recipients,
                    subject=f"[{severity.upper()}] {title}",
                    body=self._format_email_body(title, message, severity, metadata),
                    html=True
                )
                results['email_sent'] = success
                if error:
                    results['errors'].append(f"Email: {error}")
                
                # Log notification in queue
                await self._log_notification(alert_id, 'email', email_recipients[0] if email_recipients else None, 
                                            'sent' if success else 'failed', error)
            
            # Send Slack notification
            if channels in ['slack', 'both'] and slack_webhook:
                success, error = await SlackNotifier.send_slack(
                    slack_webhook,
                    message=message,
                    title=title,
                    severity=severity,
                    metadata=metadata
                )
                results['slack_sent'] = success
                if error:
                    results['errors'].append(f"Slack: {error}")
                
                # Log notification in queue
                await self._log_notification(alert_id, 'slack', None, 
                                            'sent' if success else 'failed', error)
            
            # Update alert log status
            await self._update_alert_status(alert_id, 'sent')
            
            return results
        except Exception as e:
            logger.error(f"Error sending alert {alert_id}: {e}")
            results['errors'].append(f"General error: {str(e)}")
            return results
    
    def _format_email_body(self, title: str, message: str, severity: str, 
                          metadata: Optional[Dict] = None) -> str:
        """Format a compact, readable HTML email"""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        severity_label = severity.upper()

        metadata_rows = ""
        if metadata:
            for key, value in metadata.items():
                metadata_rows += f"""
                <tr>
                    <td style="padding:6px 8px;border:1px solid #e5e7eb;background:#f9fafb;">{key.replace('_',' ').title()}</td>
                    <td style="padding:6px 8px;border:1px solid #e5e7eb;">{value}</td>
                </tr>
                """
        if not metadata_rows:
            metadata_rows = """
            <tr>
                <td style="padding:6px 8px;border:1px solid #e5e7eb;background:#f9fafb;">Details</td>
                <td style="padding:6px 8px;border:1px solid #e5e7eb;">No extra metadata provided</td>
            </tr>
            """

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #111827; background: #f8fafc; padding: 12px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:auto;background:#fff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="background:#0f4c81;color:#fff;padding:14px 16px;font-size:18px;font-weight:700;">
                {title}
              </td>
            </tr>
            <tr>
              <td style="padding:14px 16px;font-size:14px;line-height:1.5;">
                <div style="margin-bottom:10px;"><strong>Severity:</strong> {severity_label}</div>
                <div style="margin-bottom:10px;"><strong>Time (UTC):</strong> {timestamp}</div>
                <div style="margin:12px 0 6px 0;"><strong>Message</strong></div>
                <div style="padding:10px 12px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;">{message}</div>
                <div style="margin:14px 0 6px 0;"><strong>Details</strong></div>
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px;">
                  {metadata_rows}
                </table>
                <div style="margin-top:16px;padding-top:10px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;">
                  Price threshold alerts (e.g., BTC &gt; $50k)<br/>
                  Volatility alerts (&gt; 5% in 10 min)<br/>
                  Data missing alerts (API down for X minutes)<br/>
                  System health alerts (DB full, API failing, etc.)<br/>
                  Email/Slack notifications · Alert history log
                </div>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """
    
    async def _log_notification(self, alert_id: int, channel: str, recipient: Optional[str],
                               status: str, error_message: Optional[str] = None) -> bool:
        """Log notification attempt in database"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO notification_queue 
                    (alert_id, channel, recipient, status, error_message, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                """, alert_id, channel, recipient, status, error_message)
                return True
        except Exception as e:
            logger.error(f"Error logging notification: {e}")
            return False
    
    async def _update_alert_status(self, alert_id: int, status: str) -> bool:
        """Update alert status in database"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE alert_logs
                    SET status = $1, sent_at = NOW()
                    WHERE id = $2
                """, status, alert_id)
                return True
        except Exception as e:
            logger.error(f"Error updating alert status: {e}")
            return False
    
    async def get_pending_notifications(self, limit: int = 100) -> List[Dict]:
        """Get pending notifications from queue"""
        try:
            async with self.db_pool.acquire() as conn:
                notifications = await conn.fetch("""
                    SELECT id, alert_id, channel, recipient, retry_count, max_retries
                    FROM notification_queue
                    WHERE status = 'pending' AND retry_count < max_retries
                    ORDER BY created_at ASC
                    LIMIT $1
                """, limit)
                
                return [dict(n) for n in notifications]
        except Exception as e:
            logger.error(f"Error getting pending notifications: {e}")
            return []
    
    async def retry_notification(self, notification_id: int) -> bool:
        """Retry failed notification"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE notification_queue
                    SET retry_count = retry_count + 1, last_retry_at = NOW()
                    WHERE id = $1
                """, notification_id)
                return True
        except Exception as e:
            logger.error(f"Error retrying notification: {e}")
            return False
