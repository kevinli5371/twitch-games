"""Concurrent/rollback/fencing checks through real PostgREST, disposable DB only."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from twitch_games.auth import Identity
from twitch_games.config import Settings
from twitch_games.contracts.models import OpenRound, StartGame, TranscriptBatch
from twitch_games.database import Database
from twitch_games.errors import GameError
from twitch_games.http_game_service import HTTPGameService
from twitch_games.store import one, run
from twitch_games.supabase_http import SupabaseHTTP


def main():
    dsn = os.environ["TWITCH_GAMES_TEST_DATABASE_URL"]
    sql = Database(Settings(database_url=dsn, _env_file=None))
    parsed = sql.engine.url
    assert parsed.host in {"127.0.0.1", "localhost"} and parsed.database.endswith("_test")
    database = SupabaseHTTP(
        Settings(
            environment="test",
            supabase_url="https://fixture.supabase.co",
            supabase_secret_key="sb_secret_local_http_test_only",
            test_supabase_http_url=os.environ["TWITCH_GAMES_TEST_SUPABASE_HTTP_URL"],
            _env_file=None,
        )
    )
    service = HTTPGameService(database, None)
    channel = str(uuid4().int)[:15]
    owner = Identity(channel, channel, "broadcaster")
    now = datetime.now(UTC)
    try:
        connected = service.call(
            "stream_connect",
            owner,
            twitch_stream_id="fixture-concurrency",
            started_at=(now - timedelta(minutes=5)).isoformat(),
        )
        stream = connected["stream_id"]
        bad_id = str(uuid4())
        try:
            service.call(
                "intake",
                owner,
                stream_id=stream,
                digest="0" * 64,
                body={
                    "batch_id": bad_id,
                    "source": "twitch_player_captions",
                    "segments": [
                        {
                            "sequence": 0,
                            "text": "The first valid fixture segment.",
                            "observed_at": now.isoformat(),
                        },
                        {
                            "sequence": 1,
                            "text": "Future timestamp must roll back the entire batch.",
                            "observed_at": (now + timedelta(hours=1)).isoformat(),
                        },
                    ],
                },
            )
            raise AssertionError("Invalid batch accepted")
        except GameError as error:
            assert error.status == 422
        with sql.transaction() as c:
            assert (
                one(
                    c,
                    "SELECT count(*) AS n FROM twitch_games.transcript_batches WHERE id=:id",
                    id=bad_id,
                )["n"]
                == 0
            )
        batch = TranscriptBatch(
            batch_id=uuid4(),
            source="twitch_player_captions",
            segments=[
                {
                    "sequence": 0,
                    "text": (
                        "The incredible championship finished with "
                        "a brilliant victory for our team."
                    ),
                    "observed_at": now,
                }
            ],
        )
        service.intake(owner, stream, batch)
        game = service.start(
            owner, channel, StartGame(request_id=uuid4(), mode="quote", policy_id="quote_v1")
        )
        opened = service.open_round(
            owner, game["game_id"], OpenRound(request_id=uuid4(), expected_version=game["version"])
        )
        round_id = opened["round"]["round_id"]
        q = service.call("score_input", owner, round_id=round_id)["round"]
        canonical = q["canonical_answer_snapshot"]

        def submit(index):
            identity = Identity(channel, channel + str(index + 100), "viewer")
            body = {"request_id": str(uuid4()), "answer": canonical if index < 100 else "wrong"}
            result = service.call(
                "submit",
                identity,
                round_id=round_id,
                body=body,
                display_name="Fixture viewer " + str(index),
            )
            return identity, body, result

        with ThreadPoolExecutor(max_workers=12) as executor:
            submitted = list(executor.map(submit, range(105)))
        identity, body, receipt = submitted[0]
        with ThreadPoolExecutor(max_workers=2) as executor:
            retried = list(
                executor.map(
                    lambda _: service.call(
                        "submit",
                        identity,
                        round_id=round_id,
                        body=body,
                        display_name="Fixture viewer",
                    ),
                    range(2),
                )
            )
        assert retried[0] == retried[1] == receipt
        with sql.transaction() as c:
            run(
                c,
                "UPDATE twitch_games.rounds SET opened_at=clock_timestamp()-interval '31 seconds',"
                "closes_at=clock_timestamp()-interval '1 second' WHERE id=:id",
                id=round_id,
            )
        awards = service.awards(round_id)
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(
                executor.map(
                    lambda _: service.call("score_finalize", round_id=round_id, awards=awards),
                    range(2),
                )
            )
        board = service.leaderboard(submitted[-1][0], game["game_id"])
        assert (
            len(board["entries"]) == 100
            and board["own_entry"]["rank"] == 101
            and board["own_entry"]["points"] == 0
        )
        with sql.transaction() as c:
            counts = one(
                c,
                "SELECT count(*) AS n,sum(points) AS total "
                "FROM twitch_games.score_entries WHERE round_id=:id",
                id=round_id,
            )
            assert counts["n"] == 105 and counts["total"] == 100
            assert (
                one(c, "SELECT version FROM twitch_games.channels WHERE id=:id", id=channel)[
                    "version"
                ]
                == opened["version"] + 1
            )
        # Refresh claims fence delayed writers; fixture ciphertext never authorizes real Twitch.
        profile = {"id": channel, "login": "fixture" + channel, "display_name": "Fixture owner"}
        service.call(
            "oauth_login",
            profile=profile,
            access="fixture-protected-access",
            refresh="fixture-protected-refresh",
            seconds=3600,
            session_digest=hashlib.sha256(channel.encode()).hexdigest(),
            old_digest=None,
        )
        first = service.call("auth_claim", user_id=channel, force=True)
        try:
            service.call("auth_claim", user_id=channel, force=True)
            raise AssertionError("Concurrent refresh claim accepted")
        except GameError as error:
            assert error.status == 503
        with sql.transaction() as c:
            run(
                c,
                "UPDATE twitch_games.backend_claims "
                "SET expires_at=clock_timestamp()-interval '1 second' "
                "WHERE kind='auth' AND key=:key",
                key=channel,
            )
        second = service.call("auth_claim", user_id=channel, force=True)
        try:
            service.call("auth_finish", user_id=channel, lease=first["lease"], revoke=True)
            raise AssertionError("Expired refresh writer accepted")
        except GameError as error:
            assert error.status == 503
        service.call(
            "auth_finish",
            user_id=channel,
            lease=second["lease"],
            access="fixture-new-access",
            refresh="fixture-new-refresh",
            seconds=3600,
        )
        assert service.call("auth_claim", user_id=channel)["status"] == "valid"
        moderator = Identity(channel, channel + "500", "moderator", "dashboard")
        service.call(
            "grants_set",
            owner,
            owner=profile,
            moderator={
                "id": moderator.user_id,
                "login": "fixturemoderator",
                "display_name": "Fixture moderator",
            },
            permissions=["live_control"],
        )
        assert service.call("permissions", moderator) == ["live_control"]
        service.call("grants_revoke", owner, moderator_id=moderator.user_id)
        try:
            service.call("permissions", moderator)
            raise AssertionError("Revoked grant still accepted")
        except GameError as error:
            assert error.status == 403
        print(
            "Real HTTP RPC rollback, 105 concurrent submissions, retry identity, "
            "duplicate scoring, "
            "rank 101, refresh fencing and immediate grant revocation passed.",
            flush=True,
        )
    finally:
        database.close()
        with sql.transaction() as c:
            run(
                c,
                "DELETE FROM twitch_games.backend_claims WHERE key LIKE :prefix",
                prefix=channel + "%",
            )
            for table in [
                "generation_queue",
                "moderator_grants",
                "state_notifications",
                "command_receipts",
                "answer_aliases",
                "score_entries",
                "submissions",
                "rounds",
                "game_sessions",
                "question_sources",
                "question_candidates",
                "transcript_segments",
                "transcript_batches",
                "streams",
            ]:
                run(
                    c,
                    f"DELETE FROM twitch_games.{table} WHERE channel_id LIKE :prefix",
                    prefix=channel + "%",
                )
            for table, key in [
                ("dashboard_sessions", "user_id"),
                ("oauth_authorizations", "user_id"),
                ("channels", "id"),
                ("twitch_users", "id"),
                ("participants", "id"),
            ]:
                run(
                    c,
                    f"DELETE FROM twitch_games.{table} WHERE {key} LIKE :prefix",
                    prefix=channel + "%",
                )
        sql.close()


if __name__ == "__main__":
    main()
