from __future__ import annotations

import json
from datetime import datetime

from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.db import SessionLocal, bootstrap_schema
from app.main import app
from app.models import CalendarEvent, MappingRule, Match


def auth_headers():
    token = deps.create_session("531538", ttl_seconds=600)
    return {"Authorization": f"Bearer {token}"}


def reset_rows(*ids: str):
    bootstrap_schema()
    with SessionLocal() as db:
        for event_id in ids:
            db.query(Match).filter(Match.event_id == event_id).delete()
            db.query(CalendarEvent).filter(CalendarEvent.id == event_id).delete()
        db.commit()


def test_dashboard_password_login_does_not_require_teamwork_api_key(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USERNAME", "marc")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "letmein")
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"mode": "password", "username": "marc", "password": "letmein"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["expires_in"] > 0


def test_match_suggest_uses_mapping_rules_against_title_and_description():
    reset_rows("phase3-brownells")
    with SessionLocal() as db:
        db.add(
            CalendarEvent(
                id="phase3-brownells",
                title="Brownells Invoice Issue",
                description="NO document follow-up",
                start_at="2026-06-08T09:00:00-07:00",
                end_at="2026-06-08T09:45:00-07:00",
                duration_minutes=45,
                raw_json=json.dumps({"calendarId": 1306}),
                imported_at=datetime.utcnow().isoformat(),
            )
        )
        db.add(
            MappingRule(
                pattern="brownells invoice",
                project_id=502827,
                task_id=33027725,
                created_at=datetime.utcnow().isoformat(),
            )
        )
        db.commit()

    client = TestClient(app)
    response = client.post(
        "/api/match/suggest",
        headers=auth_headers(),
        json={"calendar_event_ids": ["phase3-brownells"]},
    )

    assert response.status_code == 200
    assert response.json()["matches"] == [
        {
            "event_id": "phase3-brownells",
            "project_id": 502827,
            "task_id": 33027725,
            "confidence": "high",
            "status": "pending",
        }
    ]


def test_filler_plan_gap_fills_weekdays_with_90_minute_blocks():
    reset_rows("phase3-work-2030", "filler-2030-06-03-1", "filler-2030-06-03-2")
    with SessionLocal() as db:
        db.add(
            CalendarEvent(
                id="phase3-work-2030",
                title="Known work",
                description="Already approved",
                start_at="2030-06-03T09:00:00-07:00",
                end_at="2030-06-03T15:00:00-07:00",
                duration_minutes=360,
                raw_json="{}",
                imported_at=datetime.utcnow().isoformat(),
            )
        )
        db.add(Match(event_id="phase3-work-2030", project_id=1, task_id=2, confidence="high", status="approved"))
        db.commit()

    client = TestClient(app)
    response = client.post(
        "/api/filler/plan",
        headers=auth_headers(),
        json={"week_start": "2030-06-03"},
    )

    assert response.status_code == 200
    monday_plans = [p for p in response.json()["plans"] if p["date"] == "2030-06-03"]
    assert len(monday_plans) == 1
    assert monday_plans[0]["minutes"] == 90
    assert monday_plans[0]["project_id"] == 417162
    assert monday_plans[0]["task_id"] == 29936460


def test_submit_writes_approved_matched_events_in_phase5(monkeypatch):
    reset_rows("phase3-submit-2032")
    write_calls = []

    class FakeTeamworkClient:
        def list_time_entries(self, **kwargs):
            return []

        def create_calendar_event_time(self, **kwargs):
            write_calls.append(("calendar", kwargs))
            return {"timelog": {"id": 987654}}

        def create_task_time_entry(self, **kwargs):
            write_calls.append(("task", kwargs))
            return {"time-entry": {"id": 123456}}

    monkeypatch.setattr("app.api.v1.submit.build_teamwork_client", lambda: FakeTeamworkClient())
    with SessionLocal() as db:
        db.add(
            CalendarEvent(
                id="phase3-submit-2032",
                title="ASR dev block",
                description="Enhanced 901",
                start_at="2032-06-07T10:00:00-07:00",
                end_at="2032-06-07T11:00:00-07:00",
                duration_minutes=60,
                raw_json=json.dumps({"calendarId": 1306}),
                imported_at=datetime.utcnow().isoformat(),
            )
        )
        db.add(Match(event_id="phase3-submit-2032", project_id=500, task_id=600, confidence="high", status="approved"))
        db.commit()

    client = TestClient(app)
    response = client.post(
        "/api/week/submit",
        headers=auth_headers(),
        json={"week_start": "2032-06-07", "confirm": True},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "write"
    assert response.json()["writes_enabled"] is True
    assert response.json()["would_submit"] == []
    assert response.json()["submitted"] == [{"event_id": "phase3-submit-2032", "timelog_id": 987654}]
    assert write_calls == [
        (
            "calendar",
            {
                "calendar_id": 1306,
                "event_id": "phase3-submit-2032",
                "date": "2032-06-07",
                "start_time": "10:00:00",
                "minutes": 60,
                "description": "Event: ASR dev block",
                "project_id": 500,
                "task_id": 600,
                "is_billable": True,
            },
        )
    ]
