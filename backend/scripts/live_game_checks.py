"""Real Uvicorn + real PostgreSQL gameplay; Twitch itself is a loopback HTTP fixture.

Only accepts the disposable loopback *_test DB supplied by postgres_checks.py.
Exercises the actual 30-second timer, OAuth cookies, and a process restart.
"""

import base64
import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx2 as httpx
import jwt
from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url
from starlette.routing import compile_path
from support.twitch_fixture import twitch_fixture

from twitch_games.config import Settings
from twitch_games.database import Database
from twitch_games.store import run

ROOT = Path(__file__).resolve().parents[1]
KEY = b"integration-only-extension-key-32bytes!"


class EndpointCoverage:
    """Fail the live check if any documented operation lacks a successful response."""

    def __init__(self):
        self.routes = []
        self.seen = {}

    def configure(self, schema):
        for path, operations in schema["paths"].items():
            for method in operations:
                if method.lower() in {"get", "post", "put", "delete", "patch", "head", "options"}:
                    key = (method.upper(), path)
                    self.routes.append((key, compile_path(path)[0]))
                    self.seen[key] = set()

    def observe(self, response):
        for key, pattern in self.routes:
            if response.request.method == key[0] and pattern.fullmatch(response.request.url.path):
                self.seen[key].add(response.status_code)

    def verify(self):
        missing = [
            f"{method} {path}"
            for (method, path), statuses in self.seen.items()
            if not any(200 <= status < 400 for status in statuses)
        ]
        assert self.routes, "Runtime OpenAPI must declare the expected API operations"
        assert not missing, "Missing successful real HTTP endpoint cases: " + ", ".join(missing)
        report = {
            "scope": "Real local Uvicorn/PostgreSQL; Twitch HTTP fixture; no frontend/device E2E",
            "operation_count": len(self.routes),
            "operations": [
                {"method": method, "path": path, "statuses": sorted(statuses)}
                for (method, path), statuses in sorted(self.seen.items())
            ],
        }
        target = ROOT / ".cache/endpoint-coverage.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n")
        print(
            f"All {len(self.routes)} documented API operations had successful real HTTP cases.",
            flush=True,
        )


