import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from twitch_games.application import create_app
from twitch_games.config import Settings


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.com",
        "https://example.com/path",
        "https://example.com?x=1",
        "https://user:password@example.com",
        "https://example.com#fragment",
        "javascript:alert(1)",
        "https://invalid host",
        "https://example.com:bad-port",
    ],
)
def test_invalid_browser_origins_are_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(cors_origins=[origin])


@pytest.mark.parametrize(
    "overrides",
    [
        {"environment": "invalid"},
        {
            "environment": "production",
            "docs_enabled": True,
            "cors_origins": ["https://example.com"],
        },
        {"environment": "production", "docs_enabled": False},
        {
            "environment": "production",
            "docs_enabled": False,
            "cors_origins": ["http://example.com"],
        },
    ],
)
def test_invalid_environment_config_fails_clearly(overrides):
    with pytest.raises(ValidationError):
        Settings(**overrides)


def test_environment_settings_and_origin_normalization(monkeypatch):
    monkeypatch.setenv("TWITCH_GAMES_ENVIRONMENT", "test")
    monkeypatch.setenv("TWITCH_GAMES_CORS_ORIGINS", '["http://localhost:5173/"]')
    settings = Settings()
    assert settings.environment == "test"
    assert settings.cors_origins == ["http://localhost:5173"]


def test_bad_json_configuration_blocks_application_start(monkeypatch):
    monkeypatch.setenv("TWITCH_GAMES_CORS_ORIGINS", "not-json")
    with pytest.raises(SettingsError):
        create_app()


def test_explicit_dotenv_load_and_no_input_values_in_validation_error(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("TWITCH_GAMES_ENVIRONMENT=test\n", encoding="utf-8")
    assert Settings().environment == "test"
    with pytest.raises(ValidationError) as caught:
        Settings(environment="private-invalid-value")
    assert "private-invalid-value" not in str(caught.value)
