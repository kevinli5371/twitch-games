"""Authentication, alias management, versioning and recoverable synchronization."""

from pathlib import Path

from alembic import op

revision = "0002_runtime"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text())


def downgrade():
    for table in (
        "state_notifications",
        "command_receipts",
        "answer_aliases",
        "dashboard_sessions",
        "oauth_states",
    ):
        op.drop_table(table, schema="twitch_games")
    op.drop_column("question_candidates", "generator_version", schema="twitch_games")
    op.drop_column("submissions", "revision", schema="twitch_games")
    op.drop_column("channels", "version", schema="twitch_games")
