from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def decode_token(token: str) -> dict | None:
    """Decode a JWT token and return the payload, or None on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


def create_token(payload: dict) -> str:
    """Create a signed JWT token."""
    from datetime import datetime, timedelta, timezone
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload["exp"] = expires
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    """Return the user payload from the token, or None if no/invalid token."""
    if credentials is None:
        return None
    return decode_token(credentials.credentials)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Return the user payload, or raise 401 if no/invalid token."""
    user = get_optional_user(credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user