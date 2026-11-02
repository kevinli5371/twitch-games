import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from twitch_games.application import create_app
from twitch_games.config import Settings
from twitch_games.database import SCHEMA_REVISION, Database

pytestmark = pytest.mark.integration


def seed(connection, channel="12345"):
    ids = {name: uuid4() for name in ["stream", "batch", "segment", "question", "game", "round"]}
    quote = "I cannot believe we won with a spoon."
    start = quote.index("spoon")
    connection.execute(text("INSERT INTO twitch_games.channels(id) VALUES (:id)"), {"id": channel})
    connection.execute(text("INSERT INTO twitch_games.participants(id) VALUES ('54321')"))
    connection.execute(
        text("""
        INSERT INTO twitch_games.streams(id,channel_id,twitch_stream_id,started_at)
        VALUES (:stream,:channel,'test-stream',now())
    """),
        {**ids, "channel": channel},
    )
    connection.execute(
        text("""
        INSERT INTO twitch_games.transcript_batches(id,stream_id,channel_id,source,payload_digest)
        VALUES (:batch,:stream,:channel,'twitch_player_captions',:digest)
    """),
        {**ids, "channel": channel, "digest": hashlib.sha256(quote.encode()).hexdigest()},
    )
    connection.execute(
        text("""
        INSERT INTO twitch_games.transcript_segments
            (id,batch_id,stream_id,channel_id,sequence,text,observed_at)
        VALUES (:segment,:batch,:stream,:channel,0,:quote,now())
    """),
        {**ids, "channel": channel, "quote": quote},
    )
    connection.execute(
        text("""
        INSERT INTO twitch_games.question_candidates
            (id,stream_id,channel_id,complete_quote,prompt,canonical_answer,quote_digest,
             blank_start,blank_end,accepted_aliases,review_status)
        VALUES (:question,:stream,:channel,:quote,:prompt,'spoon',:digest,
                :start,:end,'[]','pending')
    """),
        {
            **ids,
            "channel": channel,
            "quote": quote,
            "prompt": quote[:start] + "____" + quote[start + 5 :],
            "start": start,
            "end": start + 5,
            "digest": hashlib.sha256(quote.encode()).hexdigest(),
        },
    )
    connection.execute(
        text("""
        INSERT INTO twitch_games.question_sources(question_id,segment_id,stream_id,channel_id)
        VALUES (:question,:segment,:stream,:channel)
    """),
        {**ids, "channel": channel},
    )
    connection.execute(
        text("""
        INSERT INTO twitch_games.game_sessions
            (id,stream_id,channel_id,mode,status,policy_id,policy_snapshot,version,started_at)
        VALUES (:game,:stream,:channel,'quote','active','test-policy','{}',0,now())
    """),
        {**ids, "channel": channel},
    )
    connection.execute(
        text("""
        INSERT INTO twitch_games.rounds
            (id,game_id,stream_id,channel_id,question_id,phase,version,prompt_snapshot,
             canonical_answer_snapshot,accepted_aliases_snapshot,scoring_policy_id,policy_snapshot)
        VALUES (:round,:game,:stream,:channel,:question,'prepared',0,:prompt,'spoon','[]',
                'test-policy','{}')
    """),
        {**ids, "channel": channel, "prompt": quote.replace("spoon", "____")},
    )
    return {**ids, "channel": channel}


def submit(connection, ids, request=None, answer=" SpOOnn "):
    submission_id = uuid4()
    request = request or uuid4()
    connection.execute(
        text("""
        INSERT INTO twitch_games.submissions
            (id,round_id,game_id,channel_id,participant_id,request_id,raw_answer)
        VALUES (:submission,:round,:game,:channel,'54321',:request,:answer)
    """),
        {**ids, "submission": submission_id, "request": request, "answer": answer},
    )
    return submission_id


def award(connection, ids, submission_id, points=7, policy="test-policy"):
    # Synthetic test points; no production scoring policy is selected or implemented.
    connection.execute(
        text("""
        INSERT INTO twitch_games.score_entries
            (submission_id,round_id,game_id,channel_id,participant_id,outcome,points,scoring_policy_id)
        VALUES (:submission,:round,:game,:channel,'54321','correct',:points,:policy)
    """),
        {**ids, "submission": submission_id, "points": points, "policy": policy},
    )


def test_current_migration_and_all_private_tables(database):
    with database.transaction() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM twitch_games.alembic_version")
            ).scalar_one()
            == SCHEMA_REVISION
        )
        tables = connection.execute(
            text("""
            SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='twitch_games'
                AND tablename <> 'alembic_version'
        """)
        ).all()
        assert len(tables) == 11
        assert all(rls for _, rls in tables)


