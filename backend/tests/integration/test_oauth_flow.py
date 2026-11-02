import base64
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from support.twitch_fixture import twitch_fixture

from twitch_games.application import create_app
from twitch_games.auth import digest
from twitch_games.config import Settings
from twitch_games.store import one, run

pytestmark = pytest.mark.integration


def test_oauth_csrf_replay_encryption_and_revocation(database):
    with twitch_fixture() as (url, fixture):
        settings = Settings(
            environment="test",
            database_url=database.engine.url.render_as_string(hide_password=False),
            twitch_client_id="fixture-app",
            twitch_client_secret="fixture-secret",
            twitch_redirect_uri="http://localhost:8000/api/v1/auth/twitch/callback",
            token_encryption_key=Fernet.generate_key().decode(),
            test_twitch_base_url=url,
            twitch_extension_client_id="fixture-extension",
            twitch_extension_secret=base64.b64encode(
                b"integration-only-extension-key-32bytes!"
            ).decode(),
        )
        try:
            with TestClient(create_app(settings)) as client:
                start = client.get("/api/v1/auth/twitch", follow_redirects=False)
                assert start.status_code == 302
                state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
                assert (
                    client.get("/api/v1/auth/twitch/callback?state=wrong&code=90001").status_code
                    == 401
                )
                login = client.get(
                    "/api/v1/auth/twitch/callback", params={"state": state, "code": "90001"}
                )
                assert login.status_code == 200
                session = client.cookies["twitch_games_session"]
                with database.transaction() as c:
                    stored = one(
                        c,
                        "SELECT * FROM twitch_games.dashboard_sessions WHERE digest=:d",
                        d=digest(session),
                    )
                    assert stored
                    authorization = one(
                        c, "SELECT * FROM twitch_games.oauth_authorizations WHERE user_id='90001'"
                    )
                    assert authorization["encrypted_access_token"] != "token-90001"
                    assert authorization["encrypted_refresh_token"]
                    assert session not in str(stored)
                assert client.post("/api/v1/auth/logout").status_code == 403
                csrf = client.get("/api/v1/auth/session").json()["csrf_token"]
                client.cookies.set("twitch_games_oauth_state", state)
                replay = client.get(
                    "/api/v1/auth/twitch/callback", params={"state": state, "code": "90001"}
                )
                assert replay.status_code == 401
                fixture["revoked"].add("token-90001")
                with database.transaction() as c:
                    run(
                        c,
                        "UPDATE twitch_games.oauth_authorizations SET validated_at='epoch' WHERE "
                        "user_id='90001'",
                    )
                assert client.get("/api/v1/auth/session").status_code == 401
                with database.transaction() as c:
                    assert (
                        one(
                            c,
                            "SELECT digest FROM twitch_games.dashboard_sessions WHERE digest=:d",
                            d=digest(session),
                        )
                        is None
                    )
                assert csrf
        finally:
            with database.transaction() as c:
                run(c, "DELETE FROM twitch_games.dashboard_sessions WHERE user_id='90001'")
                run(c, "DELETE FROM twitch_games.oauth_authorizations WHERE user_id='90001'")
                run(c, "DELETE FROM twitch_games.channels WHERE id='90001'")
                run(c, "DELETE FROM twitch_games.twitch_users WHERE id='90001'")
                run(c, "DELETE FROM twitch_games.oauth_states")
