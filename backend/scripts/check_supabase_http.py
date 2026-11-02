"""Credential-safe hosted HTTPS preflight and optional installed-RPC readiness check."""

import argparse

from twitch_games.config import Settings
from twitch_games.errors import GameError
from twitch_games.supabase_http import SupabaseHTTP


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-rpc", action="store_true", help="Require installed backend RPC schema"
    )
    args = parser.parse_args()
    client = None
    try:
        client = SupabaseHTTP(Settings())
        client.probe()
        print("Supabase HTTPS gateway accepted the configured server key.")
        if args.require_rpc:
            if client.status() != "ok":
                raise GameError(
                    "database_unavailable", "Backend RPC migration is missing or unavailable.", 503
                )
            print("Backend RPC revision and service-key execution verified.")
        else:
            print(
                "Gameplay storage is not checked by this probe; use --require-rpc after migration."
            )
    except GameError as error:
        print(error.message)
        raise SystemExit(1) from None
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
