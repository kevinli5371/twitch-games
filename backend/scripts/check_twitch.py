"""Read-only Twitch credential checks and explicit owner-ID setup; never sends messages."""

import argparse
import re
import time
from pathlib import Path

import jwt
from dotenv import set_key
from pydantic import ValidationError

from twitch_games.auth import NUMERIC, Auth, TwitchProvider
from twitch_games.config import Settings
from twitch_games.errors import GameError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-login", required=True)
    parser.add_argument("--save-owner-id", action="store_true")
    parser.add_argument("--check-extension", action="store_true")
    parser.add_argument("--extension-version")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_]{1,25}", args.owner_login):
        raise SystemExit("Enter the Twitch login name, not a URL or display name")
    # Owner lookup only needs OAuth application credentials. Other keys may still be in setup.
    settings = Settings(twitch_extension_secret=None, twitch_extension_owner_id=None)
    if not settings.twitch_client_id or not settings.twitch_client_secret:
        raise SystemExit(
            "Fill TWITCH_GAMES_TWITCH_CLIENT_ID and TWITCH_GAMES_TWITCH_CLIENT_SECRET first"
        )
    provider = TwitchProvider(settings)
    try:
        token = provider.token(grant_type="client_credentials")["access_token"]
        validated = provider.call(
            "GET", provider.oauth + "/validate", headers={"Authorization": "OAuth " + token}
        )
        if validated.get("client_id") != settings.twitch_client_id:
            raise SystemExit("Twitch returned a token for another client")
        result = provider.call(
            "GET",
            provider.helix + "/users",
            params={"login": args.owner_login},
            headers={"Authorization": "Bearer " + token, "Client-Id": settings.twitch_client_id},
        ).get("data", [])
        if len(result) != 1 or not NUMERIC.fullmatch(result[0]["id"]):
            raise SystemExit("Twitch owner login was not found")
        owner_id = result[0]["id"]
        print("OAuth application credentials verified against Twitch; tokens not displayed.")
        print("Extension owner Twitch ID: " + owner_id)
        if args.save_owner_id:
            path = Path(__file__).resolve().parents[1] / ".env"
            set_key(path, "TWITCH_GAMES_TWITCH_EXTENSION_OWNER_ID", owner_id)
            path.chmod(0o600)
            print("Owner ID saved in the ignored backend/.env.")
        if args.check_extension:
            full = Settings(twitch_extension_owner_id=owner_id)
            auth = Auth(full, None)
            try:
                if not full.extension_configured:
                    raise SystemExit(
                        "Fill the Extension Client ID and shared Secret Keys value first"
                    )
                signed = jwt.encode(
                    {"exp": int(time.time()) + 60, "role": "external", "user_id": owner_id},
                    auth.extension_key,
                    algorithm="HS256",
                )
                params = {"extension_id": full.twitch_extension_client_id}
                if args.extension_version:
                    params["extension_version"] = args.extension_version
                provider.call(
                    "GET",
                    provider.helix + "/extensions/jwt/secrets",
                    params=params,
                    headers={
                        "Authorization": "Bearer " + signed,
                        "Client-Id": full.twitch_extension_client_id,
                    },
                )
                print("Twitch accepted the Extension owner and signing credentials.")
                print(
                    "Viewer JWTs, PubSub delivery and captions still need an installed test view."
                )
            finally:
                auth.provider.client.close()
    except GameError as error:
        raise SystemExit("Twitch check failed: " + error.message) from None
    finally:
        provider.client.close()


if __name__ == "__main__":
    try:
        main()
    except ValidationError:
        raise SystemExit(
            "Configuration is invalid; check local credential fields without posting secrets."
        ) from None
