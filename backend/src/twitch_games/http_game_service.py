"""Same game contract through backend-only transactional Supabase RPCs."""

import hashlib
from dataclasses import asdict

from twitch_games.errors import GameError
from twitch_games.game_service import json_text
from twitch_games.matching import match_answer, normalize_answer
from twitch_games.policy import POLICY
from twitch_games.quote_engine import GENERATOR_VERSION, WORD, Passage, choose_quotes


def actor(identity):
    return {
        "channel_id": identity.channel_id,
        "user_id": identity.user_id,
        "role": identity.role,
        "source": identity.source,
    }


class HTTPGameService:
    def __init__(self, database, auth):
        self.database, self.auth = database, auth

    def call(self, operation, identity=None, **args):
        if self.database is None:
            raise GameError("not_configured", "Supabase HTTPS configuration is required", 503)
        if identity is not None:
            args["actor"] = actor(identity)
        return self.database.rpc(operation, **args)

    def resolve_channel(self, key, resource_id):
        return self.call("resolve", kind=key, id=str(resource_id))

    def public_state(self, identity, channel):
        identity.viewer(channel)
        return self.call("state", identity)

    def dashboard(self, identity, channel):
        identity.viewer(channel)
        return self.call("dashboard", identity)

    def questions_http(self, identity, stream):
        return self.call("questions", identity, stream_id=str(stream))

    def connect_stream(self, identity, channel):
        identity.viewer(channel)
        self.call("permissions", identity, permission="settings")
        provider = self.auth.provider
        provider.user(channel)
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
        return self.call(
            "stream_connect",
            identity,
            twitch_stream_id=streams[0]["id"],
            started_at=streams[0]["started_at"],
        )

    def generate(self, stream):
        source = self.call("generation_read", stream_id=str(stream))
        if not source:
            return
        passages, parts, ids = [], [], []
        for record in reversed(source["records"]):
            if parts and len(" ".join(parts)) + len(record["text"]) + 1 > 4000:
                parts, ids = [], []
            parts.append(record["text"])
            ids.append(record["id"])
            passage = " ".join(parts)
            if len(WORD.findall(passage)) >= 8:
                passages.append(Passage(passage, tuple(ids)))
                parts, ids = [], []
        existing = source["existing"]
        candidates = choose_quotes(passages, {r["canonical_answer"] for r in existing}, limit=20)
        digests = {r["quote_digest"] for r in existing}
        self.call(
            "generation_save",
            stream_id=str(stream),
            version=source["version"],
            generator=GENERATOR_VERSION,
            candidates=[asdict(c) for c in candidates if c.digest not in digests],
        )

    def intake(self, identity, stream_id, batch):
        if len({s.sequence for s in batch.segments}) != len(batch.segments):
            raise GameError(
                "validation_error", "Segment sequence numbers must be unique in a batch", 422
            )
        if any(not s.text.strip() for s in batch.segments):
            raise GameError("validation_error", "Caption text cannot be blank", 422)
        body = batch.model_dump(mode="json")
        result = self.call(
            "intake",
            identity,
            stream_id=str(stream_id),
            body=body,
            digest=hashlib.sha256(json_text(body).encode()).hexdigest(),
        )
        self.generate(stream_id)
        return result

    def aliases(self, identity, channel, body=None):
        identity.viewer(channel)
        return self.call(
            "aliases", identity, **({"body": body.model_dump(mode="json")} if body else {})
        )

    def command_args(self, operation, target, body):
        payload = body.model_dump(mode="json")
        return {
            "body": payload,
            "target": str(target),
            "policy": POLICY,
            "digest": hashlib.sha256(
                json_text([operation, str(target), payload]).encode()
            ).hexdigest(),
        }

    def start(self, identity, channel, body):
        identity.viewer(channel)
        return self.call("start", identity, **self.command_args("start", channel, body))

    def open_round(self, identity, game_id, body):
        args = self.command_args("open", game_id, body)
        previous = self.call("command_receipt", identity, **args)
        if previous is not None:
            return previous
        question = self.call(
            "open_input",
            identity,
            game_id=str(game_id),
            question_id=str(body.question_id) if body.question_id else None,
        )
        return self.call(
            "open",
            identity,
            **args,
            selected_question=question["id"],
            alias_key=normalize_answer(question["canonical_answer"]),
        )

    def submit(self, identity, round_id, body):
        identity.viewer(identity.channel_id, participating=True)
        check = self.call("resource_check", identity, round_id=str(round_id))
        name = (
            None
            if check["participant_exists"]
            else self.auth.provider.user(identity.user_id)["display_name"]
        )
        return self.call(
            "submit",
            identity,
            round_id=str(round_id),
            body=body.model_dump(mode="json"),
            display_name=name,
        )

    def awards(self, round_id, identity=None):
        data = self.call("score_input", identity, round_id=str(round_id))
        r = data["round"]
        return [
            {
                "submission_id": s["id"],
                "participant_id": s["participant_id"],
                "correct": match_answer(
                    s["raw_answer"],
                    r["canonical_answer_snapshot"],
                    tuple(r["accepted_aliases_snapshot"]),
                ).correct,
            }
            for s in data["submissions"]
        ]

    def close_round(self, identity, round_id, body):
        args = self.command_args("close", round_id, body)
        previous = self.call("command_receipt", identity, **args)
        if previous is not None:
            return previous
        return self.call("close", identity, **args, awards=self.awards(round_id, identity))

    def generate_due(self):
        for source in self.call("generation_due"):
            self.generate(source["stream_id"])

    def close_due(self):
        for r in self.call("score_due"):
            self.call("score_finalize", round_id=r["id"], awards=self.awards(r["id"]))

    def end(self, identity, game_id, body):
        return self.call("end", identity, **self.command_args("end", game_id, body))

    def own(self, identity, round_id):
        identity.viewer(identity.channel_id, participating=True)
        return self.call("own", identity, round_id=str(round_id))

    def leaderboard(self, identity, game_id):
        return self.call("board", identity, game_id=str(game_id))

    def grants(self, identity, channel, body=None, moderator_id=None):
        identity.owner(channel)
        if moderator_id:
            return self.call("grants_revoke", identity, moderator_id=moderator_id)
        if body:
            moderator = self.auth.provider.user_by_login(body.login)
            owner = self.auth.provider.user(channel)
            return self.call(
                "grants_set",
                identity,
                owner=owner,
                moderator=moderator,
                permissions=body.permissions,
            )
        return self.call("grants_list", identity)
