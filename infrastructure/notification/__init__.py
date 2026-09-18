# infrastructure/notification/__init__.py

from infrastructure.notification.service import NotificationService
from infrastructure.notification.smtp_transport import SmtpTransport

__all__ = ["NotificationService", "SmtpTransport"]
