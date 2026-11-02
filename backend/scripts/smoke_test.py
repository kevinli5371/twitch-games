"""Exercise a real, loopback-only foundation server with isolated test settings."""

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


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        TWITCH_GAMES_ENVIRONMENT="test",
        TWITCH_GAMES_DOCS_ENABLED="true",
        TWITCH_GAMES_CORS_ORIGINS="[]",
    )
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
                        assert json.load(response)["dependencies"]["database"] == "not_implemented"
                assert status == expected, (path, status)
                print(f"{path}: HTTP {status}")
            print("Real Uvicorn process smoke test passed; stopping server.")
        finally:
            process.terminate()
            process.communicate(timeout=5)


if __name__ == "__main__":
    main()
