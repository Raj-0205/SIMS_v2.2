# core/exceptions.py

__all__ = [
    "ArchitectureViolationError",
    "ServiceError",
    "ValidationError",
    "ConflictError"
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
