"""Serve the actual clients/API with disposable PostgreSQL and explicit Twitch fixtures.

For manual browser verification only; production code has no test-auth endpoint.
Ctrl-C stops all processes and removes the Docker database. Never loads .env.
"""

import base64
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import httpx2 as httpx
import jwt
from cryptography.fernet import Fernet
from postgres_checks import IMAGE
from support.twitch_fixture import twitch_fixture

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def main():
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
        with TemporaryDirectory(prefix="twitch-browser-") as cwd, twitch_fixture() as (url, _):
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
            for _ in range(50):
                try:
                    if httpx.get(f"http://127.0.0.1:{api_port}/health/ready").status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(0.2)
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
                            {"channel": "90001", "viewers": viewers}
                        ),
                    },
                )
            )
            (ROOT / ".cache/browser-stack.pid").write_text(str(os.getpid()))
            print("Synthetic Twitch browser test. Dashboard: http://127.0.0.1:4190/", flush=True)
            Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            process.terminate()
            process.wait(timeout=10)
        if started:
            subprocess.run(
                ["docker", "rm", "--force", "--volumes", name],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        print("Browser fixture processes and disposable database removed.", flush=True)


if __name__ == "__main__":
    main()
