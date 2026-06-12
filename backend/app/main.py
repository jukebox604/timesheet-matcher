from datetime import datetime, timezone, timedelta, date
import re
from pathlib import Path
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.teamwork import TeamworkClient, get_teamwork_settings, teamwork_status_payload
from app.models import init_db, insert_proposal
from app.matcher import match_and_propose
from app.auth import router as auth_router

EXCLUDED_MATCHING_EVENT_TITLES = (
    "am email review",
    "pm email review",
    "decompress",
    "personal commitment",
    "out of office",
)
PERSONAL_COMMITMENT_TITLE = "personal commitment"

FILLER_PROJECT_ID = 417162
FILLER_TASK_ID = 29936460
FILLER_DESCRIPTION = "Teamwork, Teamdesk, Slack, Email and Jira"
FILLER_START_TIME = "20:00"
FILLER_HOURS = 1
FILLER_MINUTES = 30
FILLER_BILLABLE = "0"
FILLER_TIMEZONE = ZoneInfo("America/Vancouver")
FILLER_LOCKS: dict[str, Lock] = {}
FILLER_LOCKS_GUARD = Lock()


def _is_excluded_matching_event(event: dict[str, Any]) -> bool:
    title = str(event.get("title") or event.get("summary") or "").lower()
    return any(excluded in title for excluded in EXCLUDED_MATCHING_EVENT_TITLES)


def _is_personal_commitment_event(event: dict[str, Any]) -> bool:
    title = str(event.get("title") or event.get("summary") or "").lower()
    return PERSONAL_COMMITMENT_TITLE in title


def _event_datetime_value(event: dict[str, Any], key: str) -> str:
    raw = event.get(key) or event.get(f"{key}Date") or event.get(f"{key}_at") or ""
    if isinstance(raw, dict):
        raw = raw.get("dateTime") or raw.get("date") or ""
    return str(raw or "")


def _parse_event_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=FILLER_TIMEZONE)
        return parsed
    except Exception:
        return None


def _event_local_date(event: dict[str, Any]) -> str:
    parsed = _parse_event_datetime(_event_datetime_value(event, "start"))
    if not parsed:
        return ""
    return parsed.astimezone(FILLER_TIMEZONE).date().isoformat()


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _entry_date(entry: dict[str, Any]) -> str:
    raw = entry.get("date") or ""
    value = str(raw)[:10].replace("/", "-")
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    if value:
        return value

    # Teamwork v3 timelogs often omit `date` and only return UTC `timeLogged`.
    # A Vancouver 20:00 filler entry appears as 03:00Z on the following day,
    # so convert back to the user's local date before duplicate checks.
    time_logged = str(entry.get("timeLogged") or entry.get("time-logged") or "")
    if time_logged:
        try:
            parsed = datetime.fromisoformat(time_logged.replace("Z", "+00:00"))
            return parsed.astimezone(FILLER_TIMEZONE).date().isoformat()
        except Exception:
            return time_logged[:10]
    return ""


def _entry_task_id(entry: dict[str, Any]) -> str:
    task = entry.get("task") or entry.get("todo-item") or entry.get("todoItem") or {}
    return str(
        entry.get("taskId")
        or entry.get("task-id")
        or entry.get("todoItemId")
        or entry.get("todo-item-id")
        or task.get("id")
        or ""
    )


def _entry_user_id(entry: dict[str, Any]) -> str:
    user = entry.get("user") or entry.get("person") or {}
    return str(
        entry.get("userId")
        or entry.get("user-id")
        or entry.get("personId")
        or entry.get("person-id")
        or user.get("id")
        or ""
    )


def _current_timelogs(client: TeamworkClient, start: str, end: str, user_id: str) -> list[dict[str, Any]] | None:
    """Return live Teamwork timelogs for the requested user/date range."""
    try:
        payload = client.get_time_entries(start, end, user_id)
    except Exception:
        return None
    entries = payload.get("timelogs") or payload.get("timeEntries") or []
    return [
        entry for entry in entries
        if isinstance(entry, dict)
        and (not user_id or not _entry_user_id(entry) or _entry_user_id(entry) == str(user_id))
    ]


def _event_start_value(event: dict[str, Any]) -> str:
    return _event_datetime_value(event, "start")


