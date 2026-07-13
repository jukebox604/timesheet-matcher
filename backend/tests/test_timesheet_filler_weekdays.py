from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app, FILLER_DESCRIPTION, FILLER_TASK_ID
from app.teamwork import TeamworkSettings


class FakeTeamworkClient:
    created_entries = []

    def __init__(self, settings):
        self.settings = settings

    def get_time_entries(self, start_date=None, end_date=None, user_id=None):
        return {
            "timelogs": [
                {
                    "taskId": FILLER_TASK_ID,
                    "description": FILLER_DESCRIPTION,
                    "date": day,
                }
                for day in ["2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10"]
            ]
        }

    def create_task_time_entry(self, task_id, payload):
        self.created_entries.append({"task_id": task_id, "payload": payload})
        return {"time-entry": {"id": len(self.created_entries)}}

    def get_timesheets(self, start_date=None, end_date=None, user_id=None):
        return {"meta": {"dailyTotals": {}}}


def test_timesheet_filler_creates_missing_monday_when_other_weekdays_exist(monkeypatch):
    FakeTeamworkClient.created_entries = []
    monkeypatch.setattr(
        main_module,
        "get_teamwork_settings",
        lambda: TeamworkSettings(site="doppiogroup.teamwork.com", user_id="531538", api_key="token"),
    )
    monkeypatch.setattr(main_module, "TeamworkClient", FakeTeamworkClient)

    response = TestClient(app).post(
        "/api/teamwork/timesheet-filler",
        json={"start": "2026-07-06", "end": "2026-07-10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert [item["date"] for item in payload["created"]] == ["2026-07-06"]
    assert sorted(item["date"] for item in payload["skipped"]) == [
        "2026-07-07",
        "2026-07-08",
        "2026-07-09",
        "2026-07-10",
    ]
    assert FakeTeamworkClient.created_entries == [
        {
            "task_id": FILLER_TASK_ID,
            "payload": {
                "description": FILLER_DESCRIPTION,
                "person-id": "531538",
                "date": "20260706",
                "time": "20:00",
                "hours": "1",
                "minutes": "30",
                "isbillable": "0",
            },
        }
    ]
