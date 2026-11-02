import httpx2 as httpx
import pytest
from pydantic import ValidationError

from twitch_games.config import Settings
from twitch_games.errors import GameError
from twitch_games.supabase_http import SupabaseHTTP


def test_https_transport_keeps_secret_in_header_and_never_follows_redirect():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://untrusted.example/"})

    client = SupabaseHTTP(
        Settings(
            supabase_url="https://fixture.supabase.co",
            supabase_secret_key="sb_secret_fixture_only_not_real",
            _env_file=None,
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(GameError):
            client.probe()
        assert len(requests) == 1
        assert requests[0].headers["apikey"] == "sb_secret_fixture_only_not_real"
        assert "authorization" not in requests[0].headers
        assert "sb_secret" not in str(requests[0].url)
    finally:
        client.close()


@pytest.mark.parametrize(
    "url",
    [
        "http://fixture.supabase.co",
        "https://evil.example",
        "https://user:pass@fixture.supabase.co",
        "https://fixture.supabase.co/rest/v1",
    ],
)
def test_http_configuration_rejects_non_project_secret_destinations(url):
    with pytest.raises(ValidationError):
        Settings(supabase_url=url, _env_file=None)


def test_public_key_is_not_backend_secret():
    with pytest.raises(ValidationError):
        Settings(supabase_secret_key="sb_publishable_fixture", _env_file=None)


def test_gateway_success_does_not_claim_gameplay_rpc_ready():
    client = SupabaseHTTP(
        Settings(
            supabase_url="https://fixture.supabase.co",
            supabase_secret_key="sb_secret_fixture_only_not_real",
            _env_file=None,
        ),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )
    try:
        assert client.probe() == {"https_gateway": "reachable", "gameplay_rpc": "not_verified"}
    finally:
        client.close()
