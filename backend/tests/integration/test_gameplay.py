import base64
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from support.twitch_fixture import twitch_fixture

from twitch_games.application import create_app
from twitch_games.config import Settings
from twitch_games.store import one, rows, run

pytestmark = pytest.mark.integration
KEY = b"integration-only-extension-key-32bytes!"


def credential(channel, user=None, role="viewer"):
    return {
        "Authorization": "Bearer "
        + jwt.encode(
            {
                "exp": int(time.time()) + 3600,
                "channel_id": channel,
                "user_id": user,
                "opaque_user_id": "U" + (user or "opaque"),
                "role": role,
            },
            KEY,
        )
    }


@pytest.fixture
def game(database):
    channel = str(uuid4().int)[:15]
    with twitch_fixture() as (url, provider):
        settings = Settings(
            environment="test",
            database_url=database.engine.url.render_as_string(hide_password=False),
            twitch_client_id="fixture-app",
            twitch_client_secret="fixture-secret",
            twitch_redirect_uri="http://localhost:8000/api/v1/auth/twitch/callback",
            token_encryption_key=Fernet.generate_key().decode(),
            test_twitch_base_url=url,
            twitch_extension_client_id="fixture-extension",
            twitch_extension_secret=base64.b64encode(KEY).decode(),
            twitch_extension_owner_id="90001",
        )
        app = create_app(settings)
        try:
            with TestClient(app) as client:
                yield client, app, channel, credential(channel, channel, "broadcaster"), provider
        finally:
            with database.transaction() as c:
                for table in (
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
                ):
                    run(
                        c,
                        f"DELETE FROM twitch_games.{table} WHERE channel_id=:channel",
                        channel=channel,
                    )
                run(
                    c,
                    "DELETE FROM twitch_games.dashboard_sessions WHERE user_id=:channel",
                    channel=channel,
                )
                run(
                    c,
                    "DELETE FROM twitch_games.oauth_authorizations WHERE user_id=:channel",
                    channel=channel,
                )
                run(c, "DELETE FROM twitch_games.channels WHERE id=:channel", channel=channel)
                run(c, "DELETE FROM twitch_games.twitch_users WHERE id=:channel", channel=channel)
                run(
                    c,
                    "DELETE FROM twitch_games.participants WHERE id LIKE :prefix",
                    prefix=channel + "%",
                )


def prepare(game, text="I cannot believe we won this tournament with a spoon."):
    client, app, channel, owner, provider = game
    response = client.post(f"/api/v1/channels/{channel}/stream", headers=owner)
    assert response.status_code == 200, response.text
    stream = response.json()["stream_id"]
    body = {
        "batch_id": str(uuid4()),
        "source": "twitch_player_captions",
        "segments": [{"sequence": 0, "text": text, "observed_at": datetime.now(UTC).isoformat()}],
    }
    response = client.post(f"/api/v1/streams/{stream}/transcript-batches", json=body, headers=owner)
    assert response.status_code == 202, response.text
    candidates = client.get(f"/api/v1/streams/{stream}/questions", headers=owner).json()
    assert candidates
    return stream, body, candidates[0]


def start_round(game):
    client, app, channel, owner, provider = game
    _, _, candidate = prepare(game)
    body = {"request_id": str(uuid4()), "mode": "quote", "policy_id": "quote_v1"}
    started = client.post(f"/api/v1/channels/{channel}/games", json=body, headers=owner)
    assert started.status_code == 201, started.text
    state = started.json()
    opened = client.post(
        f"/api/v1/games/{state['game_id']}/rounds",
        headers=owner,
        json={"request_id": str(uuid4()), "expected_version": state["version"]},
    )
    assert opened.status_code == 201, opened.text
    return opened.json(), candidate


def expire(database, round_id):
    with database.transaction() as c:
        run(
            c,
            "UPDATE twitch_games.rounds SET opened_at=now()-interval '31 seconds', "
            "closes_at=now()-interval '1 second' WHERE id=:id",
            id=round_id,
        )