def test_raw_answers_and_source_quotes_are_preserved(connection):
    ids = seed(connection)
    submission_id = submit(connection, ids)
    assert (
        connection.execute(
            text("SELECT raw_answer FROM twitch_games.submissions WHERE id=:id"),
            {"id": submission_id},
        ).scalar_one()
        == " SpOOnn "
    )
    row = connection.execute(
        text(
            "SELECT canonical_answer, complete_quote "
            "FROM twitch_games.question_candidates WHERE id=:id"
        ),
        {"id": ids["question"]},
    ).one()
    assert row.canonical_answer == "spoon"
    assert row.complete_quote == "I cannot believe we won with a spoon."


def test_retry_and_revision_storage_does_not_choose_editing_policy(connection):
    ids = seed(connection)
    request = uuid4()
    submit(connection, ids, request=request)
    with pytest.raises(IntegrityError), connection.begin_nested():
        submit(connection, ids, request=request)
    # Storage can retain an additional request; Step 7 decides whether editing is allowed.
    submit(connection, ids, answer="spoon")
    assert (
        connection.execute(text("SELECT count(*) FROM twitch_games.submissions")).scalar_one() == 2
    )


def test_duplicate_scores_do_not_increase_totals(connection):
    ids = seed(connection)
    first = submit(connection, ids)
    second = submit(connection, ids)
    award(connection, ids, first)
    with pytest.raises(IntegrityError), connection.begin_nested():
        award(connection, ids, first)
    with pytest.raises(IntegrityError), connection.begin_nested():
        award(connection, ids, second)
    assert (
        connection.execute(text("SELECT sum(points) FROM twitch_games.score_entries")).scalar_one()
        == 7
    )


def test_score_policy_must_match_its_round(connection):
    ids = seed(connection)
    submission_id = submit(connection, ids)
    with pytest.raises(IntegrityError), connection.begin_nested():
        award(connection, ids, submission_id, policy="wrong-policy")


def test_cross_channel_and_cross_stream_relations_are_rejected(connection):
    ids = seed(connection)
    connection.execute(text("INSERT INTO twitch_games.channels(id) VALUES ('99999')"))
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("""
            INSERT INTO twitch_games.transcript_batches
                (id,stream_id,channel_id,source,payload_digest)
            VALUES (:id,:stream,'99999','test',:digest)
        """),
            {"id": uuid4(), "stream": ids["stream"], "digest": "a" * 64},
        )
    with pytest.raises(IntegrityError), connection.begin_nested():
        submit(connection, {**ids, "channel": "99999"})
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("""
            INSERT INTO twitch_games.question_sources(question_id,segment_id,stream_id,channel_id)
            VALUES (:question,:segment,:wrong_stream,:channel)
        """),
            {**ids, "wrong_stream": uuid4()},
        )


def test_quote_blank_must_match_source_span(connection):
    ids = seed(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("""
            UPDATE twitch_games.question_candidates SET canonical_answer='fork' WHERE id=:id
        """),
            {"id": ids["question"]},
        )
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("""
            UPDATE twitch_games.question_candidates SET prompt='invented quote' WHERE id=:id
        """),
            {"id": ids["question"]},
        )


def test_policies_are_required_and_competing_sessions_are_rejected(connection):
    ids = seed(connection)
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("""
            INSERT INTO twitch_games.game_sessions
                (stream_id,channel_id,mode,status,policy_id,policy_snapshot,version)
            VALUES (:stream,:channel,'quote','active','test-policy','{}',0)
        """),
            ids,
        )
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(
            text("""
            INSERT INTO twitch_games.game_sessions(stream_id,channel_id,mode,status,version)
            VALUES (:stream,:channel,'quote','inactive',0)
        """),
            ids,
        )


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_client_roles_cannot_read_or_write_private_tables(connection, role):
    seed(connection)
    assert (
        connection.execute(
            text("SELECT count(*) FROM pg_roles WHERE rolname=:role"), {"role": role}
        ).scalar_one()
        == 1
    )
    with pytest.raises(ProgrammingError) as read_error, connection.begin_nested():
        connection.execute(text(f"SET LOCAL ROLE {role}"))
        connection.execute(text("SELECT * FROM twitch_games.question_candidates"))
    assert read_error.value.orig.sqlstate == "42501"
    with pytest.raises(ProgrammingError) as write_error, connection.begin_nested():
        connection.execute(text(f"SET LOCAL ROLE {role}"))
        connection.execute(text("INSERT INTO twitch_games.channels(id) VALUES ('88888')"))
    assert write_error.value.orig.sqlstate == "42501"


