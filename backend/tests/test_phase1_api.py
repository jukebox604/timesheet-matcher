from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.main import app


def test_health_endpoint_reports_ok():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_routes_reject_missing_bearer_token():
    client = TestClient(app)

    response = client.get("/api/mappings")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired session token"


def test_token_status_and_logout_lifecycle():
    token = deps.create_session("531538", ttl_seconds=600)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    status_response = client.get("/api/auth/token/status", headers=headers)
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["authenticated"] is True
    assert status_payload["expires_in"] > 0

    logout_response = client.post("/api/auth/logout", headers=headers)
    assert logout_response.status_code == 200
    assert logout_response.json() == {"ok": True}

    status_after_logout = client.get("/api/auth/token/status", headers=headers)
    assert status_after_logout.status_code == 200
    assert status_after_logout.json() == {"authenticated": False, "expires_in": 0}


def test_filler_plan_returns_real_phase3_plan_shape():
    token = deps.create_session("531538", ttl_seconds=600)
    client = TestClient(app)

    response = client.post(
        "/api/filler/plan",
        headers={"Authorization": f"Bearer {token}"},
        json={"week_start": "2031-01-06"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "plans" in payload
    assert payload["plans"]
    assert {"date", "minutes", "project_id", "task_id", "billable"}.issubset(payload["plans"][0])
