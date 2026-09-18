# infrastructure/notification/smtp_transport.py

from __future__ import annotations
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

from core.configuration.service import ConfigService
from core.exceptions import NotificationDeliveryError
from core.logger.service import LogService

__all__ = ["SmtpTransport"]


class SmtpTransport:
    """
    SMTP Email Transport Layer.

    Provides outbound email transmission with TLS support, environment-driven secrets,
    and a test sink hook for hermetic automated testing.
    """

    _test_sink: Optional[Callable[[str, str, str, Optional[str]], None]] = None

    @classmethod
    def set_test_sink(
        cls, sink: Optional[Callable[[str, str, str, Optional[str]], None]]
    ) -> None:
        """Register a test sink callback to intercept outbound emails during testing."""
        cls._test_sink = sink

    @classmethod
    def clear_test_sink(cls) -> None:
        """Clear any registered test sink."""
        cls._test_sink = None

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """
        Transmits an email message to the specified recipient.

        If a test sink is registered, it routes to the test sink instead of making network calls.
        """
        if not to_email or "@" not in to_email:
            raise NotificationDeliveryError(f"Invalid recipient email address: {to_email}")

        # If running in test mode with test sink attached, route directly to test sink
        if cls._test_sink is not None:
            cls._test_sink(to_email, subject, body_text, body_html)
            return True

        smtp_config = ConfigService.smtp()
        from_email = smtp_config.from_email
        from_name = smtp_config.from_name
        smtp_password = os.environ.get("SIMS_SMTP_PASSWORD")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        msg["To"] = to_email

        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=10) as server:
                if smtp_config.use_tls:
                    server.starttls()
                if smtp_config.username and smtp_password:
                    server.login(smtp_config.username, smtp_password)
                server.send_message(msg)
            LogService.info(f"Email sent successfully to {to_email}", context="NOTIFICATION")
            return True
        except Exception as exc:
            if ConfigService.app().environment == "development":
                outbox_dir = Path("exports/notifications")
                outbox_dir.mkdir(parents=True, exist_ok=True)
                outbox_file = outbox_dir / "dev_email_outbox.log"
                with open(outbox_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"TO: {to_email} | SUBJECT: {subject}\n"
                        f"{body_text}\n"
                        f"{'-'*60}\n"
                    )
                LogService.warning(
                    f"SMTP delivery failed to {to_email} ({type(exc).__name__}). "
                    f"Outbound notification saved to {outbox_file} for development testing.",
                    context="NOTIFICATION",
                )
                return True

            LogService.error(
                f"Failed to send email to {to_email}: {type(exc).__name__}",
                context="NOTIFICATION",
            )
            raise NotificationDeliveryError(
                f"Email notification delivery failed: {type(exc).__name__}"
            ) from exc
