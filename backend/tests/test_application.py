from fastapi.testclient import TestClient

from twitch_games.application import create_app
from twitch_games.config import Settings


def test_liveness_and_truthful_readiness():
    with TestClient(create_app(Settings(environment="test"))) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "ok"
        assert live.headers["cache-control"] == "no-store"
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json() == {
            "status": "not_ready",
            "stage": "foundation",
            "dependencies": {
                "database": "not_implemented",
                "twitch_auth": "not_implemented",
                "gameplay": "not_implemented",
            },
        }


def test_runtime_docs_only_advertise_implemented_health_routes():
    with TestClient(create_app(Settings())) as client:
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"]) == {"/health/live", "/health/ready"}
        assert "503" in schema["paths"]["/health/ready"]["get"]["responses"]
        assert "200" not in schema["paths"]["/health/ready"]["get"]["responses"]
        assert client.get("/api/v1/channels/12345/game-state").status_code == 404
        assert client.post("/api/v1/rounds/example-round/answers", json={}).status_code == 404


def test_production_docs_are_disabled():
    settings = Settings(
        environment="production", docs_enabled=False, cors_origins=["https://dashboard.example.com"]
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/health/live").status_code == 200


def test_only_configured_origin_can_make_credentialed_requests():
    settings = Settings(cors_origins=["https://dashboard.example.com"])
    with TestClient(create_app(settings)) as client:
        headers = {
            "Origin": "https://dashboard.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        }
        response = client.options("/health/live", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == headers["Origin"]
        assert response.headers["access-control-allow-credentials"] == "true"
        headers["Origin"] = "https://untrusted.example.com"
        denied = client.options("/health/live", headers=headers)
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers


def test_default_has_no_cross_origin_access():
    with TestClient(create_app(Settings())) as client:
        response = client.get("/health/live", headers={"Origin": "https://example.com"})
        assert "access-control-allow-origin" not in response.headers
