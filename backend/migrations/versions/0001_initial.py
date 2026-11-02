"""Private, channel-scoped quote-game persistence; no gameplay defaults."""

from pathlib import Path

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Frozen SQL lives beside this revision, not in mutable application metadata.
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    # Explicitly owned tables only. Leave schema/version bookkeeping intact.
    for table in (
        "score_entries",
        "submissions",
        "rounds",
        "game_sessions",
        "question_sources",
        "question_candidates",
        "transcript_segments",
        "transcript_batches",
        "streams",
        "participants",
        "channels",
    ):
        op.drop_table(table, schema="twitch_games")
