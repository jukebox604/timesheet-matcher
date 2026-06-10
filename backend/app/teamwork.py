import os
from typing import Any
import httpx
from difflib import SequenceMatcher

class TeamworkSettings:
    def __init__(self, api_key: str = "", site: str = "", user_id: str = "") -> None:
        self.api_key = api_key
        self.site = site
        self.user_id = user_id

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.site)


def get_teamwork_settings() -> TeamworkSettings:
    return TeamworkSettings(
        api_key=os.environ.get("TEAMWORK_API_KEY", ""),
        site=os.environ.get("TEAMWORK_SITE", ""),
        user_id=os.environ.get("TEAMWORK_USER_ID", ""),
    )


class TeamworkClient:
    def __init__(self, settings: TeamworkSettings | None = None) -> None:
        self.settings = settings or get_teamwork_settings()
        if not self.settings.has_credentials:
            raise RuntimeError("Teamwork credentials are not configured")

    @property
    def _auth(self):
        return httpx.BasicAuth(self.settings.api_key, "password")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=20) as client:
            r = client.get(path, headers={"Accept": "application/json"}, auth=self._auth, params=params)
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=20) as client:
            r = client.post(path, headers={"Accept": "application/json", "Content-Type": "application/json"}, auth=self._auth, json=data)
            r.raise_for_status()
            return r.json()

    def get_timesheets(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "startDate": start_date or "",
            "endDate": end_date or "",
            "include": "timelogs,tasks,tasks.tasklist,projects,projects.permissions,projects.integrations,timesheetsCustomRows,unavailableTimes,timeApprovals",
            "pageSize": 100,
            "page": 1,
        }
        if user_id:
            params["userId"] = user_id
        base = f"https://{self.settings.site}/projects/api/v3/timesheets.json"
        data = self._get(base, params)
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        while ((meta.get("page") or {}).get("hasMore", False) if isinstance(meta, dict) else False):
            params["page"] = int(params.get("page", 1)) + 1
            next_data = self._get(base, params)
            if not isinstance(next_data, dict) or "timesheets" not in next_data:
                break
            existing = data.get("timesheets", [])
            data["timesheets"] = existing + next_data.get("timesheets", [])
            meta = next_data.get("meta", {})
        return data

    def get_time_entries(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "startDate": start_date or "",
            "endDate": end_date or "",
            "pageSize": 100,
            "page": 1,
        }
        if user_id:
            params["userId"] = user_id
        base = f"https://{self.settings.site}/projects/api/v3/time.json"
        return self._get(base, params)

    def list_calendars(self) -> list[dict[str, Any]]:
        """List calendars available to the user."""
        base = f"https://{self.settings.site}/projects/api/v3/calendars.json"
        data = self._get(base, {"pageSize": 100})
        return data.get("calendars", [])

    def get_calendar_events(
        self,
        calendar_id: int | str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Get events (including unavailable blocks) from a calendar."""
        base = f"https://{self.settings.site}/projects/api/v3/calendars/{calendar_id}/events.json"
        data = self._get(base, {
            "startDate": start_date,
            "endDate": end_date,
            "pageSize": 200,
        })
        return data.get("events", [])

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects."""
        base = f"https://{self.settings.site}/projects/api/v3/projects.json"
        data = self._get(base, {"pageSize": 500})
        projects = data.get("projects", [])
        # Filter to active, non-archived
        return [p for p in projects if not p.get("archived", False)]

    def list_tasks(self, project_id: int | str) -> list[dict[str, Any]]:
        """List tasks for a project."""
        base = f"https://{self.settings.site}/projects/api/v3/projects/{project_id}/tasks.json"
        data = self._get(base, {"pageSize": 500})
        return data.get("tasks", [])


def teamwork_status_payload() -> dict[str, object]:
    s = get_teamwork_settings()
    return {
        "connected": s.has_credentials,
        "site": s.site,
        "user_id": s.user_id,
    }
