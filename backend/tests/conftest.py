import os

import pytest


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """No developer .env or ambient app settings may affect a test."""
    for key in os.environ:
        if key.upper().startswith("TWITCH_GAMES_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