def test_transcript_idempotency_provenance_and_isolation(game, database):
    client, app, channel, owner, provider = game
    stream, body, candidate = prepare(game)
    assert (
        candidate["complete_quote"].replace(candidate["canonical_answer"], "____", 1)
        == candidate["prompt"]
    )
    duplicate = client.post(
        f"/api/v1/streams/{stream}/transcript-batches", json=body, headers=owner
    )
    assert duplicate.json()["status"] == "duplicate"
    body["segments"][0]["text"] += " changed"
    assert (
        client.post(
            f"/api/v1/streams/{stream}/transcript-batches", json=body, headers=owner
        ).status_code
        == 409
    )
    other = credential(str(int(channel) + 1), str(int(channel) + 1), "broadcaster")
    assert client.get(f"/api/v1/streams/{stream}/questions", headers=other).status_code == 404
    assert (
        client.get(
            f"/api/v1/streams/{stream}/questions", headers=credential(channel, channel + "1")
        ).status_code
        == 403
    )
    with database.transaction() as c:
        assert (
            one(
                c,
                "SELECT count(*) AS n FROM twitch_games.transcript_batches WHERE stream_id=:s",
                s=stream,
            )["n"]
            == 1
        )
        assert (
            one(
                c,
                "SELECT count(*) AS n FROM twitch_games.question_sources WHERE question_id=:q",
                q=candidate["question_id"],
            )["n"]
            == 1
        )


def test_complete_round_private_edits_alias_snapshot_shared_ranks_and_reset(game, database):
    client, app, channel, owner, provider = game
    _, _, candidate = prepare(game)
    canonical = candidate["canonical_answer"]
    assert (
        client.put(
            f"/api/v1/channels/{channel}/aliases",
            headers=owner,
            json={"canonical": canonical, "aliases": ["approved alias"]},
        ).status_code
        == 200
    )
    started = client.post(
        f"/api/v1/channels/{channel}/games",
        headers=owner,
        json={"request_id": str(uuid4()), "mode": "quote", "policy_id": "quote_v1"},
    ).json()
    command = {"request_id": str(uuid4()), "expected_version": started["version"]}
    state = client.post(
        f"/api/v1/games/{started['game_id']}/rounds", headers=owner, json=command
    ).json()
    round_id = state["round"]["round_id"]
    assert "canonical_answer" not in state["round"]
    assert (
        datetime.fromisoformat(state["round"]["closes_at"])
        - datetime.fromisoformat(state["round"]["opened_at"])
    ).total_seconds() == 30
    assert (
        client.post(
            f"/api/v1/games/{started['game_id']}/rounds", headers=owner, json=command
        ).json()
        == state
    )
    client.put(
        f"/api/v1/channels/{channel}/aliases",
        headers=owner,
        json={"canonical": canonical, "aliases": []},
    )
    viewer = credential(channel, channel + "1")
    request = {"request_id": str(uuid4()), "answer": "wrong"}
    assert (
        client.post(f"/api/v1/rounds/{round_id}/answers", headers=viewer, json=request).status_code
        == 202
    )
    edited = {"request_id": str(uuid4()), "answer": "approved alias"}
    receipt = client.post(f"/api/v1/rounds/{round_id}/answers", headers=viewer, json=edited)
    assert receipt.status_code == 202, receipt.text
    assert set(receipt.json()) == {
        "submission_id",
        "round_id",
        "request_id",
        "status",
        "received_at",
    }
    assert (
        client.post(f"/api/v1/rounds/{round_id}/answers", headers=viewer, json=edited).json()
        == receipt.json()
    )
    edited["answer"] = "different"
    assert (
        client.post(f"/api/v1/rounds/{round_id}/answers", headers=viewer, json=edited).status_code
        == 409
    )
    own = client.get(f"/api/v1/rounds/{round_id}/me", headers=viewer).json()
    assert own["answer"] == "approved alias" and own["result"] is None
    second = credential(channel, channel + "2")
    typo = canonical[:-2] + canonical[-1] + canonical[-2]
    assert (
        client.post(
            f"/api/v1/rounds/{round_id}/answers",
            headers=second,
            json={"request_id": str(uuid4()), "answer": typo},
        ).status_code
        == 202
    )
    assert client.get(f"/api/v1/rounds/{round_id}/me", headers=second).json()["answer"] == typo
    assert (
        client.post(
            f"/api/v1/rounds/{round_id}/close",
            headers=owner,
            json={"request_id": str(uuid4()), "expected_version": state["version"]},
        ).status_code
        == 409
    )
    expire(database, round_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: app.state.game_service.close_due(), range(2)))
    results = client.get(f"/api/v1/channels/{channel}/game-state", headers=viewer).json()
    assert results["round"]["phase"] == "results"
    assert results["round"]["canonical_answer"] == canonical
    assert (
        client.get(f"/api/v1/rounds/{round_id}/me", headers=viewer).json()["result"][
            "awarded_points"
        ]
        == 1
    )
    leaderboard = client.get(f"/api/v1/games/{state['game_id']}/leaderboard", headers=viewer).json()
    assert [entry["rank"] for entry in leaderboard["entries"]] == [1, 1]
    assert [entry["points"] for entry in leaderboard["entries"]] == [1, 1]
    assert (
        client.post(
            f"/api/v1/rounds/{round_id}/answers",
            headers=viewer,
            json={"request_id": str(uuid4()), "answer": canonical},
        ).status_code
        == 409
    )
    # A retry of an accepted request remains a receipt after the deadline.
    assert (
        client.post(f"/api/v1/rounds/{round_id}/answers", headers=viewer, json=request).status_code
        == 202
    )
    ended = client.post(
        f"/api/v1/games/{state['game_id']}/end",
        headers=owner,
        json={"request_id": str(uuid4()), "expected_version": results["version"]},
    )
    assert ended.status_code == 200, ended.text
    assert client.get(f"/api/v1/games/{state['game_id']}/leaderboard", headers=viewer).json()[
        "final"
    ]
    new = client.post(
        f"/api/v1/channels/{channel}/games",
        headers=owner,
        json={"request_id": str(uuid4()), "mode": "quote", "policy_id": "quote_v1"},
    ).json()
    assert new["version"] > ended.json()["version"]
    assert (
        client.get(f"/api/v1/games/{new['game_id']}/leaderboard", headers=viewer).json()["entries"]
        == []
    )
    with database.transaction() as c:
        assert (
            one(
                c,
                "SELECT count(*) AS n FROM twitch_games.score_entries WHERE round_id=:r",
                r=round_id,
            )["n"]
            == 2
        )
        assert [
            row["raw_answer"]
            for row in rows(
                c,
                "SELECT raw_answer FROM twitch_games.submissions "
                "WHERE round_id=:r AND participant_id=:u ORDER BY revision",
                r=round_id,
                u=channel + "1",
            )
        ] == ["wrong", "approved alias"]


