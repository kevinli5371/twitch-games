"""Exercise a real, loopback-only foundation server with isolated test settings."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from twitch_games.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-status",
        default="not_configured",
        choices=["not_configured", "ok", "migration_required", "unavailable"],
    )
    args = parser.parse_args()
    database_url = None
    if args.database_status != "not_configured":
        settings = Settings()
        if settings.database_url is None:
            raise SystemExit("Configured database mode requires TWITCH_GAMES_DATABASE_URL")
        database_url = settings.database_url.get_secret_value()
    root = Path(__file__).resolve().parents[1]
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    environment = {k: v for k, v in os.environ.items() if not k.startswith("TWITCH_GAMES_")}
    environment.update(
        TWITCH_GAMES_ENVIRONMENT="test",
        TWITCH_GAMES_DOCS_ENABLED="true",
        TWITCH_GAMES_CORS_ORIGINS="[]",
    )
    if database_url is not None:
        environment["TWITCH_GAMES_DATABASE_URL"] = database_url
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # Use an empty cwd so a developer's .env cannot change smoke-test behavior.
    with TemporaryDirectory(prefix="smoke-", dir=cache) as cwd:
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
            ],
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(process.communicate()[0])
                try:
                    with urlopen(base + "/health/live", timeout=1) as response:
                        assert response.status == 200
                        assert json.load(response)["status"] == "ok"
                    break
                except URLError:
                    time.sleep(0.05)
            else:
                raise RuntimeError("Server did not become live within the startup retry window")
            print("/health/live: HTTP 200")
            for path, expected in [
                ("/health/ready", 503),
                ("/docs", 200),
                ("/api/v1/channels/12345/game-state", 404),
            ]:
                try:
                    with urlopen(base + path, timeout=2) as response:
                        status = response.status
                except HTTPError as response:
                    status = response.code
                    if path == "/health/ready":
                        assert (
                            json.load(response)["dependencies"]["database"] == args.database_status
                        )
                assert status == expected, (path, status)
                print(f"{path}: HTTP {status}")
            print(f"Database readiness: {args.database_status}; real server smoke test passed.")
        finally:
            process.terminate()
            process.communicate(timeout=5)


if __name__ == "__main__":
    main()
