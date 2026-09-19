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

    @classmethod
    def send_admin_reset_otp_email(
        cls,
        recipient_email: str,
        username: str,
        otp_code: str,
        ttl_minutes: int = 5,
    ) -> bool:
        """Sends OTP to Administrator for authorizing an Admin password reset."""
        subject = "Sudharm SIMS — Admin Password Reset Authorization OTP"
        body_text = (
            f"Hello {username},\n\n"
            f"An Admin password reset authorization was requested on Sudharm SIMS.\n\n"
            f"Your authorization OTP code is: {otp_code}\n\n"
            f"This code will expire in {ttl_minutes} minutes. If you did not initiate this request, "
            f"please immediately review active sessions and change your credentials.\n\n"
            f"— Sudharm SIMS Security"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; padding: 20px;">
    <h2 style="color: #c53030;">Sudharm SIMS — Admin Password Reset Authorization</h2>
    <p>Hello <strong>{username}</strong>,</p>
    <p>An Admin password reset authorization was requested on Sudharm SIMS.</p>
    <div style="background-color: #fff5f5; border: 2px solid #feb2b2; border-radius: 8px; padding: 16px; margin: 24px 0; text-align: center;">
        <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #c53030;">{otp_code}</span>
    </div>
    <p>This code will expire in <strong>{ttl_minutes} minutes</strong>. Enter this code in Control Center to complete the password reset.</p>
    <p style="color: #718096; font-size: 13px;">If you did not initiate this request, please review your account security immediately.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #a0aec0; font-size: 12px;">Sudharm SIMS Security Service</p>
</body>
</html>"""
        LogService.info(f"Dispatching Admin Reset OTP email to {recipient_email}", context="NOTIFICATION")
        return SmtpTransport.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    @classmethod
    def send_recovery_otp_email(
        cls,
        recipient_email: str,
        username: str,
        otp_code: str,
        ttl_minutes: int = 5,
    ) -> bool:
        """Sends OTP to Administrator for self-service password recovery."""
        subject = "Sudharm SIMS — Password Recovery Verification Code"
        body_text = (
            f"Hello {username},\n\n"
            f"A password recovery request was received for your Administrator account.\n\n"
            f"Your recovery verification code is: {otp_code}\n\n"
            f"This code will expire in {ttl_minutes} minutes. If you did not request a password reset, "
            f"you can safely ignore this email.\n\n"
            f"— Sudharm SIMS Security"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; padding: 20px;">
    <h2 style="color: #2b6cb0;">Sudharm SIMS — Password Recovery</h2>
    <p>Hello <strong>{username}</strong>,</p>
    <p>A password recovery request was received for your Administrator account.</p>
    <div style="background-color: #ebf8ff; border: 2px solid #bee3f8; border-radius: 8px; padding: 16px; margin: 24px 0; text-align: center;">
        <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #2b6cb0;">{otp_code}</span>
    </div>
    <p>This code will expire in <strong>{ttl_minutes} minutes</strong>.</p>
    <p style="color: #718096; font-size: 13px;">If you did not request this code, no action is needed.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #a0aec0; font-size: 12px;">Sudharm SIMS Security Service</p>
</body>
</html>"""
        LogService.info(f"Dispatching Password Recovery OTP email to {recipient_email}", context="NOTIFICATION")
        return SmtpTransport.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    @classmethod
    def send_email_change_current_notice(
        cls,
        recipient_email: str,
        username: str,
        otp_code: str,
        new_email: str,
        ttl_minutes: int = 15,
    ) -> bool:
        """Sends dual-verification OTP to current email address."""
        subject = "Sudharm SIMS — Email Address Change Verification (Current Email)"
        body_text = (
            f"Hello {username},\n\n"
            f"A request has been made to change your Administrator account email to: {new_email}\n\n"
            f"To authorize this change from your current email address, your verification code is: {otp_code}\n\n"
            f"This code will expire in {ttl_minutes} minutes. Both your current and new email addresses "
            f"must be verified before the change takes effect.\n\n"
            f"If you did NOT request this change, please contact system support immediately!\n\n"
            f"— Sudharm SIMS Security"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; padding: 20px;">
    <h2 style="color: #c53030;">Sudharm SIMS — Authorize Email Change</h2>
    <p>Hello <strong>{username}</strong>,</p>
    <p>A request has been made to change your Administrator account email to: <strong>{new_email}</strong></p>
    <p>Your current-email verification code is:</p>
    <div style="background-color: #fff5f5; border: 2px solid #feb2b2; border-radius: 8px; padding: 16px; margin: 24px 0; text-align: center;">
        <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #c53030;">{otp_code}</span>
    </div>
    <p>This code expires in <strong>{ttl_minutes} minutes</strong>. Dual-verification is required.</p>
    <p style="color: #e53e3e; font-weight: bold;">If you did not request this change, secure your account immediately!</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #a0aec0; font-size: 12px;">Sudharm SIMS Security Service</p>
</body>
</html>"""
        LogService.info(f"Dispatching current email change OTP to {recipient_email}", context="NOTIFICATION")
        return SmtpTransport.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    @classmethod
    def send_email_change_new_verification(
        cls,
        recipient_email: str,
        username: str,
        otp_code: str,
        ttl_minutes: int = 15,
    ) -> bool:
        """Sends dual-verification OTP to prospective new email address."""
        subject = "Sudharm SIMS — Confirm New Email Address Verification"
        body_text = (
            f"Hello {username},\n\n"
            f"You have requested to set this email address as your new Administrator account email on Sudharm SIMS.\n\n"
            f"Your new-email verification code is: {otp_code}\n\n"
            f"This code will expire in {ttl_minutes} minutes. Dual-verification must be completed to finalize.\n\n"
            f"— Sudharm SIMS Security"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; padding: 20px;">
    <h2 style="color: #2b6cb0;">Sudharm SIMS — Confirm New Email Address</h2>
    <p>Hello <strong>{username}</strong>,</p>
    <p>You have requested to set this email address as your new Administrator account email on Sudharm SIMS.</p>
    <div style="background-color: #ebf8ff; border: 2px solid #bee3f8; border-radius: 8px; padding: 16px; margin: 24px 0; text-align: center;">
        <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #2b6cb0;">{otp_code}</span>
    </div>
    <p>This code expires in <strong>{ttl_minutes} minutes</strong>.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #a0aec0; font-size: 12px;">Sudharm SIMS Security Service</p>
</body>
</html>"""
        LogService.info(f"Dispatching new email change OTP to {recipient_email}", context="NOTIFICATION")
        return SmtpTransport.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    @classmethod
    def send_recovery_key_delivery_email(
        cls,
        recipient_email: str,
        username: str,
        recovery_key: str,
        key_id: str,
    ) -> bool:
        """Sends newly generated Break-Glass recovery key backup to Administrator email."""
        subject = f"Sudharm SIMS — Break-Glass Emergency Recovery Key [{key_id}]"
        body_text = (
            f"Hello {username},\n\n"
            f"A Break-Glass Emergency Recovery Key has been generated for your Administrator account.\n\n"
            f"Key Identifier: {key_id}\n"
            f"Recovery Key:   {recovery_key}\n\n"
            f"IMPORTANT SECURITY NOTICE:\n"
            f"1. Store this recovery key in a secure offline password manager or encrypted vault.\n"
            f"2. This key possesses single-use Break-Glass authority and will immediately invalidate itself upon use.\n"
            f"3. Any previously generated recovery key has been permanently invalidated.\n"
            f"4. If you did not request this key, your account may be compromised!\n\n"
            f"— Sudharm SIMS Security"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; padding: 20px;">
    <h2 style="color: #1a365d;">Sudharm SIMS — Emergency Recovery Key</h2>
    <p>Hello <strong>{username}</strong>,</p>
    <p>A Break-Glass Emergency Recovery Key has been generated for your Administrator account.</p>
    <div style="background-color: #f7fafc; border: 2px solid #cbd5e0; border-radius: 8px; padding: 20px; margin: 24px 0;">
        <div style="font-size: 12px; color: #718096; margin-bottom: 8px;">KEY IDENTIFIER: <strong>{key_id}</strong></div>
        <div style="font-family: monospace; font-size: 20px; font-weight: bold; color: #2b6cb0; word-break: break-all; letter-spacing: 2px;">
            {recovery_key}
        </div>
    </div>
    <div style="background-color: #fffaf0; border-left: 4px solid #dd6b20; padding: 12px; margin: 20px 0;">
        <strong style="color: #c05621;">CRITICAL SECURITY INSTRUCTIONS:</strong>
        <ul style="margin: 8px 0; padding-left: 20px; color: #4a5568; font-size: 14px;">
            <li>Store this key in an encrypted vault or safe physical storage.</li>
            <li>This single-use key is your emergency recovery credential if you lose access to your password or email.</li>
            <li>Any prior recovery key is now permanently revoked.</li>
        </ul>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #a0aec0; font-size: 12px;">Sudharm SIMS Security Service</p>
</body>
</html>"""
        LogService.info(f"Dispatching Recovery Key delivery email to {recipient_email}", context="NOTIFICATION")
        return SmtpTransport.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    @classmethod
    def send_password_changed_alert(
        cls,
        recipient_email: str,
        username: str,
        change_type: str = "Password Reset",
    ) -> bool:
        """Sends security alert notification when credentials are changed."""
        subject = f"Sudharm SIMS — Security Alert: {change_type} Completed"
        body_text = (
            f"Hello {username},\n\n"
            f"A security change ({change_type}) has been successfully completed for your account.\n\n"
            f"All existing active sessions have been terminated. If you did not perform this change, "
            f"please contact system administrators immediately!\n\n"
            f"— Sudharm SIMS Security"
        )
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; color: #222; line-height: 1.6; padding: 20px;">
    <h2 style="color: #2b6cb0;">Sudharm SIMS — Security Alert</h2>
    <p>Hello <strong>{username}</strong>,</p>
    <p>A security change (<strong>{change_type}</strong>) has been successfully completed for your account.</p>
    <p>All active sessions have been terminated for security. If you did not perform this change, please report this immediately.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #a0aec0; font-size: 12px;">Sudharm SIMS Security Service</p>
</body>
</html>"""
        LogService.info(f"Dispatching password changed alert email to {recipient_email}", context="NOTIFICATION")
        return SmtpTransport.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    @classmethod
    def send_emergency_email_probe(cls, recipient_email: str) -> bool:
        """Probes email deliverability before committing emergency email updates during Break-Glass."""
        subject = "Sudharm SIMS — Emergency Recovery Deliverability Verification"
        body_text = (
            "This is an automated verification probe confirming email deliverability for your "
            "Sudharm SIMS emergency recovery session.\n\n"
            "— Sudharm SIMS Security"
        )
        return SmtpTransport.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
        )
