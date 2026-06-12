import os
from typing import Any
import httpx
from datetime import datetime
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
            if not r.content:
                return {}
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
        data = self._get(base, params)
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        while ((meta.get("page") or {}).get("hasMore", False) if isinstance(meta, dict) else False):
            params["page"] = int(params.get("page", 1)) + 1
            next_data = self._get(base, params)
            if not isinstance(next_data, dict) or "timelogs" not in next_data:
                break
            data["timelogs"] = (data.get("timelogs") or []) + (next_data.get("timelogs") or [])
            meta = next_data.get("meta", {})
        return data

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
        """Get calendar events using Teamwork's cursor pagination.

        Teamwork's v3 calendar endpoint can ignore date params and returns a
        cursor stream. Walk pages until we pass the requested end date.
        """
        base = f"https://{self.settings.site}/projects/api/v3/calendars/{calendar_id}/events.json"
        start_bound = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_bound = datetime.strptime(end_date, "%Y-%m-%d").date()
        cursor: str | None = None
        events: list[dict[str, Any]] = []
        max_pages = 150

        def event_date(ev: dict[str, Any]):
            raw = ev.get("start") or ev.get("startDate") or ev.get("start_at") or ""
            if isinstance(raw, dict):
                raw = raw.get("dateTime") or raw.get("date") or ""
            if not raw:
                return None
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
            except Exception:
                return None

        for _ in range(max_pages):
            params: dict[str, Any] = {
                "startDate": start_date,
                "endDate": end_date,
                "limit": 200,
            }
            if cursor:
                params["cursor"] = cursor
            data = self._get(base, params)
            page_events = data.get("events", []) or data.get("calendarEvents", []) or []
            if not page_events:
                break

            saw_after_end = False
            for ev in page_events:
                d = event_date(ev)
                if d is None:
                    events.append(ev)
                    continue
                if start_bound <= d <= end_bound:
                    events.append(ev)
                if d > end_bound:
                    saw_after_end = True
            if saw_after_end:
                break

            meta = data.get("meta", {}) if isinstance(data, dict) else {}
            next_cursor = meta.get("nextCursor") if isinstance(meta, dict) else None
            if not next_cursor:
                break
            cursor = next_cursor
        return events

    def get_workload(self, start_date: str, end_date: str) -> dict[str, Any]:
        base = f"https://{self.settings.site}/projects/api/v3/workload.json"
        params: dict[str, Any] = {"startDate": start_date, "endDate": end_date, "pageSize": 500, "pageOffset": 0}
        data = self._get(base, params)
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        while ((meta.get("page") or {}).get("hasMore", False) if isinstance(meta, dict) else False):
            params["pageOffset"] = int(params.get("pageOffset", 0)) + int(params.get("pageSize", 500))
            next_data = self._get(base, params)
            if not isinstance(next_data, dict):
                break
            current_users = ((data.get("workload") or {}).get("users") or [])
            next_users = ((next_data.get("workload") or {}).get("users") or [])
            data.setdefault("workload", {})["users"] = current_users + next_users
            meta = next_data.get("meta", {})
        return data

    def get_calendar_events_generic(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        base = f"https://{self.settings.site}/projects/api/v3/calendar/events.json"
        params: dict[str, Any] = {"startDate": start_date, "endDate": end_date, "pageSize": 500, "pageOffset": 0}
        data = self._get(base, params)
        events = data.get("calendarEvents", []) or []
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        while ((meta.get("page") or {}).get("hasMore", False) if isinstance(meta, dict) else False):
            params["pageOffset"] = int(params.get("pageOffset", 0)) + int(params.get("pageSize", 500))
            next_data = self._get(base, params)
            if not isinstance(next_data, dict):
                break
            events += next_data.get("calendarEvents", []) or []
            meta = next_data.get("meta", {})
        return events

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

    def log_calendar_event_time(self, calendar_id: int | str, event_id: str, timelog: dict[str, Any]) -> dict[str, Any]:
        """Create time from a calendar event so Teamwork can link mappedTaskIds."""
        base = f"https://{self.settings.site}/projects/api/v3/calendars/{calendar_id}/events/{event_id}/time.json"
        return self._post(base, {"timelog": timelog})

    def create_task_time_entry(self, task_id: int | str, time_entry: dict[str, Any]) -> dict[str, Any]:
        """Create a plain task time entry using Teamwork's v1 endpoint."""
        base = f"https://{self.settings.site}/tasks/{task_id}/time_entries.json"
        return self._post(base, {"time-entry": time_entry})


def teamwork_status_payload() -> dict[str, object]:
    s = get_teamwork_settings()
    return {
        "connected": s.has_credentials,
        "site": s.site,
        "user_id": s.user_id,
    }
