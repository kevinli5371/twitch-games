"""HTTPS transport for the in-progress Supabase RPC migration.

Not a substitute for Database.transaction(): each RPC must implement one complete
transaction. Existing gameplay remains on the verified SQL runtime until ported.
"""

import httpx2 as httpx

from twitch_games.errors import GameError


class SupabaseHTTP:
    def __init__(self, settings, *, transport=None):
        if not settings.supabase_url or not settings.supabase_secret_key:
            raise GameError("not_configured", "Configure Supabase project URL and secret key", 503)
        self.client = httpx.Client(
            base_url=settings.supabase_url + "/rest/v1/",
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

    def close(self):
        self.client.close()
