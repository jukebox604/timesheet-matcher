from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.config import settings as app_settings
from app.main import app
from app.routes import auth as auth_routes


client = TestClient(app, follow_redirects=False)


def configured_settings(**overrides):
    return replace(
        app_settings,
        google_client_id="google-client-id",
        google_client_secret="google-client-secret",
        google_redirect_uri="https://timesheet.ramos.ca/api/auth/google/callback",
        google_allowed_email="marc@ramos.ca",
        **overrides,
    )


def test_google_start_redirects_to_google_with_state(monkeypatch):
    monkeypatch.setattr(auth_routes, "settings", configured_settings())
    auth_routes._google_oauth_states.clear()

    response = client.get("/api/auth/google/start")

    assert response.status_code == 303
    location = response.headers["location"]
    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert params["client_id"] == ["google-client-id"]
    assert params["redirect_uri"] == ["https://timesheet.ramos.ca/api/auth/google/callback"]
    assert params["scope"] == ["openid email profile"]
    assert params["state"][0] in auth_routes._google_oauth_states


def test_google_callback_allows_configured_email_and_creates_session(monkeypatch):
    monkeypatch.setattr(auth_routes, "settings", configured_settings())
    auth_routes._google_oauth_states.clear()
    auth_routes._remember_oauth_state("known-state")

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            assert url == auth_routes.GOOGLE_TOKEN_URL
            assert kwargs["data"]["code"] == "oauth-code"
            return FakeResponse({"access_token": "google-access-token"})

        def get(self, url, **kwargs):
            assert url == auth_routes.GOOGLE_USERINFO_URL
            assert kwargs["headers"]["Authorization"] == "Bearer google-access-token"
            return FakeResponse({"email": "marc@ramos.ca", "email_verified": True})

    monkeypatch.setattr(auth_routes.httpx, "Client", FakeHttpxClient)

    response = client.get("/api/auth/google/callback?code=oauth-code&state=known-state")

    assert response.status_code == 303
    location = response.headers["location"]
    token = parse_qs(urlparse(location).query)["auth_token"][0]
    assert deps.validate_session(token) is True


def test_google_callback_rejects_unapproved_email(monkeypatch):
    monkeypatch.setattr(auth_routes, "settings", configured_settings())
    auth_routes._google_oauth_states.clear()
    auth_routes._remember_oauth_state("known-state")

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            return FakeResponse({"access_token": "google-access-token"})

        def get(self, url, **kwargs):
            return FakeResponse({"email": "someone@example.com", "email_verified": True})

    monkeypatch.setattr(auth_routes.httpx, "Client", FakeHttpxClient)

    response = client.get("/api/auth/google/callback?code=oauth-code&state=known-state")

    assert response.status_code == 303
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert "not allowed" in params["auth_error"][0]
