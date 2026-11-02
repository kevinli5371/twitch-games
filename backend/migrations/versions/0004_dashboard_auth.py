"""Verified profiles, refreshable authorizations and explicit moderator workspace grants."""

from pathlib import Path

from alembic import op

revision = "0004_dashboard_auth"
down_revision = "0003_round_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text())


def downgrade():
    # Restore legacy sessions from their shared authorization before dropping the new records.
    op.execute(
        "ALTER TABLE twitch_games.dashboard_sessions ADD COLUMN channel_id varchar(32), "
        "ADD COLUMN encrypted_token text, ADD COLUMN validated_at timestamptz"
    )
    op.execute(
        "UPDATE twitch_games.dashboard_sessions s SET channel_id=s.user_id, "
        "encrypted_token=a.encrypted_access_token,validated_at=a.validated_at "
        "FROM twitch_games.oauth_authorizations a WHERE a.user_id=s.user_id"
    )
    for column in ("channel_id", "encrypted_token", "validated_at"):
        op.alter_column("dashboard_sessions", column, nullable=False, schema="twitch_games")
    op.create_foreign_key(
        "legacy_session_channel",
        "dashboard_sessions",
        "channels",
        ["channel_id"],
        ["id"],
        source_schema="twitch_games",
        referent_schema="twitch_games",
    )
    op.drop_column("dashboard_sessions", "user_id", schema="twitch_games")
    op.drop_column("channels", "owner_twitch_id", schema="twitch_games")
    for table in ("moderator_grants", "oauth_authorizations", "twitch_users"):
        op.drop_table(table, schema="twitch_games")
