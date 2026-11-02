"""Compatibility and retained planning contracts from the merged dashboard foundation."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from twitch_games.config import Settings
from twitch_games.planning_contracts import PublicQuestion


def test_original_app_entrypoint_uses_the_implemented_factory():
    from twitch_games.app import create_app
    from twitch_games.application import create_app as implemented_factory

    assert create_app is implemented_factory
    with TestClient(create_app(Settings(environment="test"))) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert "/api/v1/auth/me" in client.get("/openapi.json").json()["paths"]


def test_original_entrypoint_remains_closed_without_verified_credentials():
    from twitch_games.app import create_app

    with TestClient(create_app(Settings(environment="test"))) as client:
        path = "/api/v1/channels/90001/game-state"
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer untrusted"}).status_code == 503


def test_planning_public_question_rejects_hidden_answer():
    with pytest.raises(ValidationError):
        PublicQuestion(
            id="00000000-0000-0000-0000-000000000001",
            mode="niche",
            prompt="Prompt",
            position=1,
            total=3,
            canonical_answer="secret",
        )
