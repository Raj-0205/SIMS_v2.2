from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final

from core.configuration.exceptions import (
    ConfigurationNotFoundError,
    ConfigurationParseError,
)

__all__ = ["ConfigurationLoader"]


class ConfigurationLoader:
    """
    Reads and merges TOML configuration files.

    Loading strategy:

        config/default/<name>.toml          (mandatory)
        config/<environment>/<name>.toml    (optional)

    The environment configuration overrides the default configuration
    using recursive deep merging.
    """

    CONFIG_DIRECTORY: Final[str] = "config"

    def __init__(self, project_root: Path | None = None) -> None:
        """
        Initialize the configuration loader.

        Args:
            project_root:
                Optional explicit project root. If omitted, the loader
                automatically resolves the project root.
        """
        if project_root is None:
            self._project_root = Path(__file__).resolve().parent.parent.parent
        else:
            self._project_root = project_root.resolve()

        self._config_directory = (
            self._project_root / self.CONFIG_DIRECTORY
        )

    def load(
        self,
        config_name: str,
        environment: str,
    ) -> dict[str, Any]:
        """
        Load and merge configuration.

        Args:
            config_name:
                Configuration filename without extension.

            environment:
                Runtime environment
                (development/testing/production).

        Returns:
            Fully merged configuration dictionary.

        Raises:
            ConfigurationNotFoundError
            ConfigurationParseError
        """
        config_name = config_name.strip()

        if not config_name:
            raise ConfigurationNotFoundError(
                "Configuration name cannot be empty."
            )

        environment = environment.strip().lower()

        default_file = (
            self._config_directory
            / "default"
            / f"{config_name}.toml"
        )

        environment_file = (
            self._config_directory
            / environment
            / f"{config_name}.toml"
        )

        if not default_file.exists():
            raise ConfigurationNotFoundError(
                f"Required configuration not found: {default_file}"
            )

        configuration = self._read_toml(default_file)

        if environment_file.exists():
            override = self._read_toml(environment_file)
            configuration = self._deep_merge(
                configuration,
                override,
            )

        return configuration

    def _read_toml(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        """
        Read and parse a TOML file.
        """
        try:
            with file_path.open("rb") as file:
                return tomllib.load(file)

        except tomllib.TOMLDecodeError as exc:
            raise ConfigurationParseError(
                f"Invalid TOML syntax in '{file_path}'."
            ) from exc

        except OSError as exc:
            raise ConfigurationNotFoundError(
                f"Unable to read configuration file '{file_path}'."
            ) from exc

    def _deep_merge(
        self,
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Recursively merge two dictionaries.

        Values from 'override' always take precedence.
        """
        merged = base.copy()

        for key, value in override.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = self._deep_merge(
                    merged[key],
                    value,
                )
            else:
                merged[key] = value

        return merged
