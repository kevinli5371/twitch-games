"""Backend-only atomic HTTPS RPC surface with private worker claims."""

from pathlib import Path

from alembic import op

revision = "0005_http_rpc"
down_revision = "0004_dashboard_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text())


def downgrade():
    op.execute("DROP FUNCTION public.twitch_games_backend(text,jsonb)")
    for signature in [
        "rpc_score(uuid,jsonb)",
        "rpc_profile(jsonb)",
        "rpc_board(uuid,text,text)",
        "rpc_candidates(uuid)",
        "rpc_bump(text)",
        "rpc_state(text)",
        "rpc_permission(jsonb,text,text)",
        "rpc_fail(text,text,integer)",
    ]:
        op.execute("DROP FUNCTION twitch_games." + signature)
    op.drop_table("generation_queue", schema="twitch_games")
    op.drop_table("backend_claims", schema="twitch_games")
