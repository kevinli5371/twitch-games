"""Actual PostgreSQL plus HTTP OAuth provider: grants, refresh, and session boundaries."""

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from support.twitch_fixture import twitch_fixture

from twitch_games.application import create_app
from twitch_games.auth import digest
from twitch_games.config import Settings
from twitch_games.store import one, run

pytestmark = pytest.mark.integration


@pytest.fixture
def workspace(database):
    owner = str(uuid4().int)[:12]
    moderator = owner + "1"
    with twitch_fixture() as (url, provider):
        settings = Settings(
            environment="test",
            database_url=database.engine.url.render_as_string(hide_password=False),
            twitch_client_id="fixture-app",
            twitch_client_secret="fixture-secret",
            twitch_redirect_uri="http://localhost:8000/api/v1/auth/twitch/callback",
            dashboard_url="http://localhost:4173",
            cors_origins=["http://localhost:4173"],
            token_encryption_key=Fernet.generate_key().decode(),
            test_twitch_base_url=url,
            twitch_extension_client_id="fixture-extension",
            twitch_extension_secret=base64.b64encode(
                b"integration-only-extension-key-32bytes!"
            ).decode(),
        )
        app = create_app(settings)
        try:
            with TestClient(app) as client:
                yield client, app, owner, moderator, provider
        finally:
            with database.transaction() as c:
                for table in (
                    "moderator_grants",
                    "state_notifications",
                    "command_receipts",
                    "answer_aliases",
                    "score_entries",
                    "submissions",
                    "rounds",
                    "game_sessions",
                    "question_sources",
                    "question_candidates",
                    "transcript_segments",
                    "transcript_batches",
                    "streams",
                ):
                    run(
                        c,
                        f"DELETE FROM twitch_games.{table} WHERE channel_id LIKE :prefix",
                        prefix=owner + "%",
                    )
                run(
                    c,
                    "DELETE FROM twitch_games.dashboard_sessions WHERE user_id LIKE :prefix",
                    prefix=owner + "%",
                )
                run(
                    c,
                    "DELETE FROM twitch_games.oauth_authorizations WHERE user_id LIKE :prefix",
                    prefix=owner + "%",
                )
                run(
                    c, "DELETE FROM twitch_games.channels WHERE id LIKE :prefix", prefix=owner + "%"
                )
                run(
                    c,
                    "DELETE FROM twitch_games.twitch_users WHERE id LIKE :prefix",
                    prefix=owner + "%",
                )


