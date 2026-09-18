from __future__ import annotations

from typing import Final

from pydantic import ValidationError

from core.configuration.environment import EnvironmentDetector
from core.configuration.exceptions import (
    ConfigurationValidationError,
)
from core.configuration.loader import ConfigurationLoader
from core.configuration.models import (
    ApplicationConfig,
    ConfigurationRoot,
    DatabaseConfig,
    SessionConfig,
    SmtpConfig,
)

__all__ = ["ConfigService"]


class ConfigService:
    """
    Central Configuration Engine.

    Responsible for loading, validating and exposing the application's
    configuration through a singleton interface.
    """

    _loader: Final[ConfigurationLoader] = ConfigurationLoader()
    _instance: ConfigurationRoot | None = None

    @classmethod
    def initialize(cls, force_reload: bool = False) -> None:
        """
        Load configuration into memory.

        Args:
            force_reload:
                Reload configuration even if already initialized.

        Raises:
            ConfigurationValidationError
        """
        if cls._instance is not None and not force_reload:
            return

        environment = EnvironmentDetector.get_current().value

        try:
            raw_application = cls._loader.load(
                "app",
                environment,
            )

            raw_database = cls._loader.load(
                "database",
                environment,
            )

            application = ApplicationConfig(
                **raw_application.get("application", {})
            )

            database = DatabaseConfig(
                **raw_database.get("database", {})
            )

            smtp = SmtpConfig(
                **raw_application.get("smtp", {})
            )

            session = SessionConfig(
                **raw_application.get("session", {})
            )

            cls._instance = ConfigurationRoot(
                application=application,
                database=database,
                smtp=smtp,
                session=session,
            )

        except ValidationError as exc:
            raise ConfigurationValidationError(
                "Configuration validation failed."
            ) from exc

    @classmethod
    def reload(cls) -> None:
        """
        Force reload all configuration files.
        """
        cls.initialize(force_reload=True)

    @classmethod
    def is_loaded(cls) -> bool:
        """
        Returns True if configuration has already been initialized.
        """
        return cls._instance is not None

    @classmethod
    def _root(cls) -> ConfigurationRoot:
        """
        Return the root configuration object.
        """
        if cls._instance is None:
            cls.initialize()

        if cls._instance is None:
            raise ConfigurationValidationError(
                "Configuration service failed to initialize."
            )

        return cls._instance

    @classmethod
    def app(cls) -> ApplicationConfig:
        """
        Return application configuration.
        """
        return cls._root().application

    @classmethod
    def database(cls) -> DatabaseConfig:
        """
        Return database configuration.
        """
        return cls._root().database

    @classmethod
    def smtp(cls) -> SmtpConfig:
        """
        Return SMTP notification configuration.
        """
        return cls._root().smtp

    @classmethod
    def session(cls) -> SessionConfig:
        """
        Return session and authentication security configuration.
        """
        return cls._root().session