def _event_display_date(event: dict[str, Any]) -> str:
    raw = _event_start_value(event)
    return raw[:10] if raw else ""


def _event_start_time(event: dict[str, Any]) -> str:
    raw = _event_start_value(event)
    return raw[11:19] if len(raw) >= 19 else ""


def _event_duration_minutes(event: dict[str, Any]) -> int:
    if event.get("allDay"):
        return 480
    raw_minutes = event.get("duration_minutes") or event.get("minutes")
    if raw_minutes is not None:
        try:
            return max(0, int(raw_minutes))
        except Exception:
            pass
    start_dt = _parse_event_datetime(_event_datetime_value(event, "start"))
    end_dt = _parse_event_datetime(_event_datetime_value(event, "end"))
    if not start_dt or not end_dt:
        return 0
    return max(0, int((end_dt - start_dt).total_seconds() / 60))


def _entry_local_time(entry: dict[str, Any]) -> str:
    raw = str(entry.get("timeLogged") or entry.get("time-logged") or "")
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(FILLER_TIMEZONE).strftime("%H:%M:%S")
    except Exception:
        return ""


def _entry_raw_date(entry: dict[str, Any]) -> str:
    raw = str(entry.get("timeLogged") or entry.get("time-logged") or "")
    return raw[:10] if raw else ""


def _entry_raw_time(entry: dict[str, Any]) -> str:
    raw = str(entry.get("timeLogged") or entry.get("time-logged") or "")
    return raw[11:19] if len(raw) >= 19 else ""


def _timelog_matches_event(entry: dict[str, Any], event: dict[str, Any], task_id: int | str) -> bool:
    if _entry_task_id(entry) != str(task_id):
        return False
    return _timelog_matches_event_timebox(entry, event)


