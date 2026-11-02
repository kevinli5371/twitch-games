"""Fenced PubSub acknowledgement over Supabase HTTPS; no private event payloads."""

import json
import time

import jwt

from twitch_games.errors import GameError
from twitch_games.synchronization import Publisher


class HTTPPublisher(Publisher):
    def publish_one(self):
        if not self.database or not self.configured:
            return
        item = self.database.rpc("notice_claim")
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
        success = False
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
                    "message": json.dumps(
                        {
                            "event": "game_state_changed",
                            "channel_id": item["channel_id"],
                            "version": item["version"],
                        },
                        separators=(",", ":"),
                    ),
                },
            )
            success = True
        except GameError:
            pass
        self.database.rpc(
            "notice_finish",
            channel_id=item["channel_id"],
            lease=item["lease"],
            version=item["version"],
            success=success,
        )