def test_rls_denies_rows_even_when_select_grants_exist(connection):
    seed(connection)
    connection.execute(text("GRANT USAGE ON SCHEMA twitch_games TO anon"))
    connection.execute(text("GRANT SELECT ON twitch_games.question_candidates TO anon"))
    try:
        connection.execute(text("SET LOCAL ROLE anon"))
        assert (
            connection.execute(
                text("SELECT count(*) FROM twitch_games.question_candidates")
            ).scalar_one()
            == 0
        )
    finally:
        connection.execute(text("RESET ROLE"))


def test_database_transaction_rolls_back_on_failure(database):
    channel = str(uuid4().int)[:20]
    with pytest.raises(RuntimeError), database.transaction() as connection:
        connection.execute(
            text("INSERT INTO twitch_games.channels(id) VALUES (:id)"), {"id": channel}
        )
        raise RuntimeError("Deliberate isolated transaction failure")
    with database.transaction() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM twitch_games.channels WHERE id=:id"), {"id": channel}
            ).scalar_one()
            == 0
        )


def test_commit_survives_engine_disposal_and_new_connection(database):
    channel = str(uuid4().int)[:20]
    try:
        with database.transaction() as connection:
            connection.execute(
                text(
                    "INSERT INTO twitch_games.channels(id,display_name) "
                    "VALUES (:id,'persisted test')"
                ),
                {"id": channel},
            )
        database.engine.dispose()
        with database.transaction() as connection:
            assert (
                connection.execute(
                    text("SELECT display_name FROM twitch_games.channels WHERE id=:id"),
                    {"id": channel},
                ).scalar_one()
                == "persisted test"
            )
    finally:
        with database.transaction() as connection:
            connection.execute(
                text("DELETE FROM twitch_games.channels WHERE id=:id"), {"id": channel}
            )


def test_api_readiness_checks_real_postgres(database):
    url = database.engine.url.render_as_string(hide_password=False)
    with TestClient(create_app(Settings(database_url=SecretStr(url)))) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503  # Auth/gameplay still unimplemented.
        assert response.json()["dependencies"]["database"] == "ok"
        assert response.json()["dependencies"]["twitch_auth"] == "not_implemented"


def test_missing_migration_is_reported_without_automatic_ddl(database):
    url = database.engine.url.set(database="postgres").render_as_string(hide_password=False)
    other = Database(Settings(database_url=SecretStr(url)))
    try:
        assert other.status() == "migration_required"
        with other.transaction() as connection:
            assert (
                connection.execute(text("SELECT to_regnamespace('twitch_games')")).scalar_one()
                is None
            )
    finally:
        other.close()


def test_unavailable_database_is_sanitized(database):
    url = database.engine.url.set(database="does_not_exist_test").render_as_string(
        hide_password=False
    )
    other = Database(Settings(database_url=SecretStr(url)))
    try:
        assert other.status() == "unavailable"
    finally:
        other.close()


def test_concurrent_duplicate_score_is_rejected_by_database(database):
    channel = str(uuid4().int)[:20]
    ids = None
    try:
        with database.transaction() as connection:
            ids = seed(connection, channel=channel)
            submission_id = submit(connection, ids)
        barrier = Barrier(2)

        def attempt():
            try:
                with database.transaction() as connection:
                    barrier.wait(timeout=5)
                    award(connection, ids, submission_id)
                return "committed"
            except IntegrityError as error:
                assert error.orig.sqlstate == "23505"
                return "duplicate"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: attempt(), range(2)))
        assert sorted(outcomes) == ["committed", "duplicate"]
        with database.transaction() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT sum(points) FROM twitch_games.score_entries "
                        "WHERE channel_id=:channel"
                    ),
                    {"channel": channel},
                ).scalar_one()
                == 7
            )
    finally:
        if ids is not None:
            with database.transaction() as connection:
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
                ):
                    connection.execute(
                        text(f"DELETE FROM twitch_games.{table} WHERE channel_id=:channel"),
                        {"channel": channel},
                    )
                connection.execute(
                    text("DELETE FROM twitch_games.channels WHERE id=:channel"),
                    {"channel": channel},
                )
                connection.execute(text("DELETE FROM twitch_games.participants WHERE id='54321'"))


def test_long_unicode_quote_uses_character_offsets_and_bounded_digest_index(connection):
    ids = seed(connection)
    quote = "🍌" * 3000 + " spoon."
    start = quote.index("spoon")
    connection.execute(
        text("""
        INSERT INTO twitch_games.question_candidates
            (stream_id,channel_id,complete_quote,prompt,canonical_answer,quote_digest,
             blank_start,blank_end,accepted_aliases,review_status)
        VALUES (:stream,:channel,:quote,:prompt,'spoon',:digest,:start,:end,'[]','pending')
    """),
        {
            **ids,
            "quote": quote,
            "prompt": quote[:start] + "____.",
            "digest": hashlib.sha256(quote.encode()).hexdigest(),
            "start": start,
            "end": start + 5,
        },
    )
