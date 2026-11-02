"""Verify the configured hosted PostgreSQL connection without printing credentials.

Default is read-only. --apply-migrations applies the app's additive schema migration;
--exercise-writes checks an insert and rollback, leaving no probe records behind.
Never run destructive downgrade or the disposable test suite against a hosted project.
"""

import argparse
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from twitch_games.config import Settings
from twitch_games.database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-migrations", action="store_true")
    parser.add_argument("--exercise-writes", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    if settings.database_url is None:
        raise SystemExit("Set TWITCH_GAMES_DATABASE_URL in backend/.env; do not paste credentials.")
    database = Database(settings)
    try:
        if database.engine.url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
            raise SystemExit("Hosted checks require explicit TLS in the PostgreSQL URI")
        with database.engine.begin() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
            # sslmode=require/verify-* enforces TLS on this client connection. pg_stat_ssl
            # can instead describe the pooler-to-database leg, so do not infer client TLS from it.
        print("Configured PostgreSQL connection verified over TLS; URI/password not logged.")
        if args.apply_migrations:
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            command.upgrade(config, "head")
            print("App migration applied; unrelated schemas not modified.")
        status = database.status()
        print(f"Application migration status: {status}")
        if status != "ok":
            raise SystemExit("Connectivity verified, but application migration is not ready")
        if args.exercise_writes:
            identifier = "9" + str(uuid4().int)[:22]
            with database.engine.connect() as connection:
                transaction = connection.begin()
                try:
                    connection.execute(
                        text(
                            "INSERT INTO twitch_games.channels(id,display_name) VALUES (:id,:name)"
                        ),
                        {"id": identifier, "name": "temporary verification; rolled back"},
                    )
                    assert (
                        connection.execute(
                            text("SELECT count(*) FROM twitch_games.channels WHERE id=:id"),
                            {"id": identifier},
                        ).scalar_one()
                        == 1
                    )
                finally:
                    transaction.rollback()
            with database.transaction() as connection:
                assert (
                    connection.execute(
                        text("SELECT count(*) FROM twitch_games.channels WHERE id=:id"),
                        {"id": identifier},
                    ).scalar_one()
                    == 0
                )
            print("Hosted insert/rollback verified; no probe record retained.")
        with database.engine.begin() as connection:
            for role in ("anon", "authenticated"):
                exists = connection.execute(
                    text("SELECT count(*) FROM pg_roles WHERE rolname=:role"), {"role": role}
                ).scalar_one()
                if exists:
                    assert not connection.execute(
                        text("SELECT has_schema_privilege(:role,'twitch_games','USAGE')"),
                        {"role": role},
                    ).scalar_one()
        print("Existing client-role schema permissions verified.")
    except SQLAlchemyError:
        raise SystemExit(
            "Database check failed; check connectivity/role permissions locally. "
            "Driver details suppressed to protect connection information."
        ) from None
    finally:
        database.close()


if __name__ == "__main__":
    main()
