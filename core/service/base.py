# core/service/base.py

from __future__ import annotations
from contextlib import contextmanager
from typing import Iterator

from core.logger.service import LogService
from core.database.transaction import TransactionManager
from core.database.exceptions import DatabaseError
from core.exceptions import ServiceError, ValidationError, ConflictError, ArchitectureViolationError
from core.exceptions import ArchitectureViolationError

__all__ = ["BaseService"]


class BaseService:
    """
    Foundation for all Domain Services in SIMS.
    
    Responsibilities:
    1. Enforces Business Rules.
    2. Orchestrates Repository calls.
    3. Manages Transaction boundaries (Unit of Work).
    
    Strictly Forbids:
    - Raw SQL queries.
    - Database cursor manipulation.
    - Nested transactions (Service calling Service).
    """

    @classmethod
    @contextmanager
    def unit_of_work(cls) -> Iterator[None]:
        """
        Context manager for orchestrating transaction boundaries.
        Ensures that multiple repository operations either commit atomically
        or roll back entirely upon any business or database failure.
        
        Architecture Policy: Nested transactions are STRICTLY FORBIDDEN.
        """
        if TransactionManager.in_transaction():
            LogService.error("Architecture Violation: Nested transaction detected.", context=cls.__name__)
            raise ArchitectureViolationError(
                "Nested transactions are forbidden. A Service cannot call another Service's "
                "unit_of_work. Use an orchestration layer (Workflow) if multiple services "
                "must participate in a single transaction."
            )

        TransactionManager.begin()
        try:
            yield
            TransactionManager.commit()
        except ServiceError as exc:
            TransactionManager.rollback()
            LogService.warning(f"Business rule violation: {exc}", context=cls.__name__)
            raise
        except DatabaseError as exc:
            TransactionManager.rollback()
            LogService.error(f"Database execution failed during transaction: {exc}", context=cls.__name__)
            raise ServiceError("An internal database error occurred while processing the request.") from exc
        except Exception as exc:
            TransactionManager.rollback()
            LogService.error(f"Unexpected system failure during transaction: {exc}", context=cls.__name__)
            raise ServiceError("An unexpected system error occurred.") from exc
