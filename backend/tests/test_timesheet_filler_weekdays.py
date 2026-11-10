from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app, FILLER_DESCRIPTION, FILLER_TASK_ID
from app.teamwork import TeamworkSettings


class FakeTeamworkClient:
    created_entries = []
    daily_totals = {}
    unavailable_totals = {}
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
        self.existing_timelogs.append({
            "taskId": task_id, "date": date_key,
            "description": payload["description"], "minutes": minutes,
        })
        return {"time-entry": {"id": len(self.created_entries)}}

    def get_timesheets(self, start_date=None, end_date=None, user_id=None):
        return {"meta": {"dailyTotals": dict(self.daily_totals)}}


def install_fake(monkeypatch, daily_totals, existing_timelogs=None, unavailable_totals=None):
    FakeTeamworkClient.created_entries = []
    FakeTeamworkClient.daily_totals = dict(daily_totals)
    FakeTeamworkClient.unavailable_totals = dict(unavailable_totals or {})
    FakeTeamworkClient.existing_timelogs = list(existing_timelogs or [])
    monkeypatch.setattr(
        main_module,
        "get_teamwork_settings",
        lambda: TeamworkSettings(site="doppiogroup.teamwork.com", user_id="531538", api_key="token"),
    )
    monkeypatch.setattr(main_module, "TeamworkClient", FakeTeamworkClient)
    monkeypatch.setattr(
        main_module,
        "_unavailable_daily_totals",
        lambda client, start, end, user_id: (dict(FakeTeamworkClient.unavailable_totals), []),
    )