def _plain_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = text.replace(":+1:", " ").replace("👍", " ").replace("✅", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _text_words(value: str) -> set[str]:
    stop = {"event", "the", "and", "for", "with", "from", "this", "that", "work", "meeting", "call", "task", "created", "reclaim"}
    return {word for word in _plain_text(value).split() if len(word) >= 3 and word not in stop}


def _timelog_text_matches_event(entry: dict[str, Any], event: dict[str, Any]) -> bool:
    title = str(event.get("title") or event.get("summary") or "")
    description = _entry_description(entry)
    title_text = _plain_text(title)
    description_text = _plain_text(description)
    if title_text and title_text in description_text:
        return True
    title_words = _text_words(title)
    if not title_words:
        return False
    description_words = _text_words(description)
    overlap = title_words & description_words
    return len(overlap) >= 2 and (len(overlap) / len(title_words)) >= 0.45


def _timelog_matches_event_timebox(entry: dict[str, Any], event: dict[str, Any]) -> bool:
    if _event_display_date(event) not in {_entry_date(entry), _entry_raw_date(entry)}:
        return False
    if int(entry.get("minutes") or 0) != _event_duration_minutes(event):
        return False
    event_time = _event_start_time(event)
    if event_time and event_time not in {_entry_raw_time(entry), _entry_local_time(entry)}:
        return False
    return True


def _timelog_matches_event_shape(entry: dict[str, Any], event: dict[str, Any]) -> bool:
    return _timelog_matches_event_timebox(entry, event) and _timelog_text_matches_event(entry, event)


def _drop_stale_mapped_task_ids(events: list[dict[str, Any]], live_timelogs: list[dict[str, Any]] | None) -> None:
    """Reconcile calendar mappedTaskIds with live timelogs.

    Calendar mappedTaskIds can be stale after deletion, while recurring/event
    edge cases can have a real timelog without mappedTaskIds. Use exact
    event-shaped live timelogs (date, duration, start time, title/description)
    to decide the displayed logged state.
    """
    if live_timelogs is None:
        return
    for event in events:
        mapped = event.get("mappedTaskIds")
        original_mapped = mapped if isinstance(mapped, list) else []
        current = [task_id for task_id in original_mapped if any(_timelog_matches_event(entry, event, task_id) for entry in live_timelogs)]
        if current:
            event["mappedTaskIds"] = current
            continue

        shaped_matches = [entry for entry in live_timelogs if _timelog_matches_event_shape(entry, event)]
        if shaped_matches:
            live_task_ids = []
            for entry in shaped_matches:
                task_id = _entry_task_id(entry)
                if task_id and int(task_id) not in live_task_ids:
                    live_task_ids.append(int(task_id))
            if original_mapped:
                event["staleMappedTaskIds"] = original_mapped
            event["mappedTaskIds"] = live_task_ids
            event["liveLoggedTaskIds"] = live_task_ids
        elif original_mapped:
            event["staleMappedTaskIds"] = original_mapped
            event["mappedTaskIds"] = []


def _entry_description(entry: dict[str, Any]) -> str:
    return str(entry.get("description") or entry.get("body") or "")


def _entry_matches(entry: dict[str, Any], *, date: str, task_id: int | str, description: str | None = None) -> bool:
    if _entry_date(entry) != date:
        return False
    if _entry_task_id(entry) != str(task_id):
        return False
    if description is not None and _entry_description(entry).strip() != description.strip():
        return False
    return True


def _existing_timelogs(client: TeamworkClient, start: str, end: str, user_id: str) -> list[dict[str, Any]]:
    payload = client.get_time_entries(start_date=start, end_date=end, user_id=user_id)
    return payload.get("timelogs", []) or payload.get("timeEntries", []) or payload.get("time-entries", []) or []


def _filler_lock_for(user_id: str, start: str, end: str) -> Lock:
    key = f"{user_id}:{start}:{end}"
    with FILLER_LOCKS_GUARD:
        if key not in FILLER_LOCKS:
            FILLER_LOCKS[key] = Lock()
        return FILLER_LOCKS[key]


def _calendar_timelog_payload(entry: dict[str, Any]) -> dict[str, Any]:
    start_at = str(entry.get("start") or entry.get("start_at") or "")
    date = str(entry.get("date") or start_at[:10])
    time = str(entry.get("time") or (start_at[11:19] if len(start_at) >= 19 else "09:00:00"))
    if len(time) == 5:
        time = f"{time}:00"
    return {
        "date": date,
        "time": time,
        "hasStartTime": True,
        "minutes": int(entry.get("minutes") or entry.get("duration_minutes") or 0),
        "description": str(entry.get("description") or f"Event: {entry.get('title', '')}"),
        "projectId": int(entry["projectId"]),
        "taskId": int(entry["taskId"]),
        "isBillable": bool(entry.get("isBillable", False)),
    }


def _date_strings(start: str, end: str) -> list[str]:
    try:
        current = _parse_date(start).date()
        end_date = _parse_date(end).date()
    except Exception:
        return []
    dates: list[str] = []
    while current <= end_date:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _event_minutes_for_date(event: dict[str, Any], target_date: str) -> int:
    if event.get("allDay"):
        return 480
    start_raw = str(event.get("startDate") or event.get("start") or "")
    end_raw = str(event.get("endDate") or event.get("end") or "")
    if start_raw[:10] != target_date:
        return 0
    try:
        start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
        return max(0, int((end_dt - start_dt).total_seconds() / 60))
    except Exception:
        return 0


def _unavailable_daily_totals(client: TeamworkClient, start: str, end: str, user_id: str) -> tuple[dict[str, int], list[dict[str, Any]]]:
    dates = _date_strings(start, end)
    totals = {day: 0 for day in dates}
    if not dates or not user_id:
        return totals, []
    workload = client.get_workload(start, end)
    users = ((workload.get("workload") or {}).get("users") or []) if isinstance(workload, dict) else []
    user_row = next((row for row in users if str(row.get("userId") or (row.get("user") or {}).get("id")) == str(user_id)), None)
    if not user_row:
        return totals, []

    events_by_id = {str(event.get("id")): event for event in client.get_calendar_events_generic(start, end)}
    included_events: list[dict[str, Any]] = []
    seen_events: set[tuple[str, str]] = set()
    for day, info in (user_row.get("dates") or {}).items():
        if day not in totals or not isinstance(info, dict):
            continue
        event_refs = info.get("events") or []
        for ref in event_refs:
            event_id = str((ref or {}).get("id") or "")
            if not event_id or (day, event_id) in seen_events:
                continue
            seen_events.add((day, event_id))
            event = events_by_id.get(event_id)
            minutes = _event_minutes_for_date(event or {}, day) if event else 0
            if minutes <= 0:
                minutes = int(info.get("capacityMinutes") or 0)
            if minutes > 0:
                totals[day] += min(minutes, 480)
                included_events.append({
                    "id": event_id,
                    "date": day,
                    "minutes": min(minutes, 480),
                    "title": (event or {}).get("title") or "Unavailable",
                    "typeId": (event or {}).get("typeId"),
                    "startDate": (event or {}).get("startDate"),
                    "endDate": (event or {}).get("endDate"),
                })
    return totals, included_events


def _personal_commitment_daily_totals(client: TeamworkClient, start: str, end: str) -> tuple[dict[str, int], list[dict[str, Any]]]:
    dates = _date_strings(start, end)
    totals = {day: 0 for day in dates}
    if not dates:
        return totals, []
    events: list[dict[str, Any]] = []
    for event in client.get_calendar_events(1306, start, end):
        if not _is_personal_commitment_event(event):
            continue
        day = _event_local_date(event)
        if day not in totals:
            continue
        minutes = _event_duration_minutes(event)
        if minutes <= 0:
            continue
        totals[day] += minutes
        events.append({
            "id": str(event.get("id") or ""),
            "date": day,
            "minutes": minutes,
            "title": event.get("title") or event.get("summary") or "Personal Commitment",
            "start": _event_datetime_value(event, "start"),
            "end": _event_datetime_value(event, "end"),
            "loggedAsUnavailable": False,
        })
    return totals, events


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"
INDEX_FILE = FRONTEND_DIST / "index.html"

app = FastAPI(title=settings.app_name)


@app.middleware("http")
async def no_store_api_responses(request: Request, call_next) -> Response:
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Register auth routes (Google OAuth)
app.include_router(auth_router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "app": settings.app_name,
        "status": "ok",
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/teamwork/status")
def teamwork_status() -> dict[str, object]:
    return teamwork_status_payload()


@app.get("/api/teamwork/timesheets")
def teamwork_timesheets(
    startDate: str | None = Query(default=None, description="YYYY-MM-DD"),
    endDate: str | None = Query(default=None, description="YYYY-MM-DD"),
    userId: str | None = Query(default=None),
) -> dict[str, object]:
    teamwork_settings = get_teamwork_settings()
    if not teamwork_settings.has_credentials:
        raise HTTPException(status_code=503, detail="Teamwork is not configured")
    client = TeamworkClient(settings=teamwork_settings)
    effective_user_id = userId or teamwork_settings.user_id
    try:
        payload = client.get_timesheets(
            start_date=startDate,
            end_date=endDate,
            user_id=effective_user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    timesheets = payload.get("timesheets", [])
    meta = payload.get("meta", {}) or {}
    totals = ((meta.get("dailyTotals") or {}) if isinstance(meta, dict) else {})
    unavailable_totals: dict[str, int] = {}
    unavailable_events: list[dict[str, Any]] = []
    personal_commitment_totals: dict[str, int] = {}
    personal_commitment_events: list[dict[str, Any]] = []
    if startDate and endDate and effective_user_id:
        try:
            unavailable_totals, unavailable_events = _unavailable_daily_totals(client, startDate, endDate, str(effective_user_id))
        except Exception:
            unavailable_totals, unavailable_events = {}, []
        try:
            personal_commitment_totals, personal_commitment_events = _personal_commitment_daily_totals(client, startDate, endDate)
        except Exception:
            personal_commitment_totals, personal_commitment_events = {}, []
    credited_totals = {
        day: int(totals.get(day, 0) or 0) + int(unavailable_totals.get(day, 0) or 0)
        for day in sorted(set(totals) | set(unavailable_totals))
    }
    personal_commitment_unlogged_totals = {
        day: max(int(personal_commitment_totals.get(day, 0) or 0) - int(unavailable_totals.get(day, 0) or 0), 0)
        for day in sorted(set(personal_commitment_totals) | set(unavailable_totals))
    }
    return {
        "site": teamwork_settings.site,
        "user_id": effective_user_id,
        "query": {"startDate": startDate, "endDate": endDate},
        "count": len(timesheets),
        "dailyTotals": totals,
        "unavailableDailyTotals": unavailable_totals,
        "creditedDailyTotals": credited_totals,
        "personalCommitmentDailyTotals": personal_commitment_totals,
        "personalCommitmentUnloggedDailyTotals": personal_commitment_unlogged_totals,
        "unavailableEvents": unavailable_events,
        "personalCommitmentEvents": personal_commitment_events,
        "timesheets": timesheets,
    }


@app.get("/api/teamwork/calendars")
def list_calendars() -> dict[str, object]:
    teamwork_settings = get_teamwork_settings()
    if not teamwork_settings.has_credentials:
        raise HTTPException(status_code=503, detail="Teamwork is not configured")
    try:
        calendars = TeamworkClient(settings=teamwork_settings).list_calendars()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"calendars": calendars}


@app.get("/api/teamwork/events")
def get_events(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
) -> dict[str, object]:
    teamwork_settings = get_teamwork_settings()
    if not teamwork_settings.has_credentials:
        raise HTTPException(status_code=503, detail="Teamwork is not configured")
    client = TeamworkClient(settings=teamwork_settings)
    try:
        calendars = client.list_calendars()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch calendars: {exc}")

    all_events: list[dict[str, Any]] = []
    # The matching page is driven from Marc's Google-synced calendar. Avoid the
    # blocked_time calendar here; it is for project-linked time blocks, not the
    # personal calendar import flow.
    target_calendars = [cal for cal in calendars if str(cal.get("id")) == "1306"] or calendars
    for cal in target_calendars:
        cal_id = cal.get("id")
        if not cal_id:
            continue
        try:
            events = client.get_calendar_events(cal_id, start, end)
            for ev in events:
                ev["_calendar_name"] = cal.get("name", "")
                ev["calendarId"] = cal_id
                # Normalize field names
                ev["title"] = ev.get("summary", ev.get("title", ""))
                ev_start = ev.get("start", {})
                ev_end = ev.get("end", {})
                if isinstance(ev_start, dict):
                    ev["start_at"] = ev_start.get("dateTime", "")
                else:
                    ev["start_at"] = str(ev_start)
                if isinstance(ev_end, dict):
                    ev["end_at"] = ev_end.get("dateTime", "")
                else:
                    ev["end_at"] = str(ev_end)
                # Frontend expects strings; do not leak Teamwork's nested start/end dicts.
                ev["start"] = ev.get("start_at", "")
                ev["end"] = ev.get("end_at", "")
                # Compute duration in minutes
                if ev.get("duration_minutes") is None and ev["start_at"] and ev["end_at"]:
                    try:
                        s = datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00"))
                        e = datetime.fromisoformat(ev["end_at"].replace("Z", "+00:00"))
                        ev["duration_minutes"] = int((e - s).total_seconds() / 60)
                    except Exception:
                        ev["duration_minutes"] = 0
            all_events.extend(events)
        except Exception:
            pass

    # Teamwork calendar endpoints can ignore date params; filter on normalized start_at here.
    try:
        filter_start = datetime.strptime(start, "%Y-%m-%d").date()
        filter_end = datetime.strptime(end, "%Y-%m-%d").date()
        filtered_events: list[dict[str, Any]] = []
        for ev in all_events:
            ev_start = str(ev.get("start_at") or ev.get("start") or "")
            if not ev_start:
                filtered_events.append(ev)
                continue
            try:
                ev_date = datetime.fromisoformat(ev_start.replace("Z", "+00:00")).date()
                if filter_start <= ev_date <= filter_end:
                    filtered_events.append(ev)
            except Exception:
                filtered_events.append(ev)
        all_events = filtered_events
    except Exception:
        pass

    all_events = [ev for ev in all_events if not _is_excluded_matching_event(ev)]

    live_timelogs = _current_timelogs(client, start, end, teamwork_settings.user_id or "")
    _drop_stale_mapped_task_ids(all_events, live_timelogs)

    # Sort by start_at
    all_events.sort(key=lambda e: str(e.get("start_at", "")))

    return {
        "query": {"start": start, "end": end},
        "count": len(all_events),
        "events": all_events,
    }


@app.get("/api/teamwork/projects")
def list_projects() -> dict[str, object]:
    teamwork_settings = get_teamwork_settings()
    if not teamwork_settings.has_credentials:
        raise HTTPException(status_code=503, detail="Teamwork is not configured")
    try:
        projects = TeamworkClient(settings=teamwork_settings).list_projects()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"projects": projects}


@app.get("/api/teamwork/projects/{project_id}/tasks")
def list_tasks(project_id: int) -> dict[str, object]:
    teamwork_settings = get_teamwork_settings()
    if not teamwork_settings.has_credentials:
        raise HTTPException(status_code=503, detail="Teamwork is not configured")
    try:
        tasks = TeamworkClient(settings=teamwork_settings).list_tasks(project_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"tasks": tasks}


@app.post("/api/teamwork/submit-matched")
def submit_matched(payload: dict[str, Any]) -> dict[str, object]:
    teamwork_settings = get_teamwork_settings()
    if not teamwork_settings.has_credentials:
        raise HTTPException(status_code=503, detail="Teamwork is not configured")
    client = TeamworkClient(settings=teamwork_settings)
    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        raise HTTPException(status_code=400, detail="entries must be a list")

    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        event_id = str(entry.get("eventId") or "")
        if entry.get("mappedTaskIds"):
            skipped.append({"eventId": event_id, "reason": "already linked in Teamwork"})
            continue
        if not event_id or not entry.get("projectId") or not entry.get("taskId"):
            skipped.append({"eventId": event_id, "reason": "missing project/task/event id"})
            continue
        timelog = _calendar_timelog_payload(entry)
        if timelog["minutes"] <= 0:
            skipped.append({"eventId": event_id, "reason": "zero duration"})
            continue
        try:
            result = client.log_calendar_event_time(entry.get("calendarId") or 1306, event_id, timelog)
            created.append({"eventId": event_id, "taskId": timelog["taskId"], "minutes": timelog["minutes"], "result": result})
        except Exception as exc:
            errors.append({"eventId": event_id, "error": str(exc)})

    return {"status": "ok" if not errors else "partial", "created": created, "skipped": skipped, "errors": errors}


@app.post("/api/teamwork/timesheet-filler")
def run_timesheet_filler(payload: dict[str, Any]) -> dict[str, object]:
    teamwork_settings = get_teamwork_settings()
    if not teamwork_settings.has_credentials:
        raise HTTPException(status_code=503, detail="Teamwork is not configured")
    user_id = teamwork_settings.user_id or "531538"
    start = str(payload.get("start") or "")
    end = str(payload.get("end") or "")
    if not start or not end:
        raise HTTPException(status_code=400, detail="start and end are required")

    client = TeamworkClient(settings=teamwork_settings)
    try:
        start_date = _parse_date(start).date()
        end_date = _parse_date(end).date()
    except Exception:
        raise HTTPException(status_code=400, detail="start/end must be YYYY-MM-DD")
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end must be on or after start")

    lock = _filler_lock_for(str(user_id), start, end)
    if not lock.acquire(blocking=False):
        return {
            "status": "running",
            "message": "Time Sheet Filler is already running for this loaded range. No new filler entries were created.",
            "created": [],
            "skipped": [],
            "existingDates": [],
            "dailyTotals": {},
        }

    try:
        workdays: list[date] = []
        cursor = start_date
        while cursor <= end_date:
            if cursor.weekday() < 5:
                workdays.append(cursor)
            cursor += timedelta(days=1)

        existing_end = (end_date + timedelta(days=1)).isoformat()
        existing = _existing_timelogs(client, start, existing_end, user_id)
        existing_filler_dates = sorted({
            day.isoformat()
            for day in workdays
            if any(_entry_matches(e, date=day.isoformat(), task_id=FILLER_TASK_ID, description=FILLER_DESCRIPTION) for e in existing)
        })

        # If any standard filler entries already exist in the loaded range, do not
        # create a partial second set. This keeps the button safe and makes the
        # duplicate state obvious to the user.
        if existing_filler_dates:
            verify_payload = client.get_timesheets(start_date=start, end_date=end, user_id=user_id)
            daily_totals = ((verify_payload.get("meta") or {}).get("dailyTotals") or {}) if isinstance(verify_payload, dict) else {}
            return {
                "status": "exists",
                "message": f"Time Sheet Filler entries already exist for {', '.join(existing_filler_dates)}. No new filler entries were created.",
                "created": [],
                "skipped": [
                    {"date": day.isoformat(), "reason": "filler entries already exist in this loaded range"}
                    for day in workdays
                ],
                "existingDates": existing_filler_dates,
                "dailyTotals": daily_totals,
            }

        created: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for day in workdays:
            date_key = day.isoformat()
            time_entry = {
                "description": FILLER_DESCRIPTION,
                "person-id": str(user_id),
                "date": day.strftime("%Y%m%d"),
                "time": FILLER_START_TIME,
                "hours": str(FILLER_HOURS),
                "minutes": str(FILLER_MINUTES),
                "isbillable": FILLER_BILLABLE,
            }
            try:
                result = client.create_task_time_entry(FILLER_TASK_ID, time_entry)
                created.append({"date": date_key, "taskId": FILLER_TASK_ID, "result": result})
            except Exception as exc:
                skipped.append({"date": date_key, "reason": str(exc)})

        verify_payload = client.get_timesheets(start_date=start, end_date=end, user_id=user_id)
        daily_totals = ((verify_payload.get("meta") or {}).get("dailyTotals") or {}) if isinstance(verify_payload, dict) else {}
        return {
            "status": "ok",
            "message": f"Created {len(created)} Time Sheet Filler entries; skipped {len(skipped)}.",
            "created": created,
            "skipped": skipped,
            "existingDates": [],
            "dailyTotals": daily_totals,
        }
    finally:
        lock.release()


@app.post("/api/proposals/generate")
def generate_proposals(
    startDate: str | None = Query(default=None, description="YYYY-MM-DD"),
    endDate: str | None = Query(default=None, description="YYYY-MM-DD"),
) -> dict[str, object]:
    teamwork_settings = get_teamwork_settings()
    if not teamwork_settings.has_credentials:
        raise HTTPException(status_code=503, detail="Teamwork is not configured")
    client = TeamworkClient(settings=teamwork_settings)
    try:
        payload = client.get_timesheets(startDate, endDate, teamwork_settings.user_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    timesheets = payload.get("timesheets", [])
    meta = payload.get("meta", {}) or {}
    totals = ((meta.get("dailyTotals") or {}) if isinstance(meta, dict) else {})
    created: list[dict] = []
    for sheet in timesheets:
        entity = sheet.get("entity") or {}
        task_name = (entity.get("name") or "").strip() or "<task>"
        dates = sheet.get("dates") or {}
        for date_key, detail in dates.items():
            minutes = ((detail or {}).get("totalMinutes") or 0)
            if minutes <= 0:
                continue
            proposal_id = insert_proposal({
                "task_id": str(entity.get("id", "")),
                "project_id": "",
                "task_name": task_name,
                "project_name": "<project>",
                "description": task_name,
                "date": date_key,
                "start_time": "",
                "end_time": "",
                "minutes": minutes,
                "matched": 1,
                "confidence": 1.0,
                "billable": 0,
            })
            created.append({"id": proposal_id, "date": date_key, "minutes": minutes, "task_name": task_name})
    return {
        "status": "ok",
        "query": {"startDate": startDate, "endDate": endDate},
        "created": created,
        "dailyTotals": totals,
    }


@app.get("/api/proposals")
def list_proposals(status: str | None = Query(default=None, description="Filter by status")) -> dict[str, object]:
    from app.models import fetch_proposals
    return {"status": status or "all", "items": fetch_proposals(status)}


@app.post("/api/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: int) -> dict[str, object]:
    from app.models import update_proposal_status
    update_proposal_status(proposal_id, "approved")
    return {"id": proposal_id, "status": "approved"}


@app.post("/api/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int) -> dict[str, object]:
    from app.models import update_proposal_status
    update_proposal_status(proposal_id, "rejected")
    return {"id": proposal_id, "status": "rejected"}


if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
def serve_react_app(full_path: str = "") -> FileResponse:
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    raise HTTPException(status_code=503, detail="Frontend build is not available yet")
