"""Persist quote priority, freeze full revealed quotes, and enforce v1 point values."""

from alembic import op

revision = "0003_round_snapshots"
down_revision = "0002_runtime"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE twitch_games.question_candidates ADD COLUMN selection_weight "
        "double precision NOT NULL DEFAULT 0 "
        "CHECK (selection_weight >= 0 AND selection_weight <= 100)"
    )
    op.execute("ALTER TABLE twitch_games.rounds ADD COLUMN complete_quote_snapshot text")
    op.execute(
        "UPDATE twitch_games.rounds r SET complete_quote_snapshot=q.complete_quote "
        "FROM twitch_games.question_candidates q WHERE q.id=r.question_id"
    )
    op.alter_column("rounds", "complete_quote_snapshot", nullable=False, schema="twitch_games")
    op.create_check_constraint(
        "quote_v1_points",
        "score_entries",
        "scoring_policy_id <> 'quote_v1' OR points = CASE WHEN outcome='correct' THEN 1 ELSE 0 END",
        schema="twitch_games",
    )
    op.execute("""DO $$ DECLARE role_name text; BEGIN
        FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
                EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA twitch_games FROM %I',
                    role_name);
            END IF;
        END LOOP;
    END $$""")


def downgrade():
    op.drop_constraint("quote_v1_points", "score_entries", schema="twitch_games")
    op.drop_column("rounds", "complete_quote_snapshot", schema="twitch_games")
    op.drop_column("question_candidates", "selection_weight", schema="twitch_games")
