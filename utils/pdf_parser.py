"""
PDF statement parser for UOB consolidated and Citi individual statements.

Tested with:
  - Citi PremierMiles individual PDF (pdfplumber quirk: date merged with month, e.g. "09MAR")
  - UOB consolidated multi-card PDF  (card number merged with holder name, e.g. "4006-XXXXJOEL KOH")

Entry point:
    parse_pdf(pdf_bytes, cardholder_map, default_email) -> list[dict]

Each returned dict matches the csv_parser schema:
    date             YYYY-MM-DD
    amount           positive float  (credits / payments are skipped)
    description      cleaned merchant name
    raw_description  original line text
    category         auto-categorized string
    user_email       resolved from cardholder_map or default_email
    source           "import"
    notes            ""
"""
import io
import re
from collections import Counter
from datetime import datetime

import pdfplumber

from utils.categorizer import auto_categorize

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MONTHS = "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC"

_MON_TO_INT: dict[str, int] = {
    "JAN": 1, "FEB": 2, "MAR": 3,  "APR": 4,  "MAY": 5,  "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9,  "OCT": 10, "NOV": 11, "DEC": 12,
}


def _to_date(day: int | str, month_str: str, year: int) -> str:
    """Return YYYY-MM-DD for day / month-abbreviation / year."""
    m = _MON_TO_INT.get(month_str.upper(), 1)
    try:
        return datetime(year, m, int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return datetime(year, m, 1).strftime("%Y-%m-%d")


def _detect_year(text: str) -> int:
    """Return the most-common 20xx year found in the PDF text."""
    years = re.findall(r'\b(20\d{2})\b', text)
    if years:
        return int(Counter(years).most_common(1)[0][0])
    return datetime.now().year


# ---------------------------------------------------------------------------
# Citi individual statement parser
#
# pdfplumber quirk: the day and the month abbreviation are merged without a
# space, so "09 MAR" becomes "09MAR" in the extracted text.
#
# Transaction line structure (after quirk):
#     09MAR  Nike Singapore  935.40
#     09MAR  SomeMerchant    (171.02)   ← credit, skip
# ---------------------------------------------------------------------------

_CITI_TX = re.compile(
    r'^(\d{2})(' + _MONTHS + r')\s+'             # DD+MMM (merged)
    r'(.+?)\s+'                                   # description
    r'(\([\d,]+\.\d{2}\)|[\d,]+\.\d{2})'         # (123.45) or 123.45
    r'\s*$',
    re.IGNORECASE,
)

_CITI_SKIP = re.compile(
    r'^(PREVIOUS|PAYMENT|NEW BALANCE|MINIMUM|CREDIT LIMIT|'
    r'DATE|TRANSACTION DATE|STATEMENT DATE|BALANCE B/F|'
    r'BROUGHT FORWARD|CARRIED FORWARD|SUB-TOTAL|TOTAL|'
    r'FINANCE CHARGE|LATE CHARGE)',
    re.IGNORECASE,
)


def _parse_citi_pdf(text: str, year: int, default_email: str) -> list[dict]:
    rows: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _CITI_SKIP.match(line):
            continue
        m = _CITI_TX.match(line)
        if not m:
            continue
        day, mon, desc, amt_raw = m.group(1), m.group(2), m.group(3).strip(), m.group(4)

        # Parenthesised amount = credit / refund — skip
        if amt_raw.startswith("("):
            continue

        try:
            amount = float(amt_raw.replace(",", ""))
        except ValueError:
            continue
        if amount <= 0:
            continue

        rows.append({
            "date":            _to_date(day, mon, year),
            "description":     desc,
            "raw_description": desc,
            "amount":          amount,
            "category":        auto_categorize(desc),
            "user_email":      default_email,
            "source":          "import",
            "notes":           "",
        })
    return rows


# ---------------------------------------------------------------------------
# UOB consolidated statement parser
#
# pdfplumber quirk: card number runs directly into the cardholder name:
#     "4006-8220-1287-3116JOEL KOH"
#
# Transaction line structure:
#     04 APR  03 APR  Nike Riverside Point Singapore  935.40
#     04 APR  03 APR  Income credit                   1,200.00CR   ← credit, skip
# ---------------------------------------------------------------------------

_UOB_CARD_HDR = re.compile(
    r'^(\d{4}-\d{4}-\d{4}-\d{4})'    # 16-digit card number with dashes
    r'([A-Z][A-Z ,.\'-]+?)'            # cardholder name — all-caps with spaces
    r'(?:\s+\(continued\))?\s*$',
)

_UOB_TX = re.compile(
    r'^(\d{1,2})\s+(' + _MONTHS + r')\s+'   # posting date
    r'(\d{1,2})\s+(' + _MONTHS + r')\s+'    # transaction date
    r'(.+?)\s+'                               # description
    r'([\d,]+\.\d{2}(?:CR)?)\s*$',           # amount (CR suffix = credit)
    re.IGNORECASE,
)

_UOB_SKIP = re.compile(
    r'^(SUB[ -]?TOTAL|SUBTOTAL|TOTAL DUE|TOTAL OUTSTANDING|'
    r'PAYMENT|PREVIOUS STATEMENT|PREVIOUS BALANCE|NEW BALANCE|'
    r'CREDIT LIMIT|MINIMUM SUM|MINIMUM PAYMENT|'
    r'POSTING DATE|TRANSACTION DATE|DATE\s+DATE|STATEMENT OF|'
    r'BROUGHT FORWARD|BALANCE BROUGHT)',
    re.IGNORECASE,
)


def _match_cardholder(name: str, cardholder_map: dict[str, str]) -> str | None:
    """
    Case-insensitive lookup in cardholder_map.
    Tries exact match first, then substring (for names that run together in PDF).
    Returns the mapped email or None.
    """
    name_up = name.upper().strip()
    # 1. Exact
    for k, v in cardholder_map.items():
        if k.upper().strip() == name_up:
            return v
    # 2. Map key is contained in the detected name (handles trailing garbage)
    for k, v in cardholder_map.items():
        if k.upper().strip() and k.upper().strip() in name_up:
            return v
    return None


def _parse_uob_pdf(
    text: str, year: int, cardholder_map: dict[str, str], default_email: str
) -> list[dict]:
    current_email = default_email
    rows: list[dict] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Card section header → update current email
        hdr = _UOB_CARD_HDR.match(line)
        if hdr:
            holder_name = hdr.group(2).strip()
            mapped = _match_cardholder(holder_name, cardholder_map)
            current_email = mapped if mapped is not None else default_email
            continue

        if _UOB_SKIP.match(line):
            continue

        m = _UOB_TX.match(line)
        if not m:
            continue

        post_day, post_mon = m.group(1), m.group(2)
        desc    = m.group(5).strip()
        amt_raw = m.group(6)

        # CR suffix = credit / payment — skip
        if amt_raw.upper().endswith("CR"):
            continue

        try:
            amount = float(amt_raw.replace(",", ""))
        except ValueError:
            continue
        if amount <= 0:
            continue

        rows.append({
            "date":            _to_date(post_day, post_mon, year),
            "description":     desc,
            "raw_description": desc,
            "amount":          amount,
            "category":        auto_categorize(desc),
            "user_email":      current_email,
            "source":          "import",
            "notes":           "",
        })
    return rows


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_pdf(
    pdf_bytes: bytes,
    cardholder_map: dict[str, str],
    default_email: str,
) -> list[dict]:
    """
    Parse a UOB consolidated or Citi individual PDF statement.

    Args:
        pdf_bytes:       Raw PDF file bytes.
        cardholder_map:  Mapping of cardholder name (as it appears in the PDF,
                         all-caps) to user email address.
                         E.g. {"JOEL KOH": "joel@gmail.com", "ELAINE SIM": "elaine@gmail.com"}
                         For Citi statements (single cardholder) this can be empty — all
                         transactions will use default_email.
        default_email:   Fallback email for any cardholder not found in the map.

    Returns:
        List of transaction dicts compatible with csv_parser.parse_csv() output.
        Returns [] on parse failure.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
        full_text = "\n".join(pages_text)
    except Exception as exc:
        print(f"[pdf_parser] Failed to open PDF: {exc}")
        return []

    if not full_text.strip():
        print("[pdf_parser] No text extracted from PDF")
        return []

    year = _detect_year(full_text)
    text_upper = full_text.upper()

    # Detect bank by document keywords
    is_citi = (
        "CITIBANK" in text_upper
        or "CITI PREMIER" in text_upper
        or "CITI REWARDS" in text_upper
        or "CITI CASH BACK" in text_upper
        or "CITIBANK SINGAPORE" in text_upper
    )
    is_uob = (
        "UNITED OVERSEAS BANK" in text_upper
        or "UOB CARD" in text_upper
        or "UOB VISA" in text_upper
        or "UOB MASTERCARD" in text_upper
        or "UOB ONE CARD" in text_upper
        or "UOB PRIVILEGE" in text_upper
    )

    if is_citi:
        return _parse_citi_pdf(full_text, year, default_email)
    if is_uob:
        return _parse_uob_pdf(full_text, year, cardholder_map, default_email)

    # Ambiguous — try UOB first (more distinctive line format), fall back to Citi
    uob_results = _parse_uob_pdf(full_text, year, cardholder_map, default_email)
    if uob_results:
        return uob_results
    return _parse_citi_pdf(full_text, year, default_email)