def test_timesheet_filler_plan_uses_configured_task_id_and_does_not_create(monkeypatch):
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
        "/api/teamwork/timesheet-filler/plan",
        json={"start": "2026-07-06", "end": "2026-07-10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "planned"
    assert payload["fillerTaskId"] == FILLER_TASK_ID
    assert payload["weeklyCurrentMinutes"] == 1575
    assert payload["weeklyRemainingMinutes"] == 825
    assert sum(item["minutes"] for item in payload["plan"]) == 825
    assert payload["projectedWeeklyMinutes"] == 2400
    assert FakeTeamworkClient.created_entries == []
    assert {item["taskId"] for item in payload["plan"]} == {FILLER_TASK_ID}
    assert {item["description"] for item in payload["plan"]} >= {
        "Slack / Ticket / Jira Reviews",
        "Email / Administration",
        FILLER_DESCRIPTION,
    }


def test_timesheet_filler_create_requires_approved_plan(monkeypatch):
    install_fake(monkeypatch, {"2026-07-06": 240})

    response = TestClient(app).post(
        "/api/teamwork/timesheet-filler/create",
        json={"start": "2026-07-06", "end": "2026-07-06"},
    )

    assert response.status_code == 400
    assert FakeTeamworkClient.created_entries == []


def test_timesheet_filler_create_approved_plan_posts_to_configured_task(monkeypatch):
    install_fake(
        monkeypatch,
        {
            "2026-07-06": 240,
            "2026-07-07": 480,
            "2026-07-08": 480,
            "2026-07-09": 480,
            "2026-07-10": 480,
        },
    )
    client = TestClient(app)
    plan_response = client.post(
        "/api/teamwork/timesheet-filler/plan",
        json={"start": "2026-07-06", "end": "2026-07-10"},
    )
    plan = plan_response.json()["plan"]

    response = client.post(
        "/api/teamwork/timesheet-filler/create",
        json={"start": "2026-07-06", "end": "2026-07-10", "plan": plan},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["fillerTaskId"] == FILLER_TASK_ID
    assert payload["weeklyRemainingMinutes"] == 0
    assert sum(item["minutes"] for item in payload["created"]) == 240
    assert {entry["task_id"] for entry in FakeTeamworkClient.created_entries} == {FILLER_TASK_ID}
    assert [entry["payload"]["description"] for entry in FakeTeamworkClient.created_entries] == [
        "Slack / Ticket / Jira Reviews",
        "Email / Administration",
        FILLER_DESCRIPTION,
    ]


def test_timesheet_filler_plan_counts_unavailable_time_toward_40h(monkeypatch):
    install_fake(
        monkeypatch,
        {
            "2026-06-01": 600,
            "2026-06-02": 450,
            "2026-06-03": 330,
            "2026-06-04": 90,
            "2026-06-05": 330,
        },
        unavailable_totals={"2026-06-04": 480},
    )

    response = TestClient(app).post(
        "/api/teamwork/timesheet-filler/plan",
        json={"start": "2026-06-01", "end": "2026-06-05"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["weeklyCurrentMinutes"] == 2280
    assert payload["weeklyRemainingMinutes"] == 120
    assert payload["plannedMinutes"] == 120
    assert payload["projectedWeeklyMinutes"] == 2400
    assert sum(item["minutes"] for item in payload["plan"]) == 120
    assert all(item["date"] != "2026-06-04" for item in payload["plan"])
    assert FakeTeamworkClient.created_entries == []


def test_timesheet_filler_plan_skips_existing_category_for_date(monkeypatch):
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
        "/api/teamwork/timesheet-filler/plan",
        json={"start": "2026-07-06", "end": "2026-07-06"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["description"] == "Slack / Ticket / Jira Reviews" for item in payload["skipped"])
    planned_descriptions = [item["description"] for item in payload["plan"]]
    assert planned_descriptions == ["Email / Administration", FILLER_DESCRIPTION]
    assert FakeTeamworkClient.created_entries == []


def test_filler_can_create_one_row_then_bulk_submit_only_remaining(monkeypatch):
    install_fake(monkeypatch, {
        "2026-07-06": 240,
        "2026-07-07": 480, "2026-07-08": 480,
        "2026-07-09": 480, "2026-07-10": 480,
    })
    client = TestClient(app)
    scope = {"start": "2026-07-06", "end": "2026-07-10"}
    plan = client.post("/api/teamwork/timesheet-filler/plan", json=scope).json()["plan"]
    assert len(plan) == 3

    single = client.post("/api/teamwork/timesheet-filler/create", json={**scope, "plan": [plan[2]]})
    assert single.status_code == 200
    assert len(single.json()["created"]) == 1
    assert FakeTeamworkClient.created_entries[0]["payload"]["isbillable"] == "0"
    remaining = client.post("/api/teamwork/timesheet-filler/plan", json=scope).json()["plan"]
    assert len(remaining) == 2
    assert plan[2] not in remaining

    bulk = client.post("/api/teamwork/timesheet-filler/create", json={**scope, "plan": remaining})
    assert bulk.status_code == 200
    assert len(bulk.json()["created"]) == 2
    assert bulk.json()["weeklyRemainingMinutes"] == 0
    assert len(FakeTeamworkClient.created_entries) == 3


def test_filler_rejects_replayed_or_stale_rows_without_extra_writes(monkeypatch):
    install_fake(monkeypatch, {
        "2026-07-06": 240,
        "2026-07-07": 480, "2026-07-08": 480,
        "2026-07-09": 480, "2026-07-10": 480,
    })
    client = TestClient(app)
    scope = {"start": "2026-07-06", "end": "2026-07-10"}
    row = client.post("/api/teamwork/timesheet-filler/plan", json=scope).json()["plan"][0]
    first = client.post("/api/teamwork/timesheet-filler/create", json={**scope, "plan": [row, row]}).json()
    assert len(first["created"]) == 1
    assert len(first["skipped"]) == 1
    again = client.post("/api/teamwork/timesheet-filler/create", json={**scope, "plan": [row]}).json()
    assert len(again["created"]) == 0
    assert len(again["skipped"]) == 1
    assert len(FakeTeamworkClient.created_entries) == 1

    # Another time entry appeared since planning; the old recommendation is
    # no longer valid and must not push the week or day above the target.
    stale = client.post("/api/teamwork/timesheet-filler/plan", json=scope).json()["plan"]
    FakeTeamworkClient.daily_totals["2026-07-06"] = 480
    refused = client.post("/api/teamwork/timesheet-filler/create", json={**scope, "plan": stale}).json()
    assert refused["created"] == []
    assert len(FakeTeamworkClient.created_entries) == 1
