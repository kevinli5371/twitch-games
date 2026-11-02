"""Validated backend settings; integration credentials stay secret and server-side."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TWITCH_GAMES_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        hide_input_in_errors=True,
    )

    environment: Literal["local", "test", "production"] = "local"
    docs_enabled: bool = True
    cors_origins: list[str] = []
    database_url: SecretStr | None = None
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    database_pool_size: int = Field(default=5, ge=1, le=20)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        try:
            url = make_url(value.get_secret_value())
            if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
                raise ValueError
            if not url.host or not url.database or not url.username:
                raise ValueError
            if url.port is not None and not 1 <= url.port <= 65535:
                raise ValueError
            if any(key in url.query for key in {"options", "host", "hostaddr", "port"}):
                raise ValueError
        except (ValueError, TypeError, ArgumentError):
            raise ValueError(
                "Database URL must be a PostgreSQL URI with user, host and database"
            ) from None
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        validated: list[str] = []
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or "*" in origin
                or any(char.isspace() for char in origin)
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS entries must be exact HTTP(S) origins without paths")
            try:
                _ = parsed.port
            except ValueError as exc:
                raise ValueError("CORS origin contains an invalid port") from exc
            normalized = origin.rstrip("/")
            if normalized not in validated:
                validated.append(normalized)
        return validated

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production":
            if self.docs_enabled:
                raise ValueError("Production requires TWITCH_GAMES_DOCS_ENABLED=false")
            if not self.cors_origins or any(
                urlsplit(origin).scheme != "https" for origin in self.cors_origins
            ):
                raise ValueError("Production requires explicit HTTPS CORS origins")
        if self.database_url is not None:
            url = make_url(self.database_url.get_secret_value())
            sslmode = url.query.get("sslmode")
            loopback = url.host in {"localhost", "127.0.0.1", "::1"}
            if (not loopback or self.environment == "production") and sslmode not in {
                "require",
                "verify-ca",
                "verify-full",
            }:
                raise ValueError("Remote/production database connections require explicit TLS")
        return self
