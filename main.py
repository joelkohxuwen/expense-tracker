"""
Family Expense Tracker — FastAPI + ReactPy entry point.

FastAPI handles:
  /auth/login     — redirect to Google OAuth
  /auth/callback  — exchange OAuth code for tokens, set session cookie
  /auth/logout    — clear session cookie
  /api/import-csv — receive uploaded CSV, parse + dedup, redirect to review

ReactPy handles everything else:
  configure(app, App) mounts the App component on / and serves the
  WebSocket endpoint that drives the reactive UI.
"""
import uuid
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from reactpy.backend.fastapi import configure

from auth.oauth import oauth
from auth.session import create_session_token, get_user_from_request
from components.app import App
from components.import_page import set_import_sessions_ref
from config import BASE_URL, DEBUG, SECRET_KEY
from database.sheets import ensure_sheets, get_expenses, get_or_create_user
from utils.csv_parser import parse_csv
from utils.deduplicator import find_duplicates

# ---------------------------------------------------------------------------
# Shared in-memory store for pending CSV import sessions.
# Keyed by UUID; each value holds the parsed transactions and the owner's email.
# A family tracker won't have thousands of concurrent imports, so a plain
# dict is sufficient — no Redis needed.
# ---------------------------------------------------------------------------
import_sessions: dict = {}

# Give the ImportPage component a reference to this dict so it can read
# pending data without a round-trip HTTP call (everything runs server-side).
set_import_sessions_ref(import_sessions)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Family Expense Tracker")

# SessionMiddleware stores OAuth state (CSRF nonce) in a signed cookie.
# https_only=False in debug so http://localhost works without TLS.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=not DEBUG,
    same_site="lax",
)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event() -> None:
    """Ensure the required Google Sheets tabs exist before taking traffic."""
    await ensure_sheets()


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/auth/login")
async def login(request: Request):
    """Redirect the browser to Google's OAuth 2.0 authorization page."""
    redirect_uri = f"{BASE_URL}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """
    Handle the OAuth callback from Google.
    Exchange the authorization code for tokens, fetch user info,
    upsert the user in Google Sheets, and set a signed JWT session cookie.
    """
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            raise ValueError("No userinfo in token response")

        user = await get_or_create_user(
            email=user_info["email"],
            name=user_info.get("name", ""),
            picture=user_info.get("picture", ""),
        )

        session_token = create_session_token(user)

        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,         # not readable by JavaScript
            secure=not DEBUG,      # require HTTPS in production
            samesite="lax",
            max_age=7 * 24 * 3600,
        )
        return response

    except Exception as exc:
        # Surface the error on the login page without leaking internals
        short = str(exc)[:80].replace("&", "%26")
        return RedirectResponse(url=f"/?error={short}", status_code=302)


@app.get("/auth/logout")
async def logout():
    """Clear the session cookie and redirect to the login screen."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_token")
    return response


# ---------------------------------------------------------------------------
# CSV import API
# ---------------------------------------------------------------------------

@app.post("/api/import-csv")
async def import_csv_endpoint(request: Request, file: UploadFile = File(...)):
    """
    Receive a credit card statement CSV, parse it, run duplicate detection,
    and store the result in import_sessions. Then redirect back to the
    ReactPy app's import review page.

    The ReactPy ImportPage component reads import_sessions[import_id] directly
    (server-side), so no separate GET API is needed to retrieve the data.
    """
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    raw_bytes = await file.read()
    text = raw_bytes.decode("utf-8", errors="replace")

    transactions = parse_csv(text)
    if not transactions:
        return RedirectResponse(url="/?page=import&error=parse_failed", status_code=302)

    # Run deduplication against all existing expenses (all users share the sheet)
    existing = await get_expenses(user_email=None)
    duplicates = find_duplicates(transactions, existing)

    # Build a lookup map: (description, amount) → duplicate info
    dup_map: dict[str, dict] = {}
    for dup in duplicates:
        key = (dup["new"]["description"], str(dup["new"]["amount"]))
        dup_map[key] = dup

    # Annotate each transaction with its duplicate info (or None)
    for tx in transactions:
        key = (tx["description"], str(tx["amount"]))
        if key in dup_map:
            tx["potential_duplicate"] = dup_map[key]["existing"]
            tx["duplicate_confidence"] = dup_map[key]["confidence"]
        else:
            tx["potential_duplicate"] = None
            tx["duplicate_confidence"] = 0.0

    import_id = str(uuid.uuid4())
    import_sessions[import_id] = {
        "transactions": transactions,
        "user_email": user["email"],
        "filename": file.filename or "uploaded.csv",
    }

    return RedirectResponse(
        url=f"/?page=import&import_id={import_id}",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# Mount ReactPy — must come last so FastAPI routes above take priority
# ---------------------------------------------------------------------------
configure(app, App)
