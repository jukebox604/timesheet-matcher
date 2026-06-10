from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.db import SessionLocal, bootstrap_schema
from app.main import app
from app.models import CalendarEvent


def auth_headers():
    token = deps.create_session("531538", ttl_seconds=600)
    return {"Authorization": f"Bearer {token}"}


def cleanup_event(event_id: str):
    bootstrap_schema()
    with SessionLocal() as db:
        row = db.get(CalendarEvent, event_id)
        if row:
            db.delete(row)
            db.commit()


def test_teamwork_week_sync_imports_calendar_events_and_returns_daily_totals(monkeypatch):
    cleanup_event("tw-evt-2033")
    cleanup_event("tw-all-day-2033")
    cleanup_event("stale-global-unavailable")
    with SessionLocal() as db:
        db.add(
            CalendarEvent(
                id="stale-global-unavailable",
                title="Unavailable",
                description="wrong global event",
                start_at="2033-06-06T00:00:00Z",
                end_at="2033-06-06T23:59:00Z",
                duration_minutes=1439,
                raw_json='{"typeId": -2, "attendingUserIds": [999999]}',
                imported_at="2033-01-01T00:00:00Z",
            )
        )
        db.commit()

    class FakeTeamworkClient:
        def list_calendar_events(self, *, start_date, end_date, page_size=100):
            assert start_date == "2033-06-06"
            assert end_date == "2033-06-13"
            return [
                {
                    "id": "tw-evt-2033",
                    "summary": "Brownells Invoice Issue",
                    "description": "NO document follow-up",
                    "start": {"dateTime": "2033-06-06T09:00:00-07:00", "timeZone": "America/Vancouver"},
                    "end": {"dateTime": "2033-06-06T09:45:00-07:00", "timeZone": "America/Vancouver"},
                    "calendar": {"id": 1306, "type": "calendars"},
                    "createdBy": {"id": 531538, "type": "users"},
                    "mappedTaskIds": [33027725],
                },
                {
                    "id": "tw-all-day-2033",
                    "title": "Unavailable",
                    "description": "",
                    "startDate": "2033-06-07T00:00:00Z",
                    "endDate": "2033-06-07T23:59:00Z",
                    "allDay": True,
                    "calendarId": 17,
                }
            ]

        def get_timesheet_daily_totals(self, *, start_date, end_date, user_id):
            assert start_date == "2033-06-06"
            assert end_date == "2033-06-12"
            assert user_id == "531538"
            return {"2033-06-06": 45, "2033-06-07": 0}

    monkeypatch.setattr("app.api.v1.sync.build_teamwork_client", lambda: FakeTeamworkClient())
    client = TestClient(app)

    response = client.post(
        "/api/sync/teamwork/week",
        headers=auth_headers(),
        json={"week_start": "2033-06-06"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["calendar_events_imported"] == 2
    assert payload["daily_totals"] == {"2033-06-06": 45, "2033-06-07": 0}
    assert payload["events"][0]["id"] == "tw-evt-2033"

    with SessionLocal() as db:
        row = db.get(CalendarEvent, "tw-evt-2033")
        assert row is not None
        assert row.title == "Brownells Invoice Issue"
        assert row.duration_minutes == 45
        assert '"mappedTaskIds": [33027725]' in row.raw_json
        all_day = db.get(CalendarEvent, "tw-all-day-2033")
        assert all_day is not None
        assert all_day.start_at == "2033-06-07T00:00:00Z"
        assert all_day.end_at == "2033-06-07T23:59:00Z"
        assert all_day.duration_minutes == 1439
        assert db.get(CalendarEvent, "stale-global-unavailable") is None


def test_teamwork_week_sync_requires_auth():
    client = TestClient(app)

    response = client.post("/api/sync/teamwork/week", json={"week_start": "2033-06-06"})

    assert response.status_code == 401
