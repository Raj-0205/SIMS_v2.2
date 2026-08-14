from __future__ import annotations

import os
from enum import Enum


class EnvironmentType(str, Enum):
    """
    Represents the supported runtime environments.
    """

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class EnvironmentDetector:
    """
    Determines the current application environment.
    """

    ENV_VAR_NAME = "SIMS_ENV"
    DEFAULT_ENV = EnvironmentType.DEVELOPMENT

    @classmethod
    def get_current(cls) -> EnvironmentType:
        """
        Returns the current runtime environment.

        Environment priority:
            1. SIMS_ENV environment variable
            2. Default environment
        """
        env_value = os.getenv(cls.ENV_VAR_NAME, "").strip().lower()

        if env_value:
            try:
                return EnvironmentType(env_value)
            except ValueError:
                # TODO:
                # Report invalid environment to the Logging Engine
                # once it becomes available.
                pass

        return cls.DEFAULT_ENV

    @classmethod
    def is_development(cls) -> bool:
        """Returns True when running in Development."""
        return cls.get_current() is EnvironmentType.DEVELOPMENT

    @classmethod
    def is_testing(cls) -> bool:
        """Returns True when running in Testing."""
        return cls.get_current() is EnvironmentType.TESTING

    @classmethod
    def is_production(cls) -> bool:
        """Returns True when running in Production."""
        return cls.get_current() is EnvironmentType.PRODUCTION

    @classmethod
    def all(cls) -> tuple[EnvironmentType, ...]:
        """
        Returns all supported environments.

        Useful for validation, UI dropdowns,
        CLI parsing and future configuration tools.
        """
        return tuple(EnvironmentType)
