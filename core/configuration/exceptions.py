from __future__ import annotations

__all__ = [
    "ConfigurationError",
    "ConfigurationNotFoundError",
    "ConfigurationParseError",
    "ConfigurationValidationError",
]


class ConfigurationError(Exception):
    """
    Base exception for all configuration-related errors.

    Every custom exception in the Configuration Engine must inherit from
    this class so callers can catch a single root exception when needed.
    """


class ConfigurationNotFoundError(ConfigurationError):
    """
    Raised when a required configuration file or directory
    cannot be located.
    """


class ConfigurationParseError(ConfigurationError):
    """
    Raised when a configuration file contains invalid TOML syntax
    or cannot be parsed successfully.
    """


class ConfigurationValidationError(ConfigurationError):
    """
    Raised when parsed configuration data fails schema or type
    validation.

    This exception is intended to wrap validation errors coming
    from Pydantic while hiding implementation details from the
    Bootstrapper.
    """