def main():
    dsn = os.environ.get("TWITCH_GAMES_TEST_DATABASE_URL")
    if not dsn:
        raise SystemExit("Run this via scripts/postgres_checks.py")
    parsed = make_url(dsn)
    if parsed.host not in {"localhost", "127.0.0.1"} or not parsed.database.endswith("_test"):
        raise SystemExit("Refusing a non-loopback/non-test database")
    database = Database(Settings(database_url=dsn, _env_file=None))
    channel = str(uuid4().int)[:15]
    process = None
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with (
        TemporaryDirectory(prefix="twitch-games-live-") as cwd,
        twitch_fixture() as (provider_url, fixture),
    ):
        environment = {k: v for k, v in os.environ.items() if not k.startswith("TWITCH_GAMES_")}
        values = {
            "ENVIRONMENT": "test",
            "DOCS_ENABLED": "true",
            "DATABASE_URL": dsn,
            "TWITCH_CLIENT_ID": "fixture-app",
            "TWITCH_CLIENT_SECRET": "fixture-secret",
            "TWITCH_REDIRECT_URI": base + "/api/v1/auth/twitch/callback",
            "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "TWITCH_EXTENSION_CLIENT_ID": "fixture-extension",
            "TWITCH_EXTENSION_SECRET": base64.b64encode(KEY).decode(),
            "TWITCH_EXTENSION_OWNER_ID": "90001",
            "TEST_TWITCH_BASE_URL": provider_url,
        }
        environment.update({"TWITCH_GAMES_" + k: v for k, v in values.items()})

        def start_server():
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "twitch_games.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
                cwd=cwd,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for _ in range(150):
                if process.poll() is not None:
                    raise RuntimeError("Local API process exited during startup")
                try:
                    response = httpx.get(base + "/health/live", timeout=1)
                    if response.status_code == 200:
                        return process
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            process.terminate()
            process.communicate(timeout=10)
            raise RuntimeError("Local API did not become live")

        def bearer(user=None, role="viewer", other_channel=None):
            token = jwt.encode(
                {
                    "exp": int(time.time()) + 120,
                    "role": role,
                    "channel_id": other_channel or channel,
                    "opaque_user_id": "U" + (user or "opaque"),
                    "user_id": user,
                },
                KEY,
            )
            return {"Authorization": "Bearer " + token}

        def checked(client, method, path, status, **kwargs):
            response = client.request(method, path, **kwargs)
            assert response.status_code == status, (
                method,
                path,
                response.status_code,
                response.text,
            )
            return response.json() if response.content else None

        try:
            process = start_server()
            coverage = EndpointCoverage()
            hooks = {"response": [coverage.observe]}
            with (
                httpx.Client(
                    base_url=base, timeout=10, follow_redirects=False, event_hooks=hooks
                ) as owner,
                httpx.Client(base_url=base, timeout=10, event_hooks=hooks) as viewer,
            ):
                schema = checked(viewer, "GET", "/openapi.json", 200)
                coverage.configure(schema)
                checked(viewer, "GET", "/health/live", 200)
                checked(viewer, "GET", "/health/ready", 200)
                checked(viewer, "GET", f"/api/v1/channels/{channel}/game-state", 401)
                login = owner.get("/api/v1/auth/twitch")
                assert login.status_code == 302
                state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
                checked(
                    owner,
                    "GET",
                    "/api/v1/auth/twitch/callback",
                    200,
                    params={"state": state, "code": channel},
                )
                session = checked(owner, "GET", "/api/v1/auth/session", 200)
                owner.headers["X-CSRF-Token"] = session["csrf_token"]
                stream = checked(owner, "POST", f"/api/v1/channels/{channel}/stream", 200)[
                    "stream_id"
                ]
                batch = {
                    "batch_id": str(uuid4()),
                    "source": "twitch_player_captions",
                    "segments": [
                        {
                            "sequence": 0,
                            "text": "I cannot believe we won this tournament with a spoon.",
                            "observed_at": datetime.now(UTC).isoformat(),
                        }
                    ],
                }
                path = f"/api/v1/streams/{stream}/transcript-batches"
                assert checked(owner, "POST", path, 202, json=batch)["status"] == "received"
                assert checked(owner, "POST", path, 202, json=batch)["status"] == "duplicate"
                moderator = httpx.Client(
                    base_url=base, timeout=10, follow_redirects=False, event_hooks=hooks
                )
                try:
                    mod_user = channel + "3"
                    mod_login = moderator.get("/api/v1/auth/twitch")
                    mod_state = parse_qs(urlsplit(mod_login.headers["location"]).query)["state"][0]
                    checked(
                        moderator,
                        "GET",
                        "/api/v1/auth/twitch/callback",
                        200,
                        params={"state": mod_state, "code": mod_user},
                    )
                    mod_me = checked(moderator, "GET", "/api/v1/auth/me", 200)
                    moderator.headers["X-CSRF-Token"] = mod_me["csrf_token"]
                    checked(moderator, "GET", f"/api/v1/dashboard/channels/{channel}", 403)
                    checked(
                        owner,
                        "PUT",
                        f"/api/v1/channels/{channel}/moderators",
                        200,
                        json={"login": "user" + mod_user, "permissions": ["live_control"]},
                    )
                    grants = checked(owner, "GET", f"/api/v1/channels/{channel}/moderators", 200)
                    assert grants == [
                        {
                            "user_id": mod_user,
                            "login": "user" + mod_user,
                            "display_name": "Viewer" + mod_user,
                            "permissions": ["live_control"],
                        }
                    ]
                    assert (
                        checked(moderator, "GET", f"/api/v1/dashboard/channels/{channel}", 200)[
                            "candidates"
                        ]
                        == []
                    )
                    checked(moderator, "GET", f"/api/v1/streams/{stream}/questions", 403)
                    with database.transaction() as c:
                        run(
                            c,
                            "UPDATE twitch_games.oauth_authorizations SET "
                            "access_expires_at='epoch' "
                            "WHERE user_id=:id",
                            id=mod_user,
                        )
                    fixture["expired"].add("token-" + mod_user)
                    checked(moderator, "GET", "/api/v1/auth/me", 200)
                    assert fixture["refresh_calls"] == 1
                    checked(
                        owner, "DELETE", f"/api/v1/channels/{channel}/moderators/{mod_user}", 204
                    )
                    checked(moderator, "GET", f"/api/v1/dashboard/channels/{channel}", 403)
                    fixture["revoked"].add("token-" + mod_user)
                    with database.transaction() as c:
                        run(
                            c,
                            "UPDATE twitch_games.oauth_authorizations SET validated_at='epoch' "
                            "WHERE user_id=:id",
                            id=mod_user,
                        )
                    checked(moderator, "GET", "/api/v1/auth/me", 401)
                    print(
                        "HTTP moderator grants, privacy and token lifecycle passed.",
                        flush=True,
                    )
                finally:
                    moderator.close()
                question = checked(owner, "GET", f"/api/v1/streams/{stream}/questions", 200)[0]
                canonical = question["canonical_answer"]
                checked(
                    owner,
                    "PUT",
                    f"/api/v1/channels/{channel}/aliases",
                    200,
                    json={"canonical": canonical, "aliases": ["fixture alias"]},
                )
                aliases = checked(owner, "GET", f"/api/v1/channels/{channel}/aliases", 200)
                assert aliases == [
                    {"canonical": canonical.casefold(), "aliases": ["fixture alias"]}
                ]
                started = checked(
                    owner,
                    "POST",
                    f"/api/v1/channels/{channel}/games",
                    201,
                    json={"request_id": str(uuid4()), "mode": "quote", "policy_id": "quote_v1"},
                )
                opened = checked(
                    owner,
                    "POST",
                    f"/api/v1/games/{started['game_id']}/rounds",
                    201,
                    json={"request_id": str(uuid4()), "expected_version": started["version"]},
                )
                round_id = opened["round"]["round_id"]
                deadline = opened["round"]["closes_at"]
                assert "canonical_answer" not in opened["round"]
                first = bearer(channel + "1")
                second = bearer(channel + "2")
                answer = {
                    "request_id": str(uuid4()),
                    "answer": canonical[:-2] + canonical[-1] + canonical[-2],
                }
                receipt = checked(
                    viewer,
                    "POST",
                    f"/api/v1/rounds/{round_id}/answers",
                    202,
                    headers=first,
                    json=answer,
                )
                checked(
                    viewer,
                    "POST",
                    f"/api/v1/rounds/{round_id}/answers",
                    202,
                    headers=second,
                    json={"request_id": str(uuid4()), "answer": "wrong"},
                )
                checked(
                    viewer,
                    "POST",
                    f"/api/v1/rounds/{round_id}/answers",
                    202,
                    headers=second,
                    json={"request_id": str(uuid4()), "answer": "fixture alias"},
                )
                assert (
                    checked(viewer, "GET", f"/api/v1/rounds/{round_id}/me", 200, headers=second)[
                        "result"
                    ]
                    is None
                )
                checked(
                    viewer,
                    "POST",
                    f"/api/v1/rounds/{round_id}/answers",
                    403,
                    headers=bearer(),
                    json=answer,
                )
                checked(
                    viewer,
                    "GET",
                    f"/api/v1/rounds/{round_id}/me",
                    404,
                    headers=bearer(channel + "1", other_channel=str(int(channel) + 1)),
                )
                print(
                    "Real HTTP OAuth, captions, quote selection and private edits passed.",
                    flush=True,
                )
                process.terminate()
                process.communicate(timeout=10)
                process = start_server()
                restored = checked(
                    viewer, "GET", f"/api/v1/channels/{channel}/game-state", 200, headers=first
                )
                assert restored["round"]["closes_at"] == deadline
                assert (
                    checked(viewer, "GET", f"/api/v1/rounds/{round_id}/me", 200, headers=first)[
                        "receipt"
                    ]["submission_id"]
                    == receipt["submission_id"]
                )
                print(
                    "API restart preserved the deadline, sessions and submissions.",
                    flush=True,
                )
                timeout = time.monotonic() + 40
                while time.monotonic() < timeout:
                    results = checked(
                        viewer, "GET", f"/api/v1/channels/{channel}/game-state", 200, headers=first
                    )
                    if results["round"]["phase"] == "results":
                        break
                    assert "canonical_answer" not in results["round"]
                    time.sleep(0.25)
                else:
                    raise AssertionError("The persisted 30-second timer did not close the round")
                assert datetime.now(UTC) >= datetime.fromisoformat(deadline)
                checked(
                    viewer,
                    "POST",
                    f"/api/v1/rounds/{round_id}/answers",
                    409,
                    headers=first,
                    json={"request_id": str(uuid4()), "answer": canonical},
                )
                assert (
                    checked(
                        viewer,
                        "POST",
                        f"/api/v1/rounds/{round_id}/answers",
                        202,
                        headers=first,
                        json=answer,
                    )
                    == receipt
                )
                own = checked(viewer, "GET", f"/api/v1/rounds/{round_id}/me", 200, headers=first)
                assert own["result"]["awarded_points"] == 1
                leaderboard = checked(
                    viewer,
                    "GET",
                    f"/api/v1/games/{started['game_id']}/leaderboard",
                    200,
                    headers=first,
                )
                assert [(e["points"], e["rank"]) for e in leaderboard["entries"]] == [
                    (1, 1),
                    (1, 1),
                ]
                print(
                    "30-second closure, scoring, late rejection and shared ranks passed.",
                    flush=True,
                )
                close_command = {"request_id": str(uuid4()), "expected_version": results["version"]}
                results = checked(
                    owner, "POST", f"/api/v1/rounds/{round_id}/close", 202, json=close_command
                )
                assert results["round"]["phase"] == "results"
                assert (
                    checked(
                        owner, "POST", f"/api/v1/rounds/{round_id}/close", 202, json=close_command
                    )
                    == results
                )
                after_close = checked(
                    viewer,
                    "GET",
                    f"/api/v1/games/{started['game_id']}/leaderboard",
                    200,
                    headers=first,
                )
                assert after_close["entries"] == leaderboard["entries"]
                ended = checked(
                    owner,
                    "POST",
                    f"/api/v1/games/{started['game_id']}/end",
                    200,
                    json={"request_id": str(uuid4()), "expected_version": results["version"]},
                )
                assert ended["status"] == "ended"
                assert checked(
                    viewer,
                    "GET",
                    f"/api/v1/games/{started['game_id']}/leaderboard",
                    200,
                    headers=first,
                )["final"]
                new = checked(
                    owner,
                    "POST",
                    f"/api/v1/channels/{channel}/games",
                    201,
                    json={"request_id": str(uuid4()), "mode": "quote", "policy_id": "quote_v1"},
                )
                assert (
                    checked(
                        viewer,
                        "GET",
                        f"/api/v1/games/{new['game_id']}/leaderboard",
                        200,
                        headers=first,
                    )["entries"]
                    == []
                )
                assert new["version"] > ended["version"]
                assert fixture["messages"]
                for notification in fixture["messages"]:
                    payload = json.loads(notification["body"]["message"])
                    assert set(payload) == {"event", "channel_id", "version"}
                    decoded = jwt.decode(
                        notification["authorization"][7:], KEY, algorithms=["HS256"]
                    )
                    assert decoded["role"] == "external"
                checked(
                    viewer,
                    "POST",
                    f"/api/v1/rounds/{round_id}/answers",
                    413,
                    headers=first,
                    content=b"x" * 524289,
                )
                print(
                    "Final standings, reset, notification privacy and body limits passed.",
                    flush=True,
                )
                checked(owner, "POST", "/api/v1/auth/logout", 204)
                checked(owner, "GET", "/api/v1/auth/me", 401)
                node_environment = {
                    **environment,
                    "FULLSTACK_TEST_BASE": base,
                    "FULLSTACK_TEST_CHANNEL": channel,
                    "FULLSTACK_TEST_VIEWER_TOKEN": first["Authorization"][7:],
                }
                subprocess.run(
                    ["node", str(ROOT / "scripts/fullstack_clients.mjs")],
                    env=node_environment,
                    check=True,
                    timeout=60,
                )
                coverage.verify()
                print(
                    "Verified real local HTTP/PostgreSQL; Twitch uses an HTTP fixture.",
                    flush=True,
                )
        finally:
            if process and process.poll() is None:
                process.terminate()
                process.communicate(timeout=10)
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
                        prefix=channel + "%",
                    )
                run(
                    c,
                    "DELETE FROM twitch_games.dashboard_sessions WHERE user_id LIKE :prefix",
                    prefix=channel + "%",
                )
                run(
                    c,
                    "DELETE FROM twitch_games.oauth_authorizations WHERE user_id LIKE :prefix",
                    prefix=channel + "%",
                )
                run(
                    c,
                    "DELETE FROM twitch_games.channels WHERE id LIKE :prefix",
                    prefix=channel + "%",
                )
                run(
                    c,
                    "DELETE FROM twitch_games.twitch_users WHERE id LIKE :prefix",
                    prefix=channel + "%",
                )
                run(
                    c,
                    "DELETE FROM twitch_games.participants WHERE id LIKE :prefix",
                    prefix=channel + "%",
                )
            database.close()


if __name__ == "__main__":
    main()
