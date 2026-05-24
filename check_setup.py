"""
Run this script to verify your .env is filled in correctly before starting the app.
  python check_setup.py
"""
import sys, os, json
from dotenv import load_dotenv

load_dotenv()

ok = True

def check(label, value, hint=""):
    global ok
    filled = bool(value and value.strip() and not value.startswith("your-") and value != "{}")
    mark = "✓" if filled else "✗"
    print(f"  {mark}  {label}")
    if not filled:
        ok = False
        if hint:
            print(f"       → {hint}")

print("\n── Checking .env ───────────────────────────────────────────")
check("GOOGLE_CLIENT_ID",          os.getenv("GOOGLE_CLIENT_ID",""),
      "Get from Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID")
check("GOOGLE_CLIENT_SECRET",      os.getenv("GOOGLE_CLIENT_SECRET",""),
      "Same place as Client ID")
check("GOOGLE_SHEETS_CREDENTIALS", os.getenv("GOOGLE_SHEETS_CREDENTIALS","{}"),
      "Paste the full service-account JSON (single line) from your downloaded key file")
check("SECRET_KEY",                os.getenv("SECRET_KEY",""),
      "Run: python -c \"import secrets; print(secrets.token_hex(32))\"")
check("BASE_URL",                  os.getenv("BASE_URL",""),
      "Use http://localhost:8000 for local dev")

# Validate the JSON credential if present
creds_raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "{}")
if creds_raw and creds_raw != "{}":
    try:
        creds = json.loads(creds_raw)
        required_keys = ["type","project_id","private_key","client_email"]
        missing = [k for k in required_keys if k not in creds]
        if missing:
            print(f"  ✗  GOOGLE_SHEETS_CREDENTIALS is valid JSON but missing keys: {missing}")
            ok = False
        else:
            svc_email = creds.get("client_email","")
            print(f"\n  Service account email: {svc_email}")
            print(f"  ↳ Make sure your 'Expense Logs' sheet is shared with this email (Editor access)")
    except json.JSONDecodeError as e:
        print(f"  ✗  GOOGLE_SHEETS_CREDENTIALS is not valid JSON: {e}")
        ok = False

print("────────────────────────────────────────────────────────────")
if ok:
    print("  All checks passed — run the app with:")
    print("  .\\venv\\Scripts\\uvicorn main:app --reload\n")
else:
    print("  Fix the items marked ✗ above, then re-run this script.\n")

sys.exit(0 if ok else 1)
