"""Email alert on pipeline failure. Self-skips if unconfigured -- same guard the
real send_email.py used, so the demo works with zero setup.
"""
import smtplib
from email.mime.text import MIMEText

from pipeline import config


def send_alert(subject, body):
    if not config.ALERT_EMAIL or not config.ALERT_APP_PASSWORD:
        print(f"[ALERT-SKIPPED] not configured -- would have sent: {subject}")
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.ALERT_EMAIL
    msg["To"] = config.ALERT_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.ALERT_EMAIL, config.ALERT_APP_PASSWORD)
        server.send_message(msg)
    print(f"[ALERT] sent: {subject}")
