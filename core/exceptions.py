# core/exceptions.py

__all__ = [
    "ArchitectureViolationError",
    "ServiceError",
    "ValidationError",
    "ConflictError",
    "AuthenticationError",
    "ForbiddenError",
    "NotificationDeliveryError",
]

class ArchitectureViolationError(Exception):
    """Raised when application layers are bypassed (e.g., UI touching DB without Service)."""
    pass

class ServiceError(Exception):
    """Base class for all business logic and service layer errors."""
    pass

class ValidationError(ServiceError):
    """Raised when business logic validation fails (e.g., missing required fields)."""
    pass

class ConflictError(ServiceError):
    """Raised when there is a data conflict (e.g., duplicate records, foreign key constraint)."""
    pass

class AuthenticationError(ServiceError):
    """Raised when authentication credentials or verification fails."""
    pass

class ForbiddenError(ServiceError):
    """Raised when an authenticated actor attempts an operation lacking required permissions."""
    pass

class NotificationDeliveryError(ServiceError):
    """Raised when an outbound notification (e.g., email) fails to deliver."""
    pass

