"""
JWT-based session management.

Sessions are stored in an HTTP-only cookie called 'session_token'.
Two entry points:
  - get_user_from_request()  — for FastAPI route handlers
  - get_user_from_scope()    — for ReactPy components (reads the ASGI WebSocket scope)
"""
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

from fastapi import Request
from jose import JWTError, jwt

from config import SECRET_KEY

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7


def create_session_token(user: dict) -> str:
    """Encode user info into a signed JWT that expires in 7 days."""
    payload = {
        "sub": user["email"],
        "name": user.get("name", ""),
        "picture": user.get("picture", ""),
        "role": user.get("role", "user"),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_session_token(token: str) -> dict | None:
    """Decode and verify a JWT session token. Returns None if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "email": payload["sub"],
            "name": payload.get("name", ""),
            "picture": payload.get("picture", ""),
            "role": payload.get("role", "user"),
        }
    except JWTError:
        return None


def get_user_from_request(request: Request) -> dict | None:
    """Extract the current user from a FastAPI request's session cookie."""
    token = request.cookies.get("session_token")
    return decode_session_token(token) if token else None


def get_user_from_scope(scope: dict) -> dict | None:
    """
    Extract the current user from an ASGI WebSocket scope.

    ReactPy components run on the server connected to the browser over a
    WebSocket. The initial HTTP upgrade request carries the cookies, which
    are accessible via the ASGI scope's 'headers' key.
    """
    headers = dict(scope.get("headers", []))
    cookie_bytes = headers.get(b"cookie", b"")
    if not cookie_bytes:
        return None

    cookie = SimpleCookie()
    cookie.load(cookie_bytes.decode("latin-1"))

    morsel = cookie.get("session_token")
    if not morsel:
        return None

    return decode_session_token(morsel.value)
