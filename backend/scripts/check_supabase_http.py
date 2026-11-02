"""Read-only HTTPS/API-key probe; does not claim a completed database adapter."""

from twitch_games.config import Settings
from twitch_games.errors import GameError
from twitch_games.supabase_http import SupabaseHTTP


def main():
    client = None
    try:
        client = SupabaseHTTP(Settings())
        client.probe()
        print("Supabase HTTPS gateway accepted the configured server key.")
        print("Gameplay RPC migration/runtime integration is still pending.")
    except GameError as error:
        print(error.message)
        raise SystemExit(1) from None
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
