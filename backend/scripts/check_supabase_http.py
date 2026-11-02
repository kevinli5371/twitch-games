"""Credential-safe hosted HTTPS preflight and optional installed-RPC readiness check."""

import argparse
import hashlib
from uuid import uuid4

from twitch_games.config import Settings
from twitch_games.errors import GameError
from twitch_games.supabase_http import SupabaseHTTP


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-rpc", action="store_true", help="Require installed backend RPC schema"
    )
    parser.add_argument(
        "--exercise-writes",
        action="store_true",
        help="Verify and remove a disposable OAuth-state record",
    )
    args = parser.parse_args()
    client = None
    try:
        client = SupabaseHTTP(Settings())
        client.probe()
        print("Supabase HTTPS gateway accepted the configured server key.")
        if args.require_rpc or args.exercise_writes:
            if client.status() != "ok":
                raise GameError(
                    "database_unavailable", "Backend RPC migration is missing or unavailable.", 503
                )
            print("Backend RPC revision and service-key execution verified.")
        else:
            print(
                "Gameplay storage is not checked by this probe; use --require-rpc after migration."
            )
        if args.exercise_writes:
            probe = hashlib.sha256(("supabase-http-probe-" + uuid4().hex).encode()).hexdigest()
            try:
                client.rpc("oauth_state_new", digest=probe)
                assert client.rpc("oauth_state_consume", digest=probe) == probe
                assert client.rpc("oauth_state_consume", digest=probe) is None
            finally:
                client.rpc("oauth_state_consume", digest=probe)
            print("Hosted insert/consume/replay verified; disposable probe removed.")
    except GameError as error:
        print(error.message)
        raise SystemExit(1) from None
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