def sign_in(client, user):
    client.cookies.clear()  # Separate browser accounts, not an account switch in one browser.
    start = client.get(
        "/api/v1/auth/twitch?return_to=https://untrusted.example", follow_redirects=False
    )
    assert start.status_code == 302
    assert (
        "HttpOnly" in start.headers["set-cookie"] and "SameSite=lax" in start.headers["set-cookie"]
    )
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    response = client.get(
        "/api/v1/auth/twitch/callback",
        params={"state": state, "code": user},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "http://localhost:4173"
    cookie = client.cookies["twitch_games_session"]
    headers = {"Cookie": "twitch_games_session=" + cookie}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    headers["X-CSRF-Token"] = me.json()["csrf_token"]
    return headers, cookie


def prepare(client, owner, headers):
    connected = client.post(f"/api/v1/channels/{owner}/stream", headers=headers)
    assert connected.status_code == 200, connected.text
    stream = connected.json()["stream_id"]
    response = client.post(
        f"/api/v1/streams/{stream}/transcript-batches",
        headers=headers,
        json={
            "batch_id": str(uuid4()),
            "source": "twitch_player_captions",
            "segments": [
                {
                    "sequence": 0,
                    "text": "I cannot believe we won this tournament with a spoon.",
                    "observed_at": datetime.now(UTC).isoformat(),
                }
            ],
        },
    )
    assert response.status_code == 202, response.text
    return stream


def test_explicit_permission_matrix_and_immediate_revocation(workspace):
    client, app, owner, moderator, provider = workspace
    owner_headers, _ = sign_in(client, owner)
    mod_headers, _ = sign_in(client, moderator)
    stream = prepare(client, owner, owner_headers)
    me = client.get("/api/v1/auth/me", headers=owner_headers).json()
    assert me["user"]["user_id"] == owner and me["user"]["login"] == "user" + owner
    assert me["user"]["avatar_url"] and me["owned_channel"]["channel_id"] == owner
    assert me["selected_workspace"]["role"] == "owner"
    assert client.get(f"/api/v1/dashboard/channels/{owner}", headers=mod_headers).status_code == 403
    grant = f"/api/v1/channels/{owner}/moderators"
    denied = client.put(
        grant,
        headers=mod_headers,
        json={"login": "user" + moderator, "permissions": ["live_control"]},
    )
    assert denied.status_code == 403
    granted = client.put(
        grant,
        headers=owner_headers,
        json={"login": "user" + moderator, "permissions": ["live_control"]},
    )
    assert granted.status_code == 200, granted.text
    selected = client.get(
        "/api/v1/auth/me", headers=mod_headers, params={"channel_id": owner}
    ).json()
    assert selected["selected_workspace"] == {
        "channel_id": owner,
        "role": "moderator",
        "permissions": ["live_control"],
    }
    assert {w["channel_id"] for w in selected["workspaces"]} == {owner, moderator}
    assert (
        next(w for w in selected["workspaces"] if w["channel_id"] == owner)["login"]
        == "user" + owner
    )
    snapshot = client.get(f"/api/v1/dashboard/channels/{owner}", headers=mod_headers)
    assert snapshot.status_code == 200 and snapshot.json()["candidates"] == []
    assert client.get(f"/api/v1/streams/{stream}/questions", headers=mod_headers).status_code == 403
    assert client.get(f"/api/v1/channels/{owner}/aliases", headers=mod_headers).status_code == 403
    assert client.post(f"/api/v1/channels/{owner}/stream", headers=mod_headers).status_code == 403
    started = client.post(
        f"/api/v1/channels/{owner}/games",
        headers=mod_headers,
        json={"request_id": str(uuid4()), "mode": "quote", "policy_id": "quote_v1"},
    )
    assert started.status_code == 201, started.text
    assert client.get(grant, headers=mod_headers).status_code == 403
    assert client.delete(grant + "/" + moderator, headers=mod_headers).status_code == 403
    client.put(
        grant,
        headers=owner_headers,
        json={"login": "user" + moderator, "permissions": ["question_review"]},
    )
    assert client.get(f"/api/v1/streams/{stream}/questions", headers=mod_headers).json()[0][
        "canonical_answer"
    ]
    assert client.get(f"/api/v1/dashboard/channels/{owner}", headers=mod_headers).json()[
        "candidates"
    ]
    denied = client.post(
        f"/api/v1/games/{started.json()['game_id']}/rounds",
        headers=mod_headers,
        json={"request_id": str(uuid4()), "expected_version": started.json()["version"]},
    )
    assert denied.status_code == 403
    client.put(
        grant,
        headers=owner_headers,
        json={"login": "user" + moderator, "permissions": ["settings"]},
    )
    assert client.post(f"/api/v1/channels/{owner}/stream", headers=mod_headers).status_code == 200
    assert (
        client.get(f"/api/v1/dashboard/channels/{owner}", headers=mod_headers).json()["candidates"]
        == []
    )
    assert client.get(f"/api/v1/streams/{stream}/questions", headers=mod_headers).status_code == 403
    assert client.delete(grant + "/" + moderator, headers=owner_headers).status_code == 204
    assert client.get(f"/api/v1/dashboard/channels/{owner}", headers=mod_headers).status_code == 403
    assert (
        client.get("/api/v1/auth/me", headers=mod_headers, params={"channel_id": owner}).status_code
        == 403
    )
    assert client.get("/api/v1/auth/me", headers=mod_headers).status_code == 200


def test_refresh_is_serialized_rotated_and_revocation_ends_all_sessions(workspace, database):
    client, app, owner, moderator, provider = workspace
    first, first_cookie = sign_in(client, owner)
    second, second_cookie = sign_in(client, owner)
    with database.transaction() as c:
        before = one(
            c, "SELECT * FROM twitch_games.oauth_authorizations WHERE user_id=:id", id=owner
        )
        run(
            c,
            "UPDATE twitch_games.oauth_authorizations SET "
            "access_expires_at=now()-interval '1 second' "
            "WHERE user_id=:id",
            id=owner,
        )
    provider["expired"].add("token-" + owner)
    with ThreadPoolExecutor(max_workers=5) as pool:
        identities = list(
            pool.map(lambda _: app.state.auth.validate_session(first_cookie), range(5))
        )
    assert all(identity.user_id == owner for identity in identities)
    assert provider["refresh_calls"] == 1
    with database.transaction() as c:
        after = one(
            c, "SELECT * FROM twitch_games.oauth_authorizations WHERE user_id=:id", id=owner
        )
        assert after["encrypted_refresh_token"] != before["encrypted_refresh_token"]
        assert "token-" not in after["encrypted_access_token"]
        # Session expiry is separate from the access-token lifetime.
        record = one(
            c,
            "SELECT expires_at FROM twitch_games.dashboard_sessions WHERE digest=:d",
            d=digest(first_cookie),
        )
        assert record["expires_at"] > after["access_expires_at"]
    assert client.get("/api/v1/auth/me", headers=second).status_code == 200
    provider["revoked"].add("token-" + owner)
    with database.transaction() as c:
        run(
            c,
            "UPDATE twitch_games.oauth_authorizations SET validated_at='epoch' WHERE user_id=:id",
            id=owner,
        )
    assert client.get("/api/v1/auth/me", headers=first).status_code == 401
    assert client.get("/api/v1/auth/me", headers=second).status_code == 401
    with database.transaction() as c:
        assert (
            one(
                c,
                "SELECT count(*) AS n FROM twitch_games.dashboard_sessions WHERE user_id=:id",
                id=owner,
            )["n"]
            == 0
        )


def test_expired_session_csrf_invalid_state_and_denial(workspace, database):
    client, app, owner, moderator, provider = workspace
    headers, cookie = sign_in(client, owner)
    csrf_missing = {"Cookie": headers["Cookie"]}
    assert client.post("/api/v1/auth/logout", headers=csrf_missing).status_code == 403
    with database.transaction() as c:
        run(
            c,
            "UPDATE twitch_games.dashboard_sessions SET expires_at=now()-interval '1 second' "
            "WHERE digest=:d",
            d=digest(cookie),
        )
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    start = client.get("/api/v1/auth/twitch", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    with database.transaction() as c:
        run(
            c,
            "UPDATE twitch_games.oauth_states SET expires_at=now()-interval '1 second' "
            "WHERE digest=:d",
            d=digest(state),
        )
    assert (
        client.get(
            "/api/v1/auth/twitch/callback", params={"state": state, "code": owner}
        ).status_code
        == 401
    )
    start = client.get("/api/v1/auth/twitch", follow_redirects=False)
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    denied = client.get(
        "/api/v1/auth/twitch/callback", params={"state": state, "error": "access_denied"}
    )
    assert denied.status_code == 401 and denied.json()["error"]["code"] == "consent_denied"
