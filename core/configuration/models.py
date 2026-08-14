from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.configuration.environment import EnvironmentType


class ApplicationConfig(BaseModel):
    """
    Immutable application configuration loaded from app.toml.
    """

    name: str = Field(
        default="Sudharm SIMS",
        description="Display name of the application.",
    )

    version: str = Field(
        default="2.2.0",
        description="Current application version.",
    )

    environment: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Current runtime environment.",
    )

    debug: bool = Field(
        default=False,
        description="Enable or disable debug mode.",
    )

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
    )


class DatabaseConfig(BaseModel):
    """
    Immutable SQLite database configuration loaded from database.toml.
    """

    engine: Literal["sqlite"] = Field(
        default="sqlite",
        description="Database engine.",
    )

    path: str = Field(
        default="database/sims.db",
        description="SQLite database file path.",
    )

    busy_timeout: int = Field(
        default=5000,
        ge=0,
        description="SQLite busy timeout in milliseconds.",
    )

    journal_mode: Literal[
        "DELETE",
        "TRUNCATE",
        "PERSIST",
        "MEMORY",
        "WAL",
        "OFF",
    ] = Field(
        default="WAL",
        description="SQLite journal mode.",
    )

    foreign_keys: bool = Field(
        default=True,
        description="Enable foreign key constraints.",
    )

    cache_size: int = Field(
        default=-20000,
        description="SQLite cache size. Negative values represent KiB.",
    )

    synchronous: Literal[
        "OFF",
        "NORMAL",
        "FULL",
        "EXTRA",
    ] = Field(
        default="NORMAL",
        description="SQLite synchronous mode.",
    )

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
    )


class ConfigurationRoot(BaseModel):
    """
    Root configuration object.

    Aggregates every configuration model used by the application.
    This becomes the single source of truth after startup.
    """

    application: ApplicationConfig = Field(
        default_factory=ApplicationConfig,
    )

    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
    )

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
    )
