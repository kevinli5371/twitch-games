"""Backend-only Supabase HTTPS transport for complete atomic RPC operations.

No arbitrary SQL or browser table access is exposed. Each RPC is one transaction;
Twitch identity and private game policy remain authoritative in FastAPI.
"""

import json

import httpx2 as httpx

from twitch_games.database import SCHEMA_REVISION
from twitch_games.errors import GameError


class SupabaseHTTP:
    def __init__(self, settings, *, transport=None):
        if not settings.supabase_url or not settings.supabase_secret_key:
            raise GameError("not_configured", "Configure Supabase project URL and secret key", 503)
        self.client = httpx.Client(
            base_url=(settings.test_supabase_http_url or settings.supabase_url) + "/rest/v1/",
            # Modern server secret keys are API keys, not JWT bearer tokens.
            headers={"apikey": settings.supabase_secret_key.get_secret_value()},
            timeout=5,
            follow_redirects=False,
            transport=transport,
        )

    def probe(self):
        """Read-only gateway/key check, not proof of installed gameplay RPCs."""
        try:
            response = self.client.get("")
        except httpx.RequestError:
            raise GameError(
                "database_unavailable", "Supabase HTTPS connection unavailable", 503
            ) from None
        if response.status_code in {401, 403}:
            raise GameError("not_configured", "Supabase rejected the server API key", 503)
        if response.status_code != 200:
            raise GameError("database_unavailable", "Supabase Data API unavailable", 503)
        return {"https_gateway": "reachable", "gameplay_rpc": "not_verified"}

    def rpc(self, operation, **args):
        try:
            response = self.client.post(
                "rpc/twitch_games_backend", json={"operation": operation, "args": args}
            )
        except httpx.RequestError:
            raise GameError(
                "database_unavailable", "Supabase HTTPS operation unavailable", 503
            ) from None
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                raise GameError(
                    "database_unavailable", "Supabase returned an invalid RPC response", 503
                ) from None
        try:
            body = response.json()
            detail = json.loads(body.get("details", "{}"))
            if body.get("code") == "P0001" and body.get("message") in {
                "forbidden",
                "not_found",
                "validation_error",
                "request_conflict",
                "stale_state",
                "round_active",
                "round_closed",
                "game_active",
                "game_ended",
                "unsupported_policy",
                "transcript_unavailable",
                "stream_unavailable",
                "database_unavailable",
            }:
                raise GameError(body["message"], detail["message"], int(detail["status"]))
        except (ValueError, TypeError, KeyError):
            pass
        raise GameError(
            "database_unavailable",
            "Supabase backend RPC unavailable; verify migration and server key",
            503,
        )

    def status(self):
        try:
            result = self.rpc("health")
            return (
                "ok"
                if isinstance(result, dict) and result.get("revision") == SCHEMA_REVISION
                else "migration_required"
            )
        except GameError:
            return "unavailable"

    def close(self):
        self.client.close()
