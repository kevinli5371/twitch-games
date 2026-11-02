"""Validated backend settings; integration credentials stay secret and server-side."""

import base64
from typing import Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
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
    supabase_url: str | None = None
    supabase_secret_key: SecretStr | None = None
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    database_pool_size: int = Field(default=5, ge=1, le=20)

    twitch_client_id: str | None = None
    twitch_client_secret: SecretStr | None = None
    twitch_redirect_uri: str | None = None
    dashboard_url: str | None = None
    token_encryption_key: SecretStr | None = None
    twitch_extension_client_id: str | None = None
    twitch_extension_secret: SecretStr | None = None
    twitch_extension_owner_id: str | None = None
    test_twitch_base_url: str | None = None

    @field_validator(
        "twitch_client_id",
        "twitch_client_secret",
        "twitch_extension_client_id",
        "twitch_extension_secret",
        "twitch_extension_owner_id",
        "token_encryption_key",
        "supabase_secret_key",
        mode="before",
    )
    @classmethod
    def unconfigured_placeholders(cls, value):
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw, str) and (raw.strip() in {"", "..."} or raw.startswith("YOUR_")):
            return None
        return value

    @property
    def oauth_configured(self) -> bool:
        return all(
            (
                self.twitch_client_id,
                self.twitch_client_secret,
                self.twitch_redirect_uri,
                self.token_encryption_key,
            )
        )

    @property
    def extension_configured(self) -> bool:
        return bool(self.twitch_extension_client_id and self.twitch_extension_secret)

    @model_validator(mode="after")
    def validate_twitch(self) -> "Settings":
        if self.test_twitch_base_url:
            parsed = urlsplit(self.test_twitch_base_url)
            if (
                self.environment != "test"
                or parsed.hostname not in {"127.0.0.1", "localhost"}
                or parsed.scheme != "http"
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise ValueError("Twitch test provider is restricted to test-mode loopback HTTP")
        for value in (self.twitch_redirect_uri, self.dashboard_url):
            if value:
                parsed = urlsplit(value)
                if (
                    not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.fragment
                    or parsed.scheme not in {"http", "https"}
                    or (
                        parsed.scheme != "https"
                        and (
                            self.environment == "production"
                            or parsed.hostname not in {"localhost", "127.0.0.1"}
                        )
                    )
                ):
                    raise ValueError("Auth URLs require HTTPS except local loopback development")
        if self.token_encryption_key:
            try:
                Fernet(self.token_encryption_key.get_secret_value().encode())
            except (ValueError, TypeError):
                raise ValueError("Token encryption key must be a valid Fernet key") from None
        if self.twitch_extension_secret:
            try:
                key = base64.b64decode(
                    self.twitch_extension_secret.get_secret_value(), validate=True
                )
                if len(key) < 32:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError(
                    "Extension secret must be base64 with at least 32 decoded bytes"
                ) from None
        if self.twitch_extension_owner_id and not self.twitch_extension_owner_id.isdecimal():
            raise ValueError("Extension owner ID must be a numeric Twitch ID")
        return self

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, value):
        if value is None or not value.strip():
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".supabase.co")
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.port not in {None, 443}
        ):
            raise ValueError("Supabase URL must be an HTTPS project origin")
        return value.rstrip("/")

    @field_validator("supabase_secret_key")
    @classmethod
    def reject_public_api_key(cls, value):
        if value and value.get_secret_value().startswith("sb_publishable_"):
            raise ValueError("Supabase HTTP backend requires a server secret key")
        return value

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
