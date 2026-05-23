# Family Expense Tracker

A shared expense-tracking web app for couples and families, built with **ReactPy** (Python-based React) + **FastAPI**, using **Google Sheets** as the database and **Google OAuth** for login.

## Features

- **Google Sign-In** — family members log in with their Google accounts; the first sign-in automatically becomes an admin
- **Manual expense entry** — date, amount, description, category, notes
- **Credit card statement import** — upload a CSV from Chase, Bank of America, Citi, Capital One, DBS, OCBC, or any bank that exports generic CSV
- **Deduplication** — the importer flags transactions that look like duplicates of manually-entered expenses; you choose to skip, import anyway, or replace the manual entry
- **Auto-categorisation** — descriptions are matched against keyword rules to suggest a category
- **Shared view** — all family members see the same sheet; the dashboard shows who spent what
- **Responsive UI** — Bootstrap 5, works on mobile

---

## Tech stack

| Layer | Library |
|---|---|
| UI components | [ReactPy](https://reactpy.dev) |
| Web framework | FastAPI + Uvicorn |
| Auth | Authlib (Google OAuth 2.0) |
| Database | Google Sheets via gspread |
| CSV parsing | pandas |
| Session tokens | python-jose (JWT, HS256) |

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/joelkohxuwen/expense-tracker.git
cd expense-tracker
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a new project (or reuse one).
2. Enable **Google Sheets API** and **Google Drive API** under *APIs & Services → Library*.
3. Enable the **Google OAuth 2.0** API (it's usually already on).

### 3. OAuth 2.0 credentials (for user login)

1. *APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID*
2. Application type: **Web application**
3. Authorised redirect URIs:
   - `http://localhost:8000/auth/callback` (local dev)
   - `https://your-app.onrender.com/auth/callback` (production)
4. Copy the **Client ID** and **Client Secret**.

### 4. Service account (for Google Sheets access)

1. *APIs & Services → Credentials → Create Credentials → Service Account*
2. Give it any name (e.g. `expense-tracker-sheets`)
3. After creating, click the service account → *Keys → Add Key → JSON*
4. Download the JSON key file — **keep it secret, never commit it**
5. Open your **Expense Logs** spreadsheet in Google Sheets
6. Click *Share* and share it with the service account email  
   (looks like `expense-tracker-sheets@your-project.iam.gserviceaccount.com`)  
   — grant **Editor** access

### 5. Environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_SHEETS_CREDENTIALS=<paste the entire service-account JSON on one line>
SPREADSHEET_NAME=Expense Logs
SECRET_KEY=<long random string — run: python -c "import secrets; print(secrets.token_hex(32))">
BASE_URL=http://localhost:8000
DEBUG=true
```

> **Tip for the JSON credential:** open the downloaded JSON file, select all, copy, and paste it as a single line. The `\n` inside the private key must stay as literal `\n` (most terminals handle this automatically when you paste).

### 6. Run locally

```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) and sign in with your Google account.

---

## Deploying to Render

1. Push the repo to GitHub (already done if you cloned from there).
2. Go to [render.com](https://render.com) → *New → Web Service* → connect the repo.
3. Render will detect `render.yaml` and pre-fill most settings.
4. Add the secret environment variables under *Environment*:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_SHEETS_CREDENTIALS`
   - `BASE_URL` — set to `https://your-app-name.onrender.com`
5. Add the Render callback URL to your Google OAuth redirect URIs:  
   `https://your-app-name.onrender.com/auth/callback`
6. Click *Deploy*.

---

## Adding family members

New users who sign in with their Google account are automatically added to the `users` tab of the Google Sheet with the `user` role. No invite flow is needed — just share the app URL. If you want to restrict access, add an `ALLOWED_EMAILS` env var (comma-separated list) and update `get_or_create_user` in `database/sheets.py` to check it.

---

## Credit card CSV import

Most banks let you export transactions as CSV from their web portal:

| Bank | Where to find it |
|---|---|
| Chase | Account Activity → Download → CSV |
| Bank of America | Account Details → Download Transactions |
| Citi | Account Details → Download |
| Capital One | Transactions → Download |
| DBS/POSB | Card Transactions → Download → CSV |
| OCBC | Account Statement → Export → CSV |
| UOB | Statements → Download |

The parser auto-detects the format. Any unrecognised CSV is tried as a "generic" format looking for `date`, `description`/`payee`/`memo`, and `debit`/`amount` columns.

---

## Project structure

```
expense-tracker/
├── main.py                 # FastAPI entry point + OAuth routes + CSV upload
├── config.py               # Environment variable loading
├── auth/
│   ├── oauth.py            # Authlib Google OAuth registration
│   └── session.py          # JWT creation / verification
├── database/
│   └── sheets.py           # Google Sheets CRUD (users, expenses, categories)
├── utils/
│   ├── categorizer.py      # Keyword → category mapping
│   ├── csv_parser.py       # Multi-bank CC statement parser
│   └── deduplicator.py     # Duplicate detection (amount + date + description)
└── components/             # ReactPy UI components
    ├── app.py              # Root component — auth gate + routing
    ├── login.py            # Login page (shown when not authenticated)
    ├── navbar.py           # Top navigation bar
    ├── dashboard.py        # Summary stats + recent transactions
    ├── expenses.py         # Full expense list with filters + edit/delete
    ├── expense_form.py     # Reusable add/edit form
    └── import_page.py      # CSV upload + deduplication review
```

### ReactPy quick reference

| Concept | ReactPy equivalent |
|---|---|
| Component | `@component` decorated function |
| State | `value, set_value = hooks.use_state(initial)` |
| Side effects | `@hooks.use_effect(dependencies=[...])` |
| Event handler | `"onClick": lambda event: ...` |
| Controlled input | `"value": state_var, "onChange": lambda e: set_var(e["target"]["value"])` |
| Read ASGI scope | `connection = use_connection(); scope = connection.scope` |
