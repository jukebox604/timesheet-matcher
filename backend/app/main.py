from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.teamwork import TeamworkClient, get_teamwork_settings, teamwork_status_payload
from app.models import init_db, insert_proposal
from app.matcher import match_and_propose
from app.auth import router as auth_router

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"
INDEX_FILE = FRONTEND_DIST / "index.html"

app = FastAPI(title=settings.app_name)

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
    try:
        payload = TeamworkClient(settings=teamwork_settings).get_timesheets(
            start_date=startDate,
            end_date=endDate,
            user_id=userId,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    timesheets = payload.get("timesheets", [])
    meta = payload.get("meta", {}) or {}
    totals = ((meta.get("dailyTotals") or {}) if isinstance(meta, dict) else {})
    return {
        "site": teamwork_settings.site,
        "user_id": userId or teamwork_settings.user_id,
        "query": {"startDate": startDate, "endDate": endDate},
        "count": len(timesheets),
        "dailyTotals": totals,
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
    for cal in calendars:
        cal_id = cal.get("id")
        if not cal_id:
            continue
        try:
            events = client.get_calendar_events(cal_id, start, end)
            for ev in events:
                ev["_calendar_name"] = cal.get("name", "")
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
                # Compute duration in minutes
                if ev.get("duration_minutes") is None and ev["start_at"] and ev["end_at"]:
                    try:
                        from datetime import datetime
                        s = datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00"))
                        e = datetime.fromisoformat(ev["end_at"].replace("Z", "+00:00"))
                        ev["duration_minutes"] = int((e - s).total_seconds() / 60)
                    except Exception:
                        ev["duration_minutes"] = 0
            all_events.extend(events)
        except Exception:
            pass

    # Sort by start_at
    all_events.sort(key=lambda e: e.get("start_at", ""))

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
