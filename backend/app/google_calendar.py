import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
DEFAULT_TOKEN_FILE = "/workspace/backend/google-calendar-token.json"


def google_calendar_token_file() -> Path:
    return Path(os.getenv("GOOGLE_CALENDAR_TOKEN_FILE", DEFAULT_TOKEN_FILE))


def google_calendar_id() -> str:
    return os.getenv("GOOGLE_CALENDAR_ID", "primary")


def google_calendar_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and google_calendar_token_file().exists())


def save_google_calendar_tokens(tokens: dict[str, Any], user_info: dict[str, Any]) -> None:
    """Persist refreshable Google OAuth tokens for server-side Calendar reads.

    The Timesheet Matcher is single-user in production, so one token file is
    intentionally enough. Preserve an existing refresh_token because Google only
    sends it on the first offline consent grant unless prompt=consent is used.
    """
    token_file = google_calendar_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if token_file.exists():
        try:
            existing = json.loads(token_file.read_text())
        except Exception:
            existing = {}

    refresh_token = tokens.get("refresh_token") or existing.get("refresh_token")
    expires_in = int(tokens.get("expires_in") or 0)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 60, 0))).isoformat() if expires_in else existing.get("expires_at")
    payload = {
        "access_token": tokens.get("access_token") or existing.get("access_token"),
        "refresh_token": refresh_token,
        "scope": tokens.get("scope") or existing.get("scope") or "",
        "token_type": tokens.get("token_type") or existing.get("token_type") or "Bearer",
        "expires_at": expires_at,
        "user": {
            "sub": user_info.get("sub"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
        },
    }
    token_file.write_text(json.dumps(payload, indent=2))
    try:
        token_file.chmod(0o600)
    except Exception:
        pass


def _load_token() -> dict[str, Any]:
    token_file = google_calendar_token_file()
    if not token_file.exists():
        raise RuntimeError("Google Calendar is not connected. Log in again with Google Calendar permission.")
    return json.loads(token_file.read_text())


def _token_expired(token: dict[str, Any]) -> bool:
    expires_at = token.get("expires_at")
    if not expires_at:
        return True
    try:
        return datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")) <= datetime.now(timezone.utc)
    except Exception:
        return True


def _refresh_token(token: dict[str, Any]) -> dict[str, Any]:
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Google Calendar token has no refresh_token. Log out and log in again.")
    with httpx.Client(timeout=20) as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
    refreshed = response.json()
    merged = {**token, **refreshed, "refresh_token": refresh_token}
    expires_in = int(refreshed.get("expires_in") or 0)
    if expires_in:
        merged["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 60, 0))).isoformat()
    google_calendar_token_file().write_text(json.dumps(merged, indent=2))
    return merged


def google_calendar_access_token() -> str:
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("Google OAuth client is not configured")
    token = _load_token()
    if _token_expired(token):
        token = _refresh_token(token)
    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError("Google Calendar token has no access_token. Log in again.")
    return str(access_token)


def list_google_calendar_events(start_date: str, end_date: str, calendar_id: str | None = None) -> list[dict[str, Any]]:
    """Read Google Calendar events for an inclusive YYYY-MM-DD date range."""
    access_token = google_calendar_access_token()
    calendar = calendar_id or google_calendar_id()
    start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    # Google Calendar timeMax is exclusive, so add one day to the requested end.
    end_dt = (datetime.fromisoformat(end_date) + timedelta(days=1)).replace(tzinfo=timezone.utc)
    params = {
        "timeMin": start_dt.isoformat().replace("+00:00", "Z"),
        "timeMax": end_dt.isoformat().replace("+00:00", "Z"),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 2500,
    }
    events: list[dict[str, Any]] = []
    page_token: str | None = None
    with httpx.Client(timeout=20) as client:
        while True:
            if page_token:
                params["pageToken"] = page_token
            response = client.get(
                GOOGLE_CALENDAR_EVENTS_URL.format(calendar_id=calendar),
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            events.extend(payload.get("items") or [])
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
    return [event for event in events if event.get("status") != "cancelled"]
