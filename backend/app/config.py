from pydantic import BaseModel
import os
import json

class Settings(BaseModel):
    app_name: str = "Timesheet Matcher"
    environment: str = "development"
    api_key: str = os.getenv("TEAMWORK_API_KEY", "")
    site: str = os.getenv("TEAMWORK_SITE", "")
    user_id: str = os.getenv("TEAMWORK_USER_ID", "")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "https://timesheet.ramos.ca/api/auth/google/callback")
    jwt_secret: str = os.getenv("JWT_SECRET", "3f51fe63408028b7e60da53c0366cf7881a565843342e6b8c99c8528c818e5a1")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours


def load_oauth_from_file(path: str = "/docker/timesheet/workspace/backend/google-oauth.json") -> dict | None:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


_settings_overrides = load_oauth_from_file()
if _settings_overrides:
    web = _settings_overrides.get("web", {})
    os.environ.setdefault("GOOGLE_CLIENT_ID", web.get("client_id", ""))
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", web.get("client_secret", ""))

settings = Settings()