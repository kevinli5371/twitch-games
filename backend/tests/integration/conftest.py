import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from twitch_games.config import Settings
from twitch_games.database import Database

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

# Capture before the foundation's per-test environment isolation runs.
TEST_DATABASE_URL = os.environ.get("TWITCH_GAMES_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def database():
    if TEST_DATABASE_URL is None:
        pytest.skip("Run scripts/postgres_checks.py to provision isolated live PostgreSQL")
    url = make_url(TEST_DATABASE_URL)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not url.database.endswith("_test"):
        pytest.fail("Integration tests refuse a non-loopback/non-test database")
    db = Database(Settings(database_url=TEST_DATABASE_URL, _env_file=None))
    assert db.status() == "ok", "Isolated test database must be migrated before tests"
    yield db
    db.close()


@pytest.fixture
def connection(database):
    with database.engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
