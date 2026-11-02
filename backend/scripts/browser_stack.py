"""Serve the actual clients/API with disposable PostgreSQL and explicit Twitch fixtures.

For manual browser verification only; production code has no test-auth endpoint.
Ctrl-C stops all processes and removes the Docker database. Never loads .env.
"""

import argparse
import base64
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import httpx2 as httpx
import jwt
import psycopg
from cryptography.fernet import Fernet
from postgres_checks import IMAGE
from support.postgrest_fixture import postgrest_fixture
from support.public_notice_fixture import public_notice_fixture
from support.twitch_fixture import twitch_fixture

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", choices=["supabase_http", "postgres"], default="supabase_http")
    parser.add_argument(
        "--smoke", action="store_true", help="Verify fixture HTTP surfaces, then clean up"
    )
    args = parser.parse_args()
    name = "twitch-games-browser-" + secrets.token_hex(4)
    environment = {k: v for k, v in os.environ.items() if not k.startswith("TWITCH_GAMES_")}
    environment["POSTGRES_PASSWORD"] = secrets.token_urlsafe(24)
    api_port, ui_port = port(), 4190
    key = secrets.token_bytes(32)
    processes = []
    started = False
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--publish",
                "127.0.0.1::5432",
                "--publish",
                "127.0.0.1::3000",
                "--env",
                "POSTGRES_PASSWORD",
                "--env",
                "POSTGRES_USER=twitch_test",
                "--env",
                "POSTGRES_DB=browser_test",
                IMAGE,
            ],
            env=environment,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        started = True
        for _ in range(30):
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "twitch_test"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Disposable database not ready")
        db_port = (
            subprocess.check_output(["docker", "port", name, "5432"], text=True)
            .strip()
            .rsplit(":", 1)[1]
        )
        with (
            TemporaryDirectory(prefix="twitch-browser-") as cwd,
            twitch_fixture() as (url, fixture),
            ExitStack() as resources,
        ):
            values = {
                "ENVIRONMENT": "test",
                "DOCS_ENABLED": "true",
                "DATABASE_URL": f"postgresql://twitch_test:{environment['POSTGRES_PASSWORD']}"
                f"@127.0.0.1:{db_port}/browser_test",
                "TWITCH_CLIENT_ID": "fixture-app",
                "TWITCH_CLIENT_SECRET": "fixture-secret",
                "TWITCH_REDIRECT_URI": f"http://127.0.0.1:{api_port}/api/v1/auth/twitch/callback",
                "DASHBOARD_URL": f"http://127.0.0.1:{ui_port}/",
                "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "TWITCH_EXTENSION_CLIENT_ID": "fixture-extension",
                "TWITCH_EXTENSION_SECRET": base64.b64encode(key).decode(),
                "TWITCH_EXTENSION_OWNER_ID": "90001",
                "TEST_TWITCH_BASE_URL": url,
                "CORS_ORIGINS": "[]",
            }
            dsn = values["DATABASE_URL"]
            with psycopg.connect(dsn) as connection:
                for role in ["anon", "authenticated"]:
                    connection.execute("CREATE ROLE " + role + " NOLOGIN NOSUPERUSER NOBYPASSRLS")
                connection.execute("CREATE ROLE service_role NOLOGIN BYPASSRLS")
            environment.update({"TWITCH_GAMES_" + k: v for k, v in values.items()})
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "alembic",
                    "-c",
                    str(ROOT / "alembic.ini"),
                    "upgrade",
                    "head",
                ],
                cwd=cwd,
                env=environment,
                check=True,
            )
            if args.storage == "supabase_http":
                rest_url = resources.enter_context(postgrest_fixture(dsn, name))
                environment.update(
                    TWITCH_GAMES_STORAGE_BACKEND="supabase_http",
                    TWITCH_GAMES_SUPABASE_URL="https://fixture.supabase.co",
                    TWITCH_GAMES_SUPABASE_SECRET_KEY="sb_secret_local_http_test_only",
                    TWITCH_GAMES_TEST_SUPABASE_HTTP_URL=rest_url,
                )
            notices = resources.enter_context(public_notice_fixture(fixture))
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "twitch_games.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--no-access-log",
                    ],
                    cwd=cwd,
                    env=environment,
                )
            )
            resources.callback(stop_process, processes[-1])
            for _ in range(50):
                try:
                    if (
                        httpx.get(
                            f"http://127.0.0.1:{api_port}/health/ready", timeout=2
                        ).status_code
                        == 200
                    ):
                        break
                except httpx.RequestError:
                    pass
                time.sleep(0.2)
            else:
                raise RuntimeError("Disposable backend did not become ready")
            viewers = [
                {
                    "id": user,
                    "token": jwt.encode(
                        {
                            "exp": int(time.time()) + 7200,
                            "channel_id": "90001",
                            "role": "viewer",
                            "user_id": user,
                            "opaque_user_id": "U" + user,
                        },
                        key,
                        algorithm="HS256",
                    ),
                }
                for user in ["90002", "90003"]
            ]
            processes.append(
                subprocess.Popen(
                    ["node", str(ROOT / "scripts/browser_server.mjs")],
                    cwd=cwd,
                    env={
                        **environment,
                        "PORT": str(ui_port),
                        "API_ORIGIN": f"http://127.0.0.1:{api_port}",
                        "BROWSER_STACK_CONTEXT": json.dumps(
                            {
                                "channel": "90001",
                                "viewers": viewers,
                                "eventsUrl": notices,
                                "storage": args.storage,
                            }
                        ),
                    },
                )
            )
            resources.callback(stop_process, processes[-1])
            (ROOT / ".cache/browser-stack.pid").write_text(str(os.getpid()))
            print(
                "Synthetic Twitch browser test; storage="
                + args.storage
                + ". Dashboard: http://127.0.0.1:4190/",
                flush=True,
            )
            if args.smoke:
                for _ in range(30):
                    try:
                        response = httpx.get(f"http://127.0.0.1:{ui_port}/viewer.html", timeout=2)
                        if response.status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Browser fixture server did not start")
                assert "/test-helper.js" in response.text
                adapter = httpx.get(f"http://127.0.0.1:{ui_port}/api-adapter.mjs")
                assert "pollMs = 3600000" in adapter.text
                assert httpx.get(f"http://127.0.0.1:{ui_port}/test-events").status_code == 200
                print("Browser harness HTTP/notice surfaces passed; cleanup follows.", flush=True)
            else:
                Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            stop_process(process)
        if started:
            subprocess.run(
                ["docker", "rm", "--force", "--volumes", name],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        pidfile = ROOT / ".cache/browser-stack.pid"
        if pidfile.exists() and pidfile.read_text() == str(os.getpid()):
            pidfile.unlink()
        print("Browser fixture processes and disposable database removed.", flush=True)


if __name__ == "__main__":
    main()
