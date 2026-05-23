import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# Service account JSON for Google Sheets access (paste the full JSON as a single-line string)
GOOGLE_SHEETS_CREDENTIALS = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "{}")

SPREADSHEET_NAME = os.environ.get("SPREADSHEET_NAME", "Expense Logs")

# Generate a strong random key for production: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deploying")

# Full public URL of the app (no trailing slash) — must match the OAuth redirect URI
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
