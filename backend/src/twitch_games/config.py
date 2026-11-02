"""Non-secret foundation settings; later steps add integration configuration."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        return self
