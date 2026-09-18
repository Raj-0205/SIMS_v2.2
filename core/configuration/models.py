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


class SmtpConfig(BaseModel):
    """
    Immutable SMTP configuration for security notifications.
    Password must be retrieved securely from the environment variable SIMS_SMTP_PASSWORD.
    """

    host: str = Field(
        default="localhost",
        description="SMTP server hostname.",
    )

    port: int = Field(
        default=587,
        description="SMTP server port.",
    )

    username: str = Field(
        default="",
        description="SMTP username.",
    )

    use_tls: bool = Field(
        default=True,
        description="Enable STARTTLS encryption.",
    )

    from_email: str = Field(
        default="noreply@sudharmsims.local",
        description="Sender email address.",
    )

    from_name: str = Field(
        default="Sudharm SIMS Security",
        description="Sender display name.",
    )

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
    )


class SessionConfig(BaseModel):
    """
    Session and authentication security configuration.
    """

    admin_timeout_minutes: int = Field(
        default=60,
        ge=1,
        description="Inactivity timeout for standard Admin sessions in minutes.",
    )

    administrator_timeout_minutes: int = Field(
        default=15,
        ge=1,
        description="Inactivity timeout for privileged Administrator sessions in minutes.",
    )

    otp_ttl_seconds: int = Field(
        default=300,
        ge=30,
        description="OTP challenge expiration time in seconds (default: 5 min).",
    )

    max_otp_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum failed attempts allowed per OTP challenge.",
    )

    max_login_attempts: int = Field(
        default=5,
        ge=1,
        description="Maximum consecutive failed password attempts before account lockout.",
    )

    lockout_duration_minutes: int = Field(
        default=15,
        ge=1,
        description="Account lockout duration in minutes after exceeding max_login_attempts.",
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

    smtp: SmtpConfig = Field(
        default_factory=SmtpConfig,
    )

    session: SessionConfig = Field(
        default_factory=SessionConfig,
    )

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
    )