def test_concurrent_request_retries_and_stale_controller(game, database):
    client, app, channel, owner, provider = game
    state, candidate = start_round(game)
    round_id = state["round"]["round_id"]
    viewer = credential(channel, channel + "1")
    body = {"request_id": str(uuid4()), "answer": candidate["canonical_answer"]}
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    f"/api/v1/rounds/{round_id}/answers", headers=viewer, json=body
                ),
                range(5),
            )
        )
    assert all(response.status_code == 202 for response in responses), [r.text for r in responses]
    assert len({r.json()["submission_id"] for r in responses}) == 1
    assert (
        client.post(
            f"/api/v1/games/{state['game_id']}/rounds",
            headers=owner,
            json={"request_id": str(uuid4()), "expected_version": 0},
        ).json()["error"]["code"]
        == "stale_state"
    )
    spectator = credential(channel)
    assert (
        client.post(f"/api/v1/rounds/{round_id}/answers", headers=spectator, json=body).status_code
        == 403
    )
    other = credential(str(int(channel) + 1), channel + "1")
    assert client.get(f"/api/v1/rounds/{round_id}/me", headers=other).status_code == 404
    with database.transaction() as c:
        assert (
            one(
                c,
                "SELECT count(*) AS n FROM twitch_games.submissions WHERE round_id=:r",
                r=round_id,
            )["n"]
            == 1
        )


def test_pubsub_is_minimal_signed_and_retries(game, database):
    client, app, channel, owner, provider = game
    provider["pubsub_unavailable"] = True
    state, candidate = start_round(game)
    with database.transaction() as c:
        run(
            c,
            "UPDATE twitch_games.state_notifications SET next_attempt_at='epoch' "
            "WHERE channel_id=:c",
            c=channel,
        )
    app.state.publisher.publish_one()
    with database.transaction() as c:
        record = one(
            c, "SELECT * FROM twitch_games.state_notifications WHERE channel_id=:c", c=channel
        )
        assert record["attempts"] >= 1
        run(
            c,
            "UPDATE twitch_games.state_notifications SET next_attempt_at='epoch' "
            "WHERE channel_id=:c",
            c=channel,
        )
    provider["pubsub_unavailable"] = False
    app.state.publisher.publish_one()
    message = provider["messages"][-1]
    assert message["client_id"] == "fixture-extension"
    decoded = jwt.decode(message["authorization"][7:], KEY, algorithms=["HS256"])
    assert decoded["role"] == "external" and decoded["user_id"] == "90001"
    import json

    notification = json.loads(message["body"]["message"])
    assert notification == {
        "event": "game_state_changed",
        "channel_id": channel,
        "version": state["version"],
    }
    assert candidate["canonical_answer"] not in message["body"]["message"]
    count = len(provider["messages"])
    app.state.publisher.publish_one()
    assert len(provider["messages"]) == count


