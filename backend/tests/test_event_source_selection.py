from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.teamwork import TeamworkSettings


class FakeTeamworkClient:
    def __init__(self, settings):
        self.settings = settings

    def list_calendars(self):
        return [{"id": 1306, "name": "marc@doppiogroup.com"}]

    def get_calendar_events(self, calendar_id, start, end):
        return [
            {
                "id": "tw-1",
                "summary": "Teamwork event",
                "start": {"dateTime": f"{start}T15:00:00Z"},
                "end": {"dateTime": f"{start}T16:00:00Z"},
            }
        ]


def _configure_common(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_teamwork_settings",
        lambda: TeamworkSettings(site="doppiogroup.teamwork.com", user_id="531538", api_key="token"),
    )
    monkeypatch.setattr(main_module, "TeamworkClient", FakeTeamworkClient)
    monkeypatch.setattr(main_module, "_current_timelogs", lambda *args, **kwargs: [])
    monkeypatch.setattr(main_module, "_current_timesheet_rows", lambda *args, **kwargs: [])


def test_events_default_to_teamwork_even_when_google_is_configured(monkeypatch):
    _configure_common(monkeypatch)
    monkeypatch.setattr(main_module, "google_calendar_configured", lambda: True)
    monkeypatch.setattr(
        main_module,
        "list_google_calendar_events",
        lambda start, end: [
            {
                "id": "g-should-not-be-default",
                "summary": "Google should not be default",
                "start": {"dateTime": f"{start}T17:00:00Z"},
                "end": {"dateTime": f"{start}T17:30:00Z"},
            }
        ],
    )

    response = TestClient(app).get("/api/teamwork/events?start=2032-01-05&end=2032-01-09")

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"]["source"] == "teamwork"
    assert payload["count"] == 1
    assert payload["events"][0]["source"] == "teamwork"
    assert payload["events"][0]["title"] == "Teamwork event"


def test_events_can_explicitly_use_google_calendar(monkeypatch):
    _configure_common(monkeypatch)
    monkeypatch.setattr(main_module, "google_calendar_configured", lambda: True)
    monkeypatch.setattr(
        main_module,
        "list_google_calendar_events",
        lambda start, end: [
            {
                "id": "g-1",
                "summary": "Google event",
                "start": {"dateTime": f"{start}T17:00:00Z"},
                "end": {"dateTime": f"{start}T17:30:00Z"},
            }
        ],
    )

    response = TestClient(app).get("/api/teamwork/events?start=2032-01-05&end=2032-01-09&source=google")

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"]["source"] == "google"
    assert payload["count"] == 1
    assert payload["events"][0]["source"] == "google"
    assert payload["events"][0]["title"] == "Google event"
