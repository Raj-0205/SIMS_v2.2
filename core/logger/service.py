# core/logger/service.py

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Final

from core.configuration.service import ConfigService
from core.logger.exceptions import LoggerInitializationError

__all__ = ["LogService"]


class LogService:
    """
    Central Logging Engine.
    
    Provides a thread-safe, rotating file and console logging service.
    Abstracts the underlying Python logging module to prevent leaks across 
    the enterprise architecture.
    """

    _is_initialized: bool = False
    _DEFAULT_CONTEXT: Final[str] = "SYSTEM"
    
    # 5 MB per file, max 5 backups = 25 MB total disk usage
    _MAX_BYTES: Final[int] = 5 * 1024 * 1024 
    _BACKUP_COUNT: Final[int] = 5

    @classmethod
    def initialize(cls) -> None:
        """
        Initializes the logging handlers, formatters, and rotation policy.
        Can safely be called multiple times but will only execute once.
        
        Raises:
            LoggerInitializationError: If directory creation or file locks fail.
        """
        if cls._is_initialized:
            return

        try:
            app_config = ConfigService.app()
            log_level = logging.DEBUG if app_config.debug else logging.INFO

            project_root = Path(__file__).resolve().parent.parent.parent
            log_dir = project_root / "runtime" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "sims.log"

            formatter = logging.Formatter(
                fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

            file_handler = RotatingFileHandler(
                filename=log_file,
                maxBytes=cls._MAX_BYTES,
                backupCount=cls._BACKUP_COUNT,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

            root_logger = logging.getLogger()
            root_logger.setLevel(log_level)
            
            if root_logger.hasHandlers():
                root_logger.handlers.clear()

            root_logger.addHandler(file_handler)
            root_logger.addHandler(console_handler)

            cls._is_initialized = True
            
            cls.info("Logger Engine initialized successfully.", context="LOGGER")

        except Exception as exc:
            raise LoggerInitializationError(
                f"Failed to initialize Logger Engine: {exc}"
            ) from exc

    @classmethod
    def is_initialized(cls) -> bool:
        """
        Checks if the logging engine has been successfully initialized.
        """
        return cls._is_initialized

    @classmethod
    def get_logger(cls, context: str) -> logging.Logger:
        """
        Retrieves a standard logger bound to a specific context name.
        Intended for internal framework use only.
        """
        return logging.getLogger(context.upper())

    @classmethod
    def _get_context_logger(cls, context: str | None) -> logging.Logger:
        """Internal helper to resolve the logger for generic calls."""
        name = context.upper() if context else cls._DEFAULT_CONTEXT
        return cls.get_logger(name)

    # =========================================================================
    # PUBLIC CONVENIENCE API
    # =========================================================================

    @classmethod
    def debug(cls, message: str, context: str | None = None, *args: Any, **kwargs: Any) -> None:
        cls._get_context_logger(context).debug(message, *args, **kwargs)

    @classmethod
    def info(cls, message: str, context: str | None = None, *args: Any, **kwargs: Any) -> None:
        cls._get_context_logger(context).info(message, *args, **kwargs)

    @classmethod
    def warning(cls, message: str, context: str | None = None, *args: Any, **kwargs: Any) -> None:
        cls._get_context_logger(context).warning(message, *args, **kwargs)

    @classmethod
    def error(cls, message: str, context: str | None = None, *args: Any, **kwargs: Any) -> None:
        cls._get_context_logger(context).error(message, *args, **kwargs)

    @classmethod
    def critical(cls, message: str, context: str | None = None, *args: Any, **kwargs: Any) -> None:
        cls._get_context_logger(context).critical(message, *args, **kwargs)

    @classmethod
    def exception(cls, message: str, context: str | None = None, *args: Any, **kwargs: Any) -> None:
        cls._get_context_logger(context).exception(message, *args, **kwargs)

    @classmethod
    def shutdown(cls) -> None:
        """Safely flushes and closes all logging handlers."""
        logging.shutdown()
        cls._is_initialized = False
