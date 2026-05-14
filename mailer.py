"""Mailer — envía el reporte HTML vía Gmail SMTP."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def send_report(html_content: str, recipients: list[str], subject: str, config: dict) -> bool:
    gmail_user = config["gmail_user"]
    gmail_password = config["gmail_password"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Digest Tributario Chile <{gmail_user}>"
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText("Este email requiere un cliente de email con soporte HTML.", "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, recipients, msg.as_string())
        log.info(f"  Enviado a: {', '.join(recipients)}")
        return True
    except Exception as e:
        log.error(f"  Error enviando email: {e}")
        raise
