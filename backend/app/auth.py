import secrets
import httpx
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.config import settings
from app.deps import create_token, get_optional_user
from app.google_calendar import save_google_calendar_tokens

router = APIRouter(prefix="/api/auth", tags=["auth"])


def generate_state() -> str:
    return secrets.token_urlsafe(32)


@router.get("/google/login")
def google_login(state: str | None = Query(default=None)):
    if state is None:
        state = generate_state()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile https://www.googleapis.com/auth/calendar.readonly",
        "state": state,
        "access_type": "offline",
        "prompt": "consent select_account",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    token_data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post("https://oauth2.googleapis.com/token", data=token_data)
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to exchange code: {token_response.text}",
            )
        tokens = token_response.json()

    id_token_str = tokens.get("id_token")
    if not id_token_str:
        raise HTTPException(status_code=400, detail="No id_token in Google response")

    try:
        request_adapter = google_requests.Request()
        info = id_token.verify_oauth2_token(id_token_str, request_adapter, settings.google_client_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Token verification failed: {e}")

    user_info = {"sub": info.get("sub"), "email": info.get("email", ""), "name": info.get("name", ""), "picture": info.get("picture", "")}
    save_google_calendar_tokens(tokens, user_info)
    jwt_token = create_token(user_info)
    return RedirectResponse(url=f"/?token={jwt_token}", status_code=302)


@router.get("/status")
def auth_status(user: dict | None = Depends(get_optional_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"authenticated": True, "user": {"sub": user.get("sub"), "email": user.get("email"), "name": user.get("name"), "picture": user.get("picture")}}


@router.post("/logout")
def auth_logout():
    return {"status": "ok", "message": "Logged out"}
