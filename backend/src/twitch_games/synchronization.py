"""Durable, coalesced, retryable Twitch Extension state-change notifications."""

import json
import time

import jwt

from twitch_games.errors import GameError
from twitch_games.store import one, run


class Publisher:
    def __init__(self, database, auth):
        self.database, self.auth = database, auth

    @property
    def configured(self):
        return self.auth.settings.extension_configured and bool(
            self.auth.settings.twitch_extension_owner_id
        )

    def publish_one(self):
        if not self.database or not self.configured:
            return
        with self.database.transaction() as c:
            item = one(
                c,
                "SELECT * FROM twitch_games.state_notifications WHERE version>published_version "
                "AND next_attempt_at<=clock_timestamp() ORDER BY next_attempt_at "
                "LIMIT 1 FOR UPDATE SKIP LOCKED",
            )
            if not item:
                return
            settings = self.auth.settings
            token = jwt.encode(
                {
                    "exp": int(time.time()) + 60,
                    "role": "external",
                    "user_id": settings.twitch_extension_owner_id,
                    "channel_id": item["channel_id"],
                    "pubsub_perms": {"send": ["broadcast"]},
                },
                self.auth.extension_key,
                algorithm="HS256",
            )
            message = {
                "event": "game_state_changed",
                "channel_id": item["channel_id"],
                "version": item["version"],
            }
            try:
                self.auth.provider.call(
                    "POST",
                    self.auth.provider.helix + "/extensions/pubsub",
                    headers={
                        "Authorization": "Bearer " + token,
                        "Client-Id": settings.twitch_extension_client_id,
                    },
                    json={
                        "broadcaster_id": item["channel_id"],
                        "target": ["broadcast"],
                        "message": json.dumps(message, separators=(",", ":")),
                    },
                )
            except GameError:
                run(
                    c,
                    "UPDATE twitch_games.state_notifications SET attempts=attempts+1,"
                    "next_attempt_at=clock_timestamp()+make_interval(secs=>:delay) WHERE "
                    "channel_id=:channel",
                    delay=min(60, 2 ** min(item["attempts"] + 1, 6)),
                    channel=item["channel_id"],
                )
            else:
                run(
                    c,
                    "UPDATE twitch_games.state_notifications SET "
                    "published_version=:version,attempts=0,"
                    "last_sent_at=clock_timestamp(),next_attempt_at=clock_timestamp()+inter"
                    "val '1 second' "
                    "WHERE channel_id=:channel",
                    version=item["version"],
                    channel=item["channel_id"],
                )
