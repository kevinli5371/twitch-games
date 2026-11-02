"""Bounded PostgreSQL connections and transactions; no game policy or CRUD API."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from twitch_games.config import Settings

SCHEMA = "twitch_games"
SCHEMA_REVISION = "0001_initial"
DatabaseStatus = Literal["not_configured", "unavailable", "migration_required", "ok"]


def create_database_engine(settings: Settings) -> Engine:
    if settings.database_url is None:
        raise ValueError("TWITCH_GAMES_DATABASE_URL is not configured")
    url = make_url(settings.database_url.get_secret_value()).set(drivername="postgresql+psycopg")
    return create_engine(
        url,
        pool_size=settings.database_pool_size,
        max_overflow=0,
        pool_timeout=settings.database_connect_timeout_seconds,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds,
            # Compatible with transaction poolers; no server-side prepared state is assumed.
            "prepare_threshold": None,
        },
    )


class Database:
    def __init__(self, settings: Settings):
        self.engine = create_database_engine(settings)

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Commit on success; roll back the entire unit of work on failure."""
        with self.engine.begin() as connection:
            yield connection

    def status(self) -> DatabaseStatus:
        try:
            with self.engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL statement_timeout = 2000")
                version_table = connection.execute(
                    text("SELECT to_regclass('twitch_games.alembic_version')")
                ).scalar_one()
                if version_table is None:
                    return "migration_required"
                revisions = (
                    connection.execute(text("SELECT version_num FROM twitch_games.alembic_version"))
                    .scalars()
                    .all()
                )
                return "ok" if revisions == [SCHEMA_REVISION] else "migration_required"
        except (SQLAlchemyError, OSError):
            # Never echo a DSN, driver error, SQL parameters or secret into health responses.
            return "unavailable"

    def close(self) -> None:
        self.engine.dispose()