def test_bulk_scoring_zero_points_and_own_rank_outside_top_100(game, database):
    client, app, channel, owner, provider = game
    state, candidate = start_round(game)
    round_id = state["round"]["round_id"]
    with database.transaction() as c:
        for number in range(1, 151):
            user = channel + str(number).zfill(3)
            run(
                c,
                "INSERT INTO twitch_games.participants(id,display_name) VALUES (:id,:name)",
                id=user,
                name="Participant " + str(number),
            )
            run(
                c,
                "INSERT INTO twitch_games.submissions "
                "(round_id,game_id,channel_id,participant_id,request_id,raw_answer) "
                "VALUES (:round,:game,:channel,:user,:request,:answer)",
                round=round_id,
                game=state["game_id"],
                channel=channel,
                user=user,
                request=uuid4(),
                answer=candidate["canonical_answer"] if number <= 50 else "wrong",
            )
        # Later edits to the candidate must not change a round's frozen source quote.
        run(
            c,
            "UPDATE twitch_games.question_candidates SET "
            "complete_quote=replace(complete_quote,'won','ran'),prompt=replace(prompt,'won','ran') "
            "WHERE id=:id",
            id=candidate["question_id"],
        )
    expire(database, round_id)
    app.state.game_service.close_due()
    app.state.game_service.close_due()
    result = client.get(f"/api/v1/channels/{channel}/game-state", headers=owner).json()
    assert result["round"]["complete_quote"] == candidate["complete_quote"]
    viewer = credential(channel, channel + "150")
    board = client.get(f"/api/v1/games/{state['game_id']}/leaderboard", headers=viewer).json()
    assert len(board["entries"]) == 100
    assert board["own_entry"]["rank"] == 51 and board["own_entry"]["points"] == 0
    assert board["own_entry"] not in board["entries"]
    with database.transaction() as c:
        total = one(
            c,
            "SELECT count(*) AS n,sum(points) AS points FROM twitch_games.score_entries "
            "WHERE round_id=:round",
            round=round_id,
        )
        assert total["n"] == 150 and total["points"] == 50


def test_fragment_ordering_timestamp_validation_and_ended_stream(game, database):
    client, app, channel, owner, provider = game
    stream = client.post(f"/api/v1/channels/{channel}/stream", headers=owner).json()["stream_id"]
    observed = datetime.now(UTC).isoformat()
    batch = {
        "batch_id": str(uuid4()),
        "source": "twitch_player_captions",
        "segments": [
            {"sequence": 5, "text": "with a silver spoon.", "observed_at": observed},
            {
                "sequence": 1,
                "text": "I cannot believe we won this tournament",
                "observed_at": observed,
            },
        ],
    }
    path = f"/api/v1/streams/{stream}/transcript-batches"
    assert client.post(path, headers=owner, json=batch).status_code == 202
    question = client.get(f"/api/v1/streams/{stream}/questions", headers=owner).json()[0]
    assert (
        question["complete_quote"] == "I cannot believe we won this tournament with a silver spoon."
    )
    assert len(question["source"]["segment_ids"]) == 2
    batch["batch_id"] = str(uuid4())
    batch["segments"][0]["sequence"] = 1
    assert client.post(path, headers=owner, json=batch).status_code == 422
    batch["segments"][0]["sequence"] = 5
    batch["segments"][0]["observed_at"] = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
    assert client.post(path, headers=owner, json=batch).status_code == 422
    with database.transaction() as c:
        run(c, "UPDATE twitch_games.streams SET ended_at=now() WHERE id=:id", id=stream)
    assert client.post(path, headers=owner, json=batch).status_code == 409
