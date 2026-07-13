from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.teamwork import TeamworkSettings


class FakeTeamworkClient:
    calendar_calls = []
    task_calls = []

    def __init__(self, settings):
        self.settings = settings

    def log_calendar_event_time(self, calendar_id, event_id, timelog):
        self.calendar_calls.append({"calendar_id": calendar_id, "event_id": event_id, "timelog": timelog})
        return {"ok": True}

    def create_task_time_entry(self, task_id, time_entry):
        self.task_calls.append({"task_id": task_id, "time_entry": time_entry})
        return {"ok": True}


def install_fake(monkeypatch):
    FakeTeamworkClient.calendar_calls = []
    FakeTeamworkClient.task_calls = []
    monkeypatch.setattr(
        main_module,
        "get_teamwork_settings",
        lambda: TeamworkSettings(site="doppiogroup.teamwork.com", user_id="531538", api_key="token"),
    )
    monkeypatch.setattr(main_module, "TeamworkClient", FakeTeamworkClient)


def base_entry(**overrides):
    entry = {
        "eventId": "event-1",
        "calendarId": 1306,
        "title": "Client work",
        "description": "Matched client work",
        "start": "2026-07-13T09:00:00",
        "duration_minutes": 60,
        "projectId": 123,
        "taskId": 456,
    }
    entry.update(overrides)
    return entry


def test_teamwork_matched_entries_default_to_billable(monkeypatch):
    install_fake(monkeypatch)

    response = TestClient(app).post("/api/teamwork/submit-matched", json={"entries": [base_entry()]})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert FakeTeamworkClient.calendar_calls[0]["timelog"]["isBillable"] is True


def test_teamwork_matched_entries_can_still_be_sent_non_billable(monkeypatch):
    install_fake(monkeypatch)

    response = TestClient(app).post(
        "/api/teamwork/submit-matched",
        json={"entries": [base_entry(isBillable=False)]},
    )

    assert response.status_code == 200
    assert FakeTeamworkClient.calendar_calls[0]["timelog"]["isBillable"] is False


def test_google_plain_task_entries_default_to_billable(monkeypatch):
    install_fake(monkeypatch)

    response = TestClient(app).post(
        "/api/teamwork/submit-matched",
        json={"entries": [base_entry(eventId="google:1", calendarId="google", source="google")]},
    )

    assert response.status_code == 200
    assert FakeTeamworkClient.task_calls[0]["time_entry"]["isbillable"] == "1"
