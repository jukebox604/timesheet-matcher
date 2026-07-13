from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app, FILLER_DESCRIPTION, FILLER_TASK_ID
from app.teamwork import TeamworkSettings


class FakeTeamworkClient:
    created_entries = []
    daily_totals = {}
    existing_timelogs = []

    def __init__(self, settings):
        self.settings = settings

    def get_time_entries(self, start_date=None, end_date=None, user_id=None):
        return {"timelogs": self.existing_timelogs}

    def create_task_time_entry(self, task_id, payload):
        self.created_entries.append({"task_id": task_id, "payload": payload})
        date_key = f"{payload['date'][:4]}-{payload['date'][4:6]}-{payload['date'][6:8]}"
        minutes = int(payload["hours"]) * 60 + int(payload["minutes"])
        self.daily_totals[date_key] = self.daily_totals.get(date_key, 0) + minutes
        return {"time-entry": {"id": len(self.created_entries)}}

    def get_timesheets(self, start_date=None, end_date=None, user_id=None):
        return {"meta": {"dailyTotals": dict(self.daily_totals)}}


def install_fake(monkeypatch, daily_totals, existing_timelogs=None):
    FakeTeamworkClient.created_entries = []
    FakeTeamworkClient.daily_totals = dict(daily_totals)
    FakeTeamworkClient.existing_timelogs = list(existing_timelogs or [])
    monkeypatch.setattr(
        main_module,
        "get_teamwork_settings",
        lambda: TeamworkSettings(site="doppiogroup.teamwork.com", user_id="531538", api_key="token"),
    )
    monkeypatch.setattr(main_module, "TeamworkClient", FakeTeamworkClient)


def test_timesheet_filler_uses_configured_task_id_and_fills_week_to_40h(monkeypatch):
    install_fake(
        monkeypatch,
        {
            "2026-07-06": 240,
            "2026-07-07": 300,
            "2026-07-08": 300,
            "2026-07-09": 390,
            "2026-07-10": 345,
        },
    )

    response = TestClient(app).post(
        "/api/teamwork/timesheet-filler",
        json={"start": "2026-07-06", "end": "2026-07-10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["fillerTaskId"] == FILLER_TASK_ID
    assert payload["weeklyRemainingMinutes"] == 0
    assert sum(item["minutes"] for item in payload["created"]) == 825
    assert {entry["task_id"] for entry in FakeTeamworkClient.created_entries} == {FILLER_TASK_ID}
    assert all(entry["payload"]["person-id"] == "531538" for entry in FakeTeamworkClient.created_entries)
    assert {entry["payload"]["description"] for entry in FakeTeamworkClient.created_entries} >= {
        "Slack / Ticket / Jira Reviews",
        "Email / Administration",
        FILLER_DESCRIPTION,
    }
    assert payload["dailyTotals"] == {
        "2026-07-06": 480,
        "2026-07-07": 480,
        "2026-07-08": 480,
        "2026-07-09": 480,
        "2026-07-10": 480,
    }


def test_timesheet_filler_skips_existing_category_for_date(monkeypatch):
    install_fake(
        monkeypatch,
        {"2026-07-06": 240},
        existing_timelogs=[
            {
                "taskId": FILLER_TASK_ID,
                "description": "Slack / Ticket / Jira Reviews",
                "date": "2026-07-06",
            }
        ],
    )

    response = TestClient(app).post(
        "/api/teamwork/timesheet-filler",
        json={"start": "2026-07-06", "end": "2026-07-06"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["description"] == "Slack / Ticket / Jira Reviews" for item in payload["skipped"])
    created_descriptions = [entry["payload"]["description"] for entry in FakeTeamworkClient.created_entries]
    assert "Slack / Ticket / Jira Reviews" not in created_descriptions
    assert created_descriptions == ["Email / Administration", FILLER_DESCRIPTION]
