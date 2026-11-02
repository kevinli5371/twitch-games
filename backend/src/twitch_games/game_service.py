"""Transactional, channel-isolated quote games. PostgreSQL is the game authority."""

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import text

from twitch_games.contracts.models import PublicGameState
from twitch_games.errors import GameError
from twitch_games.matching import match_answer, normalize_answer
from twitch_games.policy import POLICY, POLICY_ID
from twitch_games.quote_engine import GENERATOR_VERSION, WORD, Passage, choose_quotes
from twitch_games.store import one, rows, run


def json_text(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def missing():
    raise GameError("not_found", "Resource not found in this channel", 404)


class GameService:
    def __init__(self, database, auth):
        self.database, self.auth = database, auth

    def db(self):
        if self.database is None:
            raise GameError("not_configured", "Database configuration is required", 503)
        return self.database

    def lock_channel(self, c, identity, permission="live_control"):
        if identity.role == "broadcaster":
            identity.owner(identity.channel_id)
            run(
                c,
                "INSERT INTO twitch_games.channels(id) VALUES (:id) ON CONFLICT DO NOTHING",
                id=identity.channel_id,
            )
        record = one(
            c, "SELECT * FROM twitch_games.channels WHERE id=:id FOR UPDATE", id=identity.channel_id
        )
        if not record:
            missing()
        self.auth.require_permission(c, identity, identity.channel_id, permission)
        return record

    def resource(self, c, table, resource_id, identity, owner=False):
        if owner:
            self.auth.require_permission(c, identity, identity.channel_id, "question_review")
        record = one(
            c,
            f"SELECT * FROM twitch_games.{table} WHERE id=:id AND channel_id=:channel",
            id=resource_id,
            channel=identity.channel_id,
        )
        if record is None:
            missing()
        return record

    def latest_stream(self, c, channel):
        return one(
            c,
            "SELECT * FROM twitch_games.streams WHERE channel_id=:channel AND ended_at "
            "IS NULL ORDER BY created_at DESC LIMIT 1",
            channel=channel,
        )

    def state(self, c, channel):
        channel_row = one(c, "SELECT version FROM twitch_games.channels WHERE id=:id", id=channel)
        game = one(
            c,
            "SELECT * FROM twitch_games.game_sessions WHERE channel_id=:channel ORDER "
            "BY created_at DESC,id DESC LIMIT 1",
            channel=channel,
        )
        result = {
            "channel_id": channel,
            "game_id": str(game["id"]) if game else None,
            "status": game["status"] if game else "idle",
            "version": channel_row["version"] if channel_row else 0,
            "server_time": one(c, "SELECT clock_timestamp() AS now")["now"],
            "round": None,
        }
        if game:
            round_row = one(
                c,
                "SELECT r.* FROM twitch_games.rounds r WHERE r.game_id=:game ORDER BY "
                "r.created_at DESC,r.id DESC LIMIT 1",
                game=game["id"],
            )
            if round_row:
                result["round"] = {
                    "round_id": str(round_row["id"]),
                    "phase": round_row["phase"],
                    "prompt": round_row["prompt_snapshot"],
                }
                if round_row["phase"] == "results":
                    result["round"].update(
                        complete_quote=round_row["complete_quote_snapshot"],
                        canonical_answer=round_row["canonical_answer_snapshot"],
                    )
                else:
                    result["round"].update(
                        opened_at=round_row["opened_at"], closes_at=round_row["closes_at"]
                    )
        return PublicGameState.model_validate(result).model_dump(mode="json")

    def public_state(self, identity, channel):
        identity.viewer(channel)
        with self.db().transaction() as c:
            # Snapshot queries use one repeatable view, even during concurrent transitions.
            run(c, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            if identity.source == "dashboard":
                self.auth.require_permission(c, identity, channel)
            return self.state(c, channel)

    def bump(self, c, channel):
        version = one(
            c,
            "UPDATE twitch_games.channels SET version=version+1 WHERE id=:id RETURNING version",
            id=channel,
        )["version"]
        run(
            c,
            "UPDATE twitch_games.game_sessions SET version=:version WHERE "
            "channel_id=:channel AND status='active'",
            version=version,
            channel=channel,
        )
        run(
            c,
            "INSERT INTO twitch_games.state_notifications(channel_id,version) VALUES "
            "(:channel,:v) ON CONFLICT(channel_id) DO UPDATE SET "
            "version=excluded.version",
            channel=channel,
            v=version,
        )
        return version

    def command(self, identity, operation, target, body, execute):
        payload = body.model_dump(mode="json")
        checksum = hashlib.sha256(json_text([operation, str(target), payload]).encode()).hexdigest()
        with self.db().transaction() as c:
            channel = self.lock_channel(c, identity)
            previous = one(
                c,
                "SELECT * FROM twitch_games.command_receipts WHERE channel_id=:channel AND "
                "request_id=:request",
                channel=identity.channel_id,
                request=body.request_id,
            )
            if previous:
                if previous["digest"] != checksum:
                    raise GameError(
                        "request_conflict", "Request ID was already used for another command"
                    )
                return previous["response"]
            expected = getattr(body, "expected_version", None)
            if expected is not None and expected != channel["version"]:
                raise GameError(
                    "stale_state", "Refresh the current state before sending this command"
                )
            execute(c)
            self.bump(c, identity.channel_id)
            response = self.state(c, identity.channel_id)
            run(
                c,
                "INSERT INTO twitch_games.command_receipts(channel_id,request_id,digest,"
                "response) VALUES (:channel,:request,:digest,CAST(:response AS jsonb))",
                channel=identity.channel_id,
                request=body.request_id,
                digest=checksum,
                response=json_text(response),
            )
            return response

    def connect_stream(self, identity, channel):
        identity.viewer(channel)
        with self.db().transaction() as c:
            self.auth.require_permission(c, identity, channel, "settings")
        provider = self.auth.provider
        provider.user(channel)  # Establishes/validates an application access token.
        data = provider.call(
            "GET",
            provider.helix + "/streams",
            params={"user_id": channel},
            headers={
                "Authorization": "Bearer " + provider.app_token,
                "Client-Id": provider.settings.twitch_client_id,
            },
        )
        streams = data.get("data", [])
        if not streams or streams[0].get("user_id") != channel:
            raise GameError("stream_unavailable", "This channel must be live to connect a stream")
        stream = streams[0]
        with self.db().transaction() as c:
            self.lock_channel(c, identity, "settings")
            current = self.latest_stream(c, channel)
            if current and current["twitch_stream_id"] == stream["id"]:
                return {"stream_id": str(current["id"]), "twitch_stream_id": stream["id"]}
            if one(
                c,
                "SELECT id FROM twitch_games.game_sessions WHERE channel_id=:channel AND "
                "status='active'",
                channel=channel,
            ):
                raise GameError("game_active", "End the active game before changing streams")
            run(
                c,
                "UPDATE twitch_games.streams SET ended_at=clock_timestamp() WHERE "
                "channel_id=:channel AND ended_at IS NULL",
                channel=channel,
            )
            record = one(
                c,
                "INSERT INTO twitch_games.streams(channel_id,twitch_stream_id,started_at) "
                "VALUES (:channel,:twitch,:started) ON CONFLICT(channel_id,"
                "twitch_stream_id) DO UPDATE SET ended_at=NULL RETURNING id",
                channel=channel,
                twitch=stream["id"],
                started=datetime.fromisoformat(stream["started_at"].replace("Z", "+00:00")),
            )
            return {"stream_id": str(record["id"]), "twitch_stream_id": stream["id"]}

    def intake(self, identity, stream_id, batch):
        checksum = hashlib.sha256(json_text(batch.model_dump(mode="json")).encode()).hexdigest()
        if len({s.sequence for s in batch.segments}) != len(batch.segments):
            raise GameError(
                "validation_error", "Segment sequence numbers must be unique in a batch", 422
            )
        if any(not segment.text.strip() for segment in batch.segments):
            raise GameError("validation_error", "Caption text cannot be blank", 422)
        with self.db().transaction() as c:
            self.lock_channel(c, identity, "settings")
            stream = self.resource(c, "streams", stream_id, identity)
            if stream["ended_at"] is not None:
                raise GameError("stream_unavailable", "Caption stream is no longer current")
            previous = one(
                c, "SELECT * FROM twitch_games.transcript_batches WHERE id=:id", id=batch.batch_id
            )
            if previous:
                if previous["stream_id"] != stream["id"] or previous["payload_digest"] != checksum:
                    raise GameError(
                        "request_conflict", "Batch ID was already used with different content"
                    )
                return {"batch_id": str(batch.batch_id), "status": "duplicate"}
            now = one(c, "SELECT clock_timestamp() AS now")["now"]
            if any(
                (segment.observed_at - now).total_seconds() > 30
                or (stream["started_at"] - segment.observed_at).total_seconds() > 60
                for segment in batch.segments
            ):
                raise GameError(
                    "validation_error", "Caption timestamps are outside this stream", 422
                )
            run(
                c,
                "INSERT INTO twitch_games.transcript_batches(id,stream_id,channel_id,"
                "source,payload_digest) VALUES (:id,:stream,:channel,:source,:digest)",
                id=batch.batch_id,
                stream=stream_id,
                channel=identity.channel_id,
                source=batch.source,
                digest=checksum,
            )
            for segment in sorted(batch.segments, key=lambda segment: segment.sequence):
                run(
                    c,
                    "INSERT INTO twitch_games.transcript_segments (batch_id,stream_id,"
                    "channel_id,sequence,text,observed_at) VALUES (:batch,:stream,:channel,"
                    ":seq,:text,:observed)",
                    batch=batch.batch_id,
                    stream=stream_id,
                    channel=identity.channel_id,
                    seq=segment.sequence,
                    text=segment.text,
                    observed=segment.observed_at,
                )
            self.generate(c, stream_id, identity.channel_id)
        return {"batch_id": str(batch.batch_id), "status": "received"}

    def generate(self, c, stream_id, channel):
        records = rows(
            c,
            "SELECT id,text,observed_at FROM twitch_games.transcript_segments WHERE "
            "stream_id=:stream ORDER BY observed_at DESC,received_at DESC,sequence "
            "DESC,id DESC LIMIT 200",
            stream=stream_id,
        )
        passages, parts, sources = [], [], []
        for record in reversed(records):
            if parts and len(" ".join(parts)) + len(record["text"]) + 1 > 4000:
                parts, sources = [], []
            parts.append(record["text"])
            sources.append(str(record["id"]))
            passage = " ".join(parts)
            if len(WORD.findall(passage)) >= 8:
                passages.append(Passage(passage, tuple(sources)))
                parts, sources = [], []
        existing = rows(
            c,
            "SELECT canonical_answer,quote_digest FROM "
            "twitch_games.question_candidates WHERE stream_id=:stream ORDER BY "
            "created_at DESC LIMIT 2000",
            stream=stream_id,
        )
        used = {record["canonical_answer"] for record in existing}
        digests = {record["quote_digest"] for record in existing}
        for candidate in choose_quotes(passages, used, limit=20):
            if candidate.digest in digests:
                continue
            question = one(
                c,
                "INSERT INTO twitch_games.question_candidates (stream_id,channel_id,"
                "complete_quote,prompt,canonical_answer,quote_digest,blank_start,blank_end,"
                "accepted_aliases,review_status,generator_version,selection_weight) VALUES "
                "(:stream,:channel,:quote,:prompt,:answer,:digest,:start,:end,'[]',"
                "'approved',:generator,:weight) ON CONFLICT DO NOTHING RETURNING id",
                stream=stream_id,
                channel=channel,
                quote=candidate.complete_quote,
                prompt=candidate.prompt,
                answer=candidate.canonical_answer,
                digest=candidate.digest,
                start=candidate.blank_start,
                end=candidate.blank_end,
                generator=GENERATOR_VERSION,
                weight=candidate.weight,
            )
            if question:
                for segment in candidate.segment_ids:
                    run(
                        c,
                        "INSERT INTO twitch_games.question_sources(question_id,segment_id,"
                        "stream_id,channel_id) VALUES (:question,:segment,:stream,:channel)",
                        question=question["id"],
                        segment=segment,
                        stream=stream_id,
                        channel=channel,
                    )
                digests.add(candidate.digest)

    def questions(self, c, stream_id):
        records = rows(
            c,
            "SELECT q.*,array_agg(s.id ORDER BY s.observed_at,s.sequence) AS segments,"
            "max(s.received_at) AS received FROM twitch_games.question_candidates q "
            "JOIN twitch_games.question_sources qs ON qs.question_id=q.id JOIN "
            "twitch_games.transcript_segments s ON s.id=qs.segment_id WHERE "
            "q.stream_id=:stream AND q.review_status='approved' AND NOT EXISTS (SELECT "
            "1 FROM twitch_games.rounds r WHERE r.question_id=q.id) GROUP BY q.id "
            "ORDER BY q.selection_weight DESC,q.created_at,q.id LIMIT 50",
            stream=stream_id,
        )
        return [
            {
                "question_id": str(r["id"]),
                "complete_quote": r["complete_quote"],
                "prompt": r["prompt"],
                "canonical_answer": r["canonical_answer"],
                "accepted_aliases": r["accepted_aliases"],
                "source": {
                    "stream_id": str(stream_id),
                    "segment_ids": [str(s) for s in r["segments"]],
                    "received_at": r["received"],
                },
            }
            for r in records
        ]

    def dashboard(self, identity, channel):
        identity.viewer(channel)
        with self.db().transaction() as c:
            run(c, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            permissions = self.auth.require_permission(c, identity, channel)
            stream = self.latest_stream(c, channel)
            last = (
                one(
                    c,
                    "SELECT max(received_at) AS received FROM twitch_games.transcript_segments "
                    "WHERE stream_id=:stream",
                    stream=stream["id"],
                )
                if stream
                else None
            )
            received = last["received"] if last else None
            status = (
                "not_connected"
                if not stream
                else "waiting"
                if not received
                else "receiving"
                if (datetime.now(UTC) - received).total_seconds() <= 30
                else "stale"
            )
            state = self.state(c, channel)
            count = (
                one(
                    c,
                    "SELECT count(DISTINCT participant_id) AS n FROM twitch_games.submissions "
                    "WHERE round_id=:round",
                    round=state["round"]["round_id"],
                )["n"]
                if state["round"]
                else 0
            )
            return {
                "channel_id": channel,
                "stream_id": str(stream["id"]) if stream else None,
                "transcript": {"status": status, "last_received_at": received},
                "candidates": self.questions(c, stream["id"])
                if stream and "question_review" in permissions
                else [],
                "game": state,
                "submission_count": count,
            }

    def aliases(self, identity, channel, body=None):
        identity.viewer(channel)
        with self.db().transaction() as c:
            self.lock_channel(c, identity, "question_review")
            if body:
                run(
                    c,
                    "INSERT INTO twitch_games.answer_aliases(channel_id,canonical,aliases) "
                    "VALUES (:channel,:canonical,CAST(:aliases AS jsonb)) ON "
                    "CONFLICT(channel_id,canonical) DO UPDATE SET aliases=excluded.aliases",
                    channel=channel,
                    canonical=body.canonical,
                    aliases=json_text(body.aliases),
                )
            return [
                dict(r)
                for r in rows(
                    c,
                    "SELECT canonical,aliases FROM twitch_games.answer_aliases WHERE "
                    "channel_id=:channel ORDER BY canonical LIMIT 1000",
                    channel=channel,
                )
            ]

    def start(self, identity, channel, body):
        identity.viewer(channel)

        def execute(c):
            if body.policy_id != POLICY_ID:
                raise GameError("unsupported_policy", "Use the quote_v1 scoring policy", 422)
            if one(
                c,
                "SELECT id FROM twitch_games.game_sessions WHERE channel_id=:channel AND "
                "status='active'",
                channel=channel,
            ):
                raise GameError("game_active", "A game is already active")
            stream = self.latest_stream(c, channel)
            if not stream:
                raise GameError("stream_unavailable", "Connect the current live stream first")
            run(
                c,
                "INSERT INTO twitch_games.game_sessions (stream_id,channel_id,mode,status,"
                "policy_id,policy_snapshot,version,started_at) VALUES (:stream,:channel,"
                "'quote','active',:policy,CAST(:snapshot AS jsonb),0,clock_timestamp())",
                stream=stream["id"],
                channel=channel,
                policy=POLICY_ID,
                snapshot=json_text(POLICY),
            )

        return self.command(identity, "start", channel, body, execute)

    def open_round(self, identity, game_id, body):
        def execute(c):
            game = self.resource(c, "game_sessions", game_id, identity)
            if game["status"] != "active":
                raise GameError("game_ended", "This game is no longer active")
            if one(
                c,
                "SELECT id FROM twitch_games.rounds WHERE game_id=:game AND phase NOT IN "
                "('results','cancelled')",
                game=game_id,
            ):
                raise GameError("round_active", "Wait for the current round to finish")
            question = one(
                c,
                "SELECT * FROM twitch_games.question_candidates q WHERE stream_id=:stream "
                "AND review_status='approved' AND (CAST(:question AS uuid) IS NULL OR "
                "id=CAST(:question AS uuid)) AND NOT EXISTS(SELECT 1 FROM "
                "twitch_games.rounds r WHERE r.question_id=q.id) ORDER BY selection_weight "
                "DESC,created_at,id LIMIT 1",
                stream=game["stream_id"],
                question=body.question_id,
            )
            if not question:
                raise GameError(
                    "transcript_unavailable", "Waiting for a new usable quote from this stream"
                )
            alias = one(
                c,
                "SELECT aliases FROM twitch_games.answer_aliases WHERE channel_id=:channel "
                "AND canonical=:canonical",
                channel=identity.channel_id,
                canonical=normalize_answer(question["canonical_answer"]),
            )
            aliases = list(
                dict.fromkeys(question["accepted_aliases"] + (alias["aliases"] if alias else []))
            )
            run(
                c,
                "INSERT INTO twitch_games.rounds (game_id,stream_id,channel_id,question_id,"
                "phase,version,prompt_snapshot,canonical_answer_snapshot,"
                "accepted_aliases_snapshot,scoring_policy_id,policy_snapshot,"
                "complete_quote_snapshot,opened_at,closes_at) VALUES (:game,:stream,"
                ":channel,:question,'answering',0,:prompt,:answer,CAST(:aliases AS jsonb),"
                ":policy,CAST(:snapshot AS jsonb),:quote,statement_timestamp(),"
                "statement_timestamp()+interval '30 seconds')",
                game=game_id,
                stream=game["stream_id"],
                channel=identity.channel_id,
                question=question["id"],
                prompt=question["prompt"],
                answer=question["canonical_answer"],
                aliases=json_text(aliases),
                policy=POLICY_ID,
                snapshot=json_text(POLICY),
                quote=question["complete_quote"],
            )

        return self.command(identity, "open", game_id, body, execute)

    def receipt(self, record):
        return {
            "submission_id": str(record["id"]),
            "round_id": str(record["round_id"]),
            "request_id": str(record["request_id"]),
            "status": "received",
            "received_at": record["received_at"],
        }

    def submit(self, identity, round_id, body):
        identity.viewer(identity.channel_id, participating=True)
        # Names come from Twitch, never from submitted payloads; cache after first verified use.
        with self.db().transaction() as c:
            self.resource(c, "rounds", round_id, identity)
            participant = one(
                c, "SELECT id FROM twitch_games.participants WHERE id=:id", id=identity.user_id
            )
        name = None if participant else self.auth.provider.user(identity.user_id)["display_name"]
        with self.db().transaction() as c:
            round_row = one(
                c,
                "SELECT * FROM twitch_games.rounds WHERE id=:id AND channel_id=:channel FOR UPDATE",
                id=round_id,
                channel=identity.channel_id,
            )
            if not round_row:
                missing()
            previous = one(
                c,
                "SELECT * FROM twitch_games.submissions WHERE round_id=:round AND "
                "participant_id=:user AND request_id=:request",
                round=round_id,
                user=identity.user_id,
                request=body.request_id,
            )
            if previous:
                if previous["raw_answer"] != body.answer:
                    raise GameError(
                        "request_conflict", "Use a new request ID when editing an answer"
                    )
                return self.receipt(previous)
            now = one(c, "SELECT clock_timestamp() AS now")["now"]
            if round_row["phase"] != "answering" or now >= round_row["closes_at"]:
                raise GameError("round_closed", "This round no longer accepts answers")
            run(
                c,
                "INSERT INTO twitch_games.participants(id,display_name) VALUES (:id,:name) "
                "ON CONFLICT DO NOTHING",
                id=identity.user_id,
                name=name,
            )
            record = one(
                c,
                "INSERT INTO twitch_games.submissions (round_id,game_id,channel_id,"
                "participant_id,request_id,raw_answer,received_at) VALUES (:round,:game,"
                ":channel,:user,:request,:answer,:received) RETURNING *",
                round=round_id,
                game=round_row["game_id"],
                channel=identity.channel_id,
                user=identity.user_id,
                request=body.request_id,
                answer=body.answer,
                received=now,
            )
            return self.receipt(record)

    def score(self, c, round_id, channel):
        record = one(
            c,
            "SELECT * FROM twitch_games.rounds WHERE id=:id AND channel_id=:channel FOR UPDATE",
            id=round_id,
            channel=channel,
        )
        if not record or record["phase"] == "results":
            return False
        now = one(c, "SELECT clock_timestamp() AS now")["now"]
        if record["phase"] != "answering" or now < record["closes_at"]:
            raise GameError("round_active", "The 30-second answer window has not ended")
        submissions = rows(
            c,
            "SELECT DISTINCT ON(participant_id) * FROM twitch_games.submissions WHERE "
            "round_id=:round ORDER BY participant_id,revision DESC",
            round=round_id,
        )
        cache, awards = {}, []
        for submission in submissions:
            normalized = normalize_answer(submission["raw_answer"])
            if normalized not in cache:
                cache[normalized] = match_answer(
                    submission["raw_answer"],
                    record["canonical_answer_snapshot"],
                    tuple(record["accepted_aliases_snapshot"]),
                ).correct
            correct = cache[normalized]
            awards.append(
                {
                    "submission": submission["id"],
                    "round": round_id,
                    "game": record["game_id"],
                    "channel": channel,
                    "user": submission["participant_id"],
                    "outcome": "correct" if correct else "incorrect",
                    "points": 1 if correct else 0,
                    "policy": record["scoring_policy_id"],
                }
            )
        if awards:
            c.execute(
                text("""
                INSERT INTO twitch_games.score_entries
                    (submission_id,round_id,game_id,channel_id,participant_id,
                     outcome,points,scoring_policy_id)
                VALUES (:submission,:round,:game,:channel,:user,:outcome,:points,:policy)
                ON CONFLICT (round_id,participant_id) DO NOTHING
            """),
                awards,
            )
        run(
            c,
            "UPDATE twitch_games.rounds SET phase='results',"
            "closed_at=clock_timestamp(),version=version+1 WHERE id=:id",
            id=round_id,
        )
        return True

    def close_round(self, identity, round_id, body):
        def execute(c):
            self.resource(c, "rounds", round_id, identity)
            self.score(c, round_id, identity.channel_id)

        return self.command(identity, "close", round_id, body, execute)

    def close_due(self):
        if self.database is None:
            return
        with self.db().transaction() as c:
            due = rows(
                c,
                "SELECT id,channel_id FROM twitch_games.rounds WHERE phase='answering' AND "
                "closes_at<=clock_timestamp() ORDER BY closes_at LIMIT 100",
            )
        for item in due:
            with self.db().transaction() as c:
                # Lock channel before round; submissions only lock the round.
                one(
                    c,
                    "SELECT id FROM twitch_games.channels WHERE id=:id FOR UPDATE",
                    id=item["channel_id"],
                )
                if self.score(c, item["id"], item["channel_id"]):
                    self.bump(c, item["channel_id"])

    def end(self, identity, game_id, body):
        def execute(c):
            game = self.resource(c, "game_sessions", game_id, identity)
            if game["status"] != "active":
                raise GameError("game_ended", "This game has already ended")
            if one(
                c,
                "SELECT id FROM twitch_games.rounds WHERE game_id=:game AND phase NOT IN "
                "('results','cancelled')",
                game=game_id,
            ):
                raise GameError(
                    "round_active", "Wait for the current round's results before ending the game"
                )
            run(
                c,
                "UPDATE twitch_games.game_sessions SET status='ended',"
                "ended_at=clock_timestamp() WHERE id=:id",
                id=game_id,
            )

        return self.command(identity, "end", game_id, body, execute)

    def own(self, identity, round_id):
        identity.viewer(identity.channel_id, participating=True)
        with self.db().transaction() as c:
            run(c, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            record = self.resource(c, "rounds", round_id, identity)
            submission = one(
                c,
                "SELECT * FROM twitch_games.submissions WHERE round_id=:round AND "
                "participant_id=:user ORDER BY revision DESC LIMIT 1",
                round=round_id,
                user=identity.user_id,
            )
            score = (
                one(
                    c,
                    "SELECT * FROM twitch_games.score_entries WHERE round_id=:round AND "
                    "participant_id=:user",
                    round=round_id,
                    user=identity.user_id,
                )
                if record["phase"] == "results"
                else None
            )
            result = {
                "round_id": str(round_id),
                "receipt": self.receipt(submission) if submission else None,
                "result": None,
                "answer": submission["raw_answer"] if submission else None,
            }
            if score:
                result["result"] = {
                    "round_id": str(round_id),
                    "submission_id": str(score["submission_id"]),
                    "outcome": score["outcome"],
                    "awarded_points": score["points"],
                    "scoring_policy_id": score["scoring_policy_id"],
                }
            return result

    def leaderboard(self, identity, game_id):
        with self.db().transaction() as c:
            run(c, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            game = self.resource(c, "game_sessions", game_id, identity)
            if identity.source == "dashboard":
                self.auth.require_permission(c, identity, identity.channel_id)
            ranked = rows(
                c,
                "WITH totals AS (SELECT participant_id,SUM(points)::int AS points FROM "
                "twitch_games.score_entries WHERE game_id=:game GROUP BY participant_id), "
                "ranked AS (SELECT participant_id,points,RANK() OVER (ORDER BY points "
                "DESC) AS rank, ROW_NUMBER() OVER (ORDER BY points DESC,participant_id) AS "
                "position FROM totals) SELECT r.*,COALESCE(p.display_name,'Viewer "
                "'||r.participant_id) AS display_name FROM ranked r JOIN "
                "twitch_games.participants p ON p.id=r.participant_id WHERE position<=100 "
                "OR participant_id=:user ORDER BY position",
                game=game_id,
                user=identity.user_id,
            )
            entries = [
                {key: value for key, value in row.items() if key != "position"} for row in ranked
            ]
            return {
                "game_id": str(game_id),
                "version": one(
                    c,
                    "SELECT version FROM twitch_games.channels WHERE id=:id",
                    id=identity.channel_id,
                )["version"],
                "final": game["status"] == "ended",
                "entries": entries[:100],
                "own_entry": next(
                    (r for r in entries if r["participant_id"] == identity.user_id), None
                ),
            }
