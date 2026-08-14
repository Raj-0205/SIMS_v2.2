# core/logger/exceptions.py

from __future__ import annotations

__all__ = [
    "LoggerError",
    "LoggerInitializationError",
]


class LoggerError(Exception):
    """
    Base exception for all logger-related errors.
    
    Every custom exception in the Logger Engine must inherit from
    this class so callers can catch a single root exception.
    """


class LoggerInitializationError(LoggerError):
    """
    Raised when the logging engine fails to initialize.
    
    This could be due to missing write permissions for the log 
    directory, invalid configuration, or failure to acquire a file lock.
    """
