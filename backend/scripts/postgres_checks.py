"""Provision, verify and clean up isolated PostgreSQL; never uses a hosted database."""

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import psycopg
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "postgres:17@sha256:3b0cda93be7c8dba2ed484d19393d93845dc3dafb88973e248ba8e6d99d784e1"


def main() -> None:
    name = f"twitch-games-pgtest-{uuid4().hex[:10]}"
    environment = os.environ.copy()
    environment["POSTGRES_PASSWORD"] = secrets.token_urlsafe(24)
    started = False

    def run(*command: str, capture: bool = False):
        return subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
        )

    def alembic(*arguments: str) -> None:
        run(sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments)

    try:
        run(
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
            "POSTGRES_DB=twitch_games_test",
            IMAGE,
            capture=True,
        )
        started = True
        for _ in range(30):
            probe = subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "pg_isready",
                    "-U",
                    "twitch_test",
                    "-d",
                    "twitch_games_test",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Disposable PostgreSQL did not become ready")
        port = int(
            run("docker", "port", name, "5432", capture=True).stdout.strip().rsplit(":", 1)[1]
        )
        url = URL.create(
            "postgresql",
            username="twitch_test",
            password=environment["POSTGRES_PASSWORD"],
            host="127.0.0.1",
            port=port,
            database="twitch_games_test",
        )
        dsn = url.render_as_string(hide_password=False)
        environment.update(
            TWITCH_GAMES_ENVIRONMENT="test",
            TWITCH_GAMES_DOCS_ENABLED="true",
            TWITCH_GAMES_CORS_ORIGINS="[]",
            TWITCH_GAMES_DATABASE_URL=dsn,
            TWITCH_GAMES_TEST_DATABASE_URL=dsn,
        )
        with psycopg.connect(dsn) as connection:
            connection.execute("CREATE ROLE anon NOLOGIN NOSUPERUSER NOBYPASSRLS")
            connection.execute("CREATE ROLE authenticated NOLOGIN NOSUPERUSER NOBYPASSRLS")
            version = connection.execute("SHOW server_version").fetchone()[0]
        print(f"Live isolated PostgreSQL {version}; credentials not logged.", flush=True)
        alembic("upgrade", "head")
        alembic("upgrade", "head")  # Repeatable application does not recreate data.
        run(sys.executable, "-m", "pytest", "-q", "-W", "error")
        run(sys.executable, "scripts/smoke_test.py", "--database-status", "ok")
        bad_url = url.set(database="missing_database_test").render_as_string(hide_password=False)
        environment["TWITCH_GAMES_DATABASE_URL"] = bad_url
        run(sys.executable, "scripts/smoke_test.py", "--database-status", "unavailable")
        environment["TWITCH_GAMES_DATABASE_URL"] = dsn
        alembic("downgrade", "base")
        with psycopg.connect(dsn) as connection:
            remaining = connection.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname='twitch_games' "
                "AND tablename <> 'alembic_version'"
            ).fetchone()[0]
            assert remaining == 0
        run(sys.executable, "scripts/smoke_test.py", "--database-status", "migration_required")
        alembic("upgrade", "head")
        run(sys.executable, "scripts/smoke_test.py", "--database-status", "ok")
        run(sys.executable, "scripts/smoke_test.py")
        print(
            "Migration up/repeat/down/up, live database tests and HTTP checks passed.", flush=True
        )
    finally:
        if started:
            subprocess.run(
                ["docker", "rm", "--force", "--volumes", name],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            print("Disposable test container and its data removed.", flush=True)


if __name__ == "__main__":
    main()
