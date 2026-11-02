import pytest
from pydantic import SecretStr, ValidationError

from twitch_games.config import Settings
from twitch_games.database import Database, create_database_engine


@pytest.mark.parametrize(
    "url",
    [
        "not-a-uri",
        "sqlite:///test.db",
        "https://project.supabase.co",
        "postgresql:///postgres",
        "postgresql://localhost/postgres",
        "postgresql://user:secret@localhost:99999/postgres",
        "postgresql://user:secret@remote.example.com/postgres",
        "postgresql://user:secret@remote.example.com/postgres?sslmode=disable",
        "postgresql://user:secret@localhost/postgres?options=-csearch_path=public",
        "postgresql://user:secret@localhost/postgres?host=remote.example.com",
    ],
)
def test_invalid_or_unencrypted_remote_connections_are_rejected(url):
    with pytest.raises(ValidationError) as caught:
        Settings(database_url=url)
    assert "user:secret" not in str(caught.value)


def test_database_url_is_secret_and_driver_is_normalized():
    settings = Settings(
        database_url="postgres://user:database-password-sentinel@localhost/postgres"
    )
    assert isinstance(settings.database_url, SecretStr)
    assert "database-password-sentinel" not in settings.model_dump_json()
    engine = create_database_engine(settings)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.hide_parameters is True
        assert "secret" not in repr(engine)
    finally:
        engine.dispose()


def test_database_is_optional_but_pool_limits_are_bounded():
    assert Settings().database_url is None
    with pytest.raises(ValueError):
        Database(Settings())
    with pytest.raises(ValidationError):
        Settings(database_pool_size=0)
    with pytest.raises(ValidationError):
        Settings(database_connect_timeout_seconds=0)


def test_remote_tls_and_encoded_password_are_preserved():
    settings = Settings(
        database_url="postgresql://user:p%40ss%3Aword@db.example.com/postgres?sslmode=require"
    )
    engine = create_database_engine(settings)
    try:
        assert engine.url.password == "p@ss:word"
        assert engine.url.query["sslmode"] == "require"
    finally:
        engine.dispose()
