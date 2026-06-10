import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.teamwork import TeamworkClient, TeamworkSettings


def test_teamwork_status_reports_missing_secret_when_api_key_absent(monkeypatch):
    monkeypatch.delenv("TEAMWORK_API_KEY", raising=False)
    monkeypatch.delenv("TEAMWORK_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("TEAMWORK_SITE", "doppiogroup.teamwork.com")
    monkeypatch.setenv("TEAMWORK_USER_ID", "531538")

    client = TestClient(app)

    response = client.get("/api/teamwork/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["connected"] is False
    assert payload["site"] == "doppiogroup.teamwork.com"
    assert payload["user_id"] == "531538"
    assert payload["message"] == "Teamwork API credentials are not configured"


def test_teamwork_client_fetches_current_user_with_basic_auth():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={"person": {"id": 531538, "firstName": "Marc"}})

    settings = TeamworkSettings(
        site="doppiogroup.teamwork.com",
        user_id="531538",
        api_key="test_api_key",
    )
    transport = httpx.MockTransport(handler)

    result = TeamworkClient(settings=settings, transport=transport).get_current_user()

    assert seen["url"] == "https://doppiogroup.teamwork.com/projects/api/v3/me.json"
    assert seen["authorization"].startswith("Basic ")
    assert result["person"]["id"] == 531538
