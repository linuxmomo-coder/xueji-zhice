from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


class MailDeliveryError(RuntimeError):
    pass


def send_email(*, recipient: str, subject: str, text: str) -> bool:
    if settings.email_provider == "disabled":
        return False
    if settings.email_provider != "smtp" or not settings.smtp_host or not settings.smtp_from_email:
        raise MailDeliveryError("邮件服务未正确配置")

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            if settings.smtp_starttls:
                client.starttls()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password or "")
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailDeliveryError("邮件发送失败") from exc
    return True
