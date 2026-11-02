"""Build the runtime image and probe it over real loopback HTTP, then clean up."""

import argparse
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    image = "twitch-games-backend:verification"
    if not args.skip_build:
        subprocess.run(["docker", "build", "--tag", image, "."], cwd=ROOT, check=True)
    name = "twitch-games-image-check-" + uuid4().hex[:8]
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
                "127.0.0.1::8000",
                "--env",
                "TWITCH_GAMES_ENVIRONMENT=production",
                "--env",
                "TWITCH_GAMES_DOCS_ENABLED=false",
                "--env",
                'TWITCH_GAMES_CORS_ORIGINS=["https://dashboard.example.test"]',
                image,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        port = (
            subprocess.check_output(["docker", "port", name, "8000"], text=True)
            .strip()
            .rsplit(":", 1)[1]
        )
        base = "http://127.0.0.1:" + port
        for _ in range(100):
            try:
                with urlopen(base + "/health/live", timeout=1) as response:
                    assert response.status == 200
                break
            except (URLError, ConnectionError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Docker API startup timed out")
        for path, expected in [
            ("/health/live", 200),
            ("/health/ready", 503),
            ("/docs", 404),
            ("/api/v1/channels/12345/game-state", 401),
        ]:
            try:
                with urlopen(base + path, timeout=2) as response:
                    status = response.status
            except HTTPError as response:
                status = response.code
            assert status == expected, (path, status)
            print("Docker image " + path + ": HTTP " + str(status))
        subprocess.run(
            [
                "docker",
                "exec",
                name,
                "python",
                "-c",
                "import os; assert os.getuid()==10001; assert not os.path.exists('/app/.env')",
            ],
            check=True,
        )
        print("Non-root runtime and exclusion of .env from image verified.")
    finally:
        subprocess.run(
            ["docker", "rm", "--force", "--volumes", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    main()
