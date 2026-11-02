"""Explicit migrations only: the API never creates or migrates a schema at startup."""

from alembic import context
from sqlalchemy import text

from twitch_games.config import Settings
from twitch_games.database import SCHEMA, create_database_engine


def run_migrations_online() -> None:
    settings = Settings()
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            existing = set(
                connection.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname=:schema"),
                    {"schema": SCHEMA},
                ).scalars()
            )
            if existing and "alembic_version" not in existing:
                raise RuntimeError(
                    "Refusing an unmanaged nonempty twitch_games schema; inspect before migrating"
                )
            # Private schema also contains Alembic's revision table.
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
            connection.execute(text(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC"))
            connection.commit()
            context.configure(
                connection=connection,
                version_table_schema=SCHEMA,
                target_metadata=None,
                transactional_ddl=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline mode is not supported; review the versioned SQL directly")
else:
    run_migrations_online()
