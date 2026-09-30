# core/exceptions.py
from typing import Any

__all__ = [
    "ArchitectureViolationError",
    "ServiceError",
    "ValidationError",
    "ConflictError",
    "NotFoundError",
    "EntityNotFoundError",
    "AuthenticationError",
    "ForbiddenError",
    "NotificationDeliveryError",
    "RateLimitExceededError",
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

class NotFoundError(ServiceError):
    """Raised when a requested resource or entity is not found."""
    pass

class EntityNotFoundError(NotFoundError):
    """Raised when a specific domain entity is not found by ID or key."""
    def __init__(self, entity_name: str = "Entity", entity_id: Any = None) -> None:
        self.entity_name = entity_name
        self.entity_id = entity_id
        msg = f"{entity_name} #{entity_id} not found." if entity_id is not None else f"{entity_name} not found."
        super().__init__(msg)

class AuthenticationError(ServiceError):
    """Raised when authentication credentials or verification fails."""
    pass

class ForbiddenError(ServiceError):
    """Raised when an authenticated actor attempts an operation lacking required permissions."""
    pass

class NotificationDeliveryError(ServiceError):
    """Raised when an outbound notification (e.g., email) fails to deliver."""
    pass

class RateLimitExceededError(AuthenticationError):
    """Raised when an operation is rate limited or temporarily locked out."""
    pass

