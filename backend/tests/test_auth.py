import base64
import time

import jwt
import pytest
from pydantic import ValidationError

from twitch_games.auth import Auth
from twitch_games.config import Settings
from twitch_games.errors import GameError

KEY = b"integration-only-extension-key-32bytes!"


def auth():
    return Auth(
        Settings(
            twitch_extension_client_id="test-extension",
            twitch_extension_secret=base64.b64encode(KEY).decode(),
        ),
        None,
    )


def token(**overrides):
    return jwt.encode(
        {
            "exp": int(time.time()) + 60,
            "channel_id": "90001",
            "role": "viewer",
            "opaque_user_id": "Uopaque",
            "user_id": "90002",
            **overrides,
        },
        KEY,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": 1},
        {"channel_id": "oops"},
        {"role": "external"},
        {"role": "broadcaster"},
        {"user_id": "bad"},
        {"opaque_user_id": "Aanon"},
        {"is_unlinked": True},
        {"channel_id": 90001},
    ],
)
def test_invalid_extension_claims(overrides):
    with pytest.raises(GameError) as error:
        auth().extension(token(**overrides))
    assert error.value.status == 401


def test_algorithm_and_signature_rejected():
    for invalid in [
        jwt.encode({"exp": time.time() + 60}, b"different-key-at-least-32-bytes-long!"),
        jwt.encode({"exp": time.time() + 60}, KEY * 2, algorithm="HS384"),
        "broken",
    ]:
        with pytest.raises(GameError):
            auth().extension(invalid)


def test_channel_and_owner_boundaries():
    identity = auth().extension(token())
    identity.viewer("90001", participating=True)
    for action in [lambda: identity.owner("90001"), lambda: identity.viewer("90003")]:
        with pytest.raises(GameError) as error:
            action()
        assert error.value.status == 403


def test_spectator_cannot_submit_without_shared_identity():
    identity = auth().extension(token(user_id=None, opaque_user_id="Aanon"))
    identity.viewer("90001")
    with pytest.raises(GameError) as error:
        identity.viewer("90001", participating=True)
    assert error.value.code == "identity_required"


@pytest.mark.parametrize(
    "settings",
    [
        {"twitch_extension_secret": "not-base64"},
        {"token_encryption_key": "not-fernet"},
        {"test_twitch_base_url": "http://127.0.0.1:9000"},
        {"environment": "test", "test_twitch_base_url": "http://remote.example"},
        {"twitch_redirect_uri": "http://remote.example/callback"},
    ],
)
def test_auth_configuration_validation(settings):
    with pytest.raises(ValidationError):
        Settings(**settings)


def test_placeholder_credentials_leave_auth_disabled():
    settings = Settings(
        twitch_client_id="...",
        twitch_client_secret="...",
        twitch_extension_client_id="...",
        twitch_extension_secret="...",
        twitch_extension_owner_id="...",
        token_encryption_key="...",
    )
    assert not settings.oauth_configured and not settings.extension_configured
    with pytest.raises(GameError) as error:
        Auth(settings, None).extension("not-a-token")
    assert error.value.code == "not_configured"
