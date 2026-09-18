# infrastructure/notification/service.py

from __future__ import annotations
from infrastructure.notification.smtp_transport import SmtpTransport
from core.logger.service import LogService

__all__ = ["NotificationService"]


class NotificationService:
    """
    High-level Notification Service.

    Coordinates templating and delivery of critical security notifications (e.g., OTP codes).
    """

    @classmethod
    def send_otp_email(
        cls,
        recipient_email: str,
        username: str,
        otp_code: str,
        ttl_minutes: int = 5,
    ) -> bool:
        """
        Sends an OTP verification email to the user for privileged authentication.
        """
        subject = "Sudharm SIMS — Administrator Verification Code"
        body_text = (
            f"Hello {username},\n\n"
            f"A login request was initiated for your Administrator privileged account on Sudharm SIMS.\n\n"
            f"Your one-time verification code is: {otp_code}\n\n"
            f"This code will expire in {ttl_minutes} minutes. If you did not initiate this request, "
            f"please contact system support immediately and review your account security.\n\n"
            f"Do not share this code with anyone.\n\n"
            f"— Sudharm SIMS Security"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; padding: 20px;">
    <h2 style="color: #1a365d;">Sudharm SIMS — Administrator Verification</h2>
    <p>Hello <strong>{username}</strong>,</p>
    <p>A login request was initiated for your Administrator privileged account on Sudharm SIMS.</p>
    <div style="background-color: #f7fafc; border: 2px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 24px 0; text-align: center;">
        <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #2b6cb0;">{otp_code}</span>
    </div>
    <p>This code will expire in <strong>{ttl_minutes} minutes</strong>. If you did not initiate this request, please contact system support immediately.</p>
    <p style="color: #718096; font-size: 13px;">Never share this code with anyone. SIMS administrators or staff will never ask for your verification code.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #a0aec0; font-size: 12px;">Sudharm SIMS Security Service</p>
</body>
</html>"""

        LogService.info(
            f"Dispatching OTP email to {recipient_email} for user {username}",
            context="NOTIFICATION",
        )
        return SmtpTransport.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )
