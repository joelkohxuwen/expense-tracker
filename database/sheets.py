"""
Google Sheets data layer.

The spreadsheet named SPREADSHEET_NAME (default: "Expense Logs") acts as the
database. On first startup, ensure_sheets() creates the required tabs:

  users     — one row per registered account
  expenses  — every logged transaction
  categories — the category list shown in dropdowns

All async functions are thin wrappers; gspread itself is synchronous, but
marking them async lets callers use `await` consistently and makes it easy to
swap in a true async client later.
"""
import json
import uuid
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEETS_CREDENTIALS, SPREADSHEET_NAME

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column headers for each worksheet tab
_HEADERS = {
    "users": ["id", "email", "name", "picture", "role", "joined_date"],
    "expenses": [
        "id", "date", "amount", "description", "category",
        "user_email", "source", "raw_description", "notes", "created_at",
    ],
    "categories": ["name"],
}

_DEFAULT_CATEGORIES = [
    "Food & Dining", "Shopping", "Transportation", "Entertainment",
    "Health & Medical", "Travel", "Utilities", "Insurance",
    "Banking & Finance", "Home & Garden", "Personal Care",
    "Education", "Income", "Other",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client() -> gspread.Client:
    creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    return gspread.authorize(creds)


def _get_client_email() -> str:
    """Return the service account email for helpful error messages."""
    try:
        return json.loads(GOOGLE_SHEETS_CREDENTIALS).get("client_email", "")
    except Exception:
        return ""


def _get_spreadsheet() -> gspread.Spreadsheet:
    client = _get_client()
    try:
        return client.open(SPREADSHEET_NAME)
    except gspread.exceptions.SpreadsheetNotFound:
        svc_email = _get_client_email()
        raise RuntimeError(
            f"Spreadsheet '{SPREADSHEET_NAME}' is not accessible to the service account.\n"
            f"Please share it with: {svc_email}\n"
            f"  1. Open your '{SPREADSHEET_NAME}' Google Sheet\n"
            f"  2. Click Share → paste the email above → set role to Editor → Send"
        ) from None


def _rows_to_dicts(rows: list[list]) -> list[dict]:
    """Convert a 2-D grid (first row = headers) to a list of dicts."""
    if not rows or len(rows) < 2:
        return []
    headers = rows[0]
    result = []
    for row in rows[1:]:
        # Pad short rows so zip always has enough values
        padded = row + [""] * (len(headers) - len(row))
        result.append(dict(zip(headers, padded)))
    return result


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

async def ensure_sheets() -> None:
    """Create any missing worksheet tabs and seed default data."""
    try:
        ss = _get_spreadsheet()
        existing = {ws.title for ws in ss.worksheets()}

        for tab_name, headers in _HEADERS.items():
            if tab_name not in existing:
                ws = ss.add_worksheet(tab_name, rows=2000, cols=len(headers))
                ws.append_row(headers)

        # Seed categories only if the tab is empty
        cat_ws = ss.worksheet("categories")
        existing_cats = cat_ws.col_values(1)
        if len(existing_cats) <= 1:  # only header or completely empty
            cat_ws.append_rows([[c] for c in _DEFAULT_CATEGORIES])

    except Exception as exc:
        # Non-fatal on startup — will surface as errors during normal use
        print(f"[sheets] Warning: could not ensure tabs: {exc}")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def get_or_create_user(email: str, name: str, picture: str = "") -> dict:
    """
    Return the existing user row for this email, or create a new one.
    The very first user to sign in automatically becomes an admin.
    """
    ss = _get_spreadsheet()
    ws = ss.worksheet("users")
    all_rows = ws.get_all_values()
    users = _rows_to_dicts(all_rows)

    for user in users:
        if user.get("email") == email:
            return user

    role = "admin" if not users else "user"
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name,
        "picture": picture,
        "role": role,
        "joined_date": datetime.now().strftime("%Y-%m-%d"),
    }
    ws.append_row([new_user[h] for h in _HEADERS["users"]])
    return new_user


async def get_all_users() -> list[dict]:
    ss = _get_spreadsheet()
    ws = ss.worksheet("users")
    return _rows_to_dicts(ws.get_all_values())


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

async def get_expenses(user_email: str | None = None, limit: int = 500) -> list[dict]:
    """
    Return expenses sorted newest-first.
    Pass user_email=None to get all expenses (used for deduplication checks).
    """
    ss = _get_spreadsheet()
    ws = ss.worksheet("expenses")
    all_rows = ws.get_all_values()
    expenses = _rows_to_dicts(all_rows)

    if user_email:
        expenses = [e for e in expenses if e.get("user_email") == user_email]

    expenses.sort(key=lambda e: e.get("date", ""), reverse=True)
    return expenses[:limit]


async def add_expense(expense: dict) -> dict:
    """Insert a single expense row and return it with the generated id."""
    ss = _get_spreadsheet()
    ws = ss.worksheet("expenses")

    expense = {**expense}  # don't mutate caller's dict
    expense["id"] = str(uuid.uuid4())
    expense.setdefault("created_at", datetime.now().isoformat())
    expense.setdefault("source", "manual")
    expense.setdefault("raw_description", expense.get("description", ""))
    expense.setdefault("notes", "")

    ws.append_row([expense.get(h, "") for h in _HEADERS["expenses"]])
    return expense


async def add_expenses_bulk(expenses: list[dict]) -> list[dict]:
    """Insert multiple expense rows in a single API call (batch-efficient)."""
    if not expenses:
        return []

    ss = _get_spreadsheet()
    ws = ss.worksheet("expenses")

    now = datetime.now().isoformat()
    rows = []
    enriched = []
    for exp in expenses:
        exp = {**exp}
        exp["id"] = str(uuid.uuid4())
        exp.setdefault("created_at", now)
        exp.setdefault("source", "import")
        exp.setdefault("raw_description", exp.get("description", ""))
        exp.setdefault("notes", "")
        rows.append([exp.get(h, "") for h in _HEADERS["expenses"]])
        enriched.append(exp)

    ws.append_rows(rows)
    return enriched


async def delete_expense(expense_id: str) -> bool:
    """Delete an expense by id. Returns True if a row was deleted."""
    ss = _get_spreadsheet()
    ws = ss.worksheet("expenses")
    all_rows = ws.get_all_values()

    if not all_rows:
        return False

    try:
        id_col_idx = all_rows[0].index("id")
    except ValueError:
        return False

    for row_num, row in enumerate(all_rows[1:], start=2):
        if len(row) > id_col_idx and row[id_col_idx] == expense_id:
            ws.delete_rows(row_num)
            return True
    return False


async def update_expense(expense_id: str, updates: dict) -> bool:
    """Update specific fields on an expense row."""
    ss = _get_spreadsheet()
    ws = ss.worksheet("expenses")
    all_rows = ws.get_all_values()

    if not all_rows:
        return False

    headers = all_rows[0]
    try:
        id_col_idx = headers.index("id")
    except ValueError:
        return False

    for row_num, row in enumerate(all_rows[1:], start=2):
        if len(row) > id_col_idx and row[id_col_idx] == expense_id:
            padded = row + [""] * (len(headers) - len(row))
            for key, val in updates.items():
                if key in headers:
                    col_idx = headers.index(key)
                    padded[col_idx] = val
            ws.update(f"A{row_num}", [padded])
            return True
    return False


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

async def get_categories() -> list[str]:
    ss = _get_spreadsheet()
    ws = ss.worksheet("categories")
    values = ws.col_values(1)
    return [v.strip() for v in values[1:] if v.strip()]
