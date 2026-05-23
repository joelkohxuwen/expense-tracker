"""
Credit card statement CSV parser.

Supports Chase, Bank of America, Citi, Capital One, and a generic fallback.
The main entry point is parse_csv(text: str) -> list[dict].

Each returned transaction dict has:
  date             YYYY-MM-DD
  amount           positive float (expenses only — credits/refunds skipped)
  description      cleaned merchant name
  raw_description  original string from the CSV
  category         auto-categorized string
"""
import io
from datetime import datetime

import pandas as pd

from utils.categorizer import auto_categorize

_DATE_FORMATS = [
    "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y",
    "%m/%d/%y", "%d-%m-%Y", "%Y/%m/%d",
    "%d %b %Y", "%b %d, %Y", "%m-%d-%Y",
]


def _parse_date(raw: str) -> str:
    raw = (raw or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")


def _parse_amount(raw: str) -> float:
    cleaned = str(raw or "").replace(",", "").replace("$", "").replace(" ", "").strip()
    try:
        return abs(float(cleaned))
    except ValueError:
        return 0.0


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from column names and return a copy."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _detect_format(df: pd.DataFrame) -> str:
    cols = {c.lower() for c in df.columns}
    if "transaction date" in cols and "post date" in cols and "type" in cols:
        return "chase"
    if "posted date" in cols and "reference number" in cols and "payee" in cols:
        return "bank_of_america"
    if "status" in cols and "debit" in cols and "credit" in cols and "description" in cols:
        return "citi"
    if any("card no" in c for c in cols):
        return "capital_one"
    return "generic"


def _to_standard(rows: list[dict]) -> list[dict]:
    """Add category and drop zero-amount rows."""
    out = []
    for row in rows:
        if row.get("amount", 0) <= 0:
            continue
        row["category"] = auto_categorize(row["description"])
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Per-bank parsers
# ---------------------------------------------------------------------------

def _parse_chase(df: pd.DataFrame) -> list[dict]:
    df = _norm_cols(df)
    rows = []
    for _, row in df.iterrows():
        # Chase: expenses are negative
        raw_amount = str(row.get("Amount", "0"))
        amount = float(raw_amount.replace(",", "").replace("$", "").strip() or "0")
        if amount >= 0:
            continue
        desc = str(row.get("Description", "")).strip()
        rows.append({
            "date": _parse_date(str(row.get("Transaction Date", ""))),
            "description": desc,
            "raw_description": desc,
            "amount": abs(amount),
        })
    return _to_standard(rows)


def _parse_boa(df: pd.DataFrame) -> list[dict]:
    df = _norm_cols(df)
    rows = []
    for _, row in df.iterrows():
        amount = _parse_amount(str(row.get("Amount", "")))
        desc = str(row.get("Payee", "")).strip()
        rows.append({
            "date": _parse_date(str(row.get("Posted Date", ""))),
            "description": desc,
            "raw_description": desc,
            "amount": amount,
        })
    return _to_standard(rows)


def _parse_citi(df: pd.DataFrame) -> list[dict]:
    df = _norm_cols(df)
    rows = []
    for _, row in df.iterrows():
        debit = _parse_amount(str(row.get("Debit", "")))
        if debit <= 0:
            continue
        desc = str(row.get("Description", "")).strip()
        rows.append({
            "date": _parse_date(str(row.get("Date", ""))),
            "description": desc,
            "raw_description": desc,
            "amount": debit,
        })
    return _to_standard(rows)


def _parse_capital_one(df: pd.DataFrame) -> list[dict]:
    df = _norm_cols(df)
    rows = []
    for _, row in df.iterrows():
        debit = _parse_amount(str(row.get("Debit", "")))
        if debit <= 0:
            continue
        desc = str(row.get("Description", "")).strip()
        rows.append({
            "date": _parse_date(str(row.get("Transaction Date", ""))),
            "description": desc,
            "raw_description": desc,
            "amount": debit,
        })
    return _to_standard(rows)


def _parse_generic(df: pd.DataFrame) -> list[dict]:
    """
    Flexible fallback: find date/description/amount columns by common names.
    Works for DBS, OCBC, UOB, and most other banks that export simple CSV.
    """
    df = _norm_cols(df)
    lower_cols = {c.lower(): c for c in df.columns}

    date_col = next(
        (lower_cols[k] for k in lower_cols if "date" in k), None
    )
    desc_col = next(
        (lower_cols[k] for k in lower_cols
         if any(t in k for t in ["description", "payee", "memo", "merchant", "narration", "particulars", "reference"])),
        None,
    )
    amount_col = next(
        (lower_cols[k] for k in lower_cols if k in {"debit", "amount", "withdrawal", "charged amount"}),
        None,
    )

    if not (date_col and desc_col and amount_col):
        return []

    rows = []
    for _, row in df.iterrows():
        amount = _parse_amount(str(row.get(amount_col, "")))
        if amount <= 0:
            continue
        desc = str(row.get(desc_col, "")).strip()
        rows.append({
            "date": _parse_date(str(row.get(date_col, ""))),
            "description": desc,
            "raw_description": desc,
            "amount": amount,
        })
    return _to_standard(rows)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_PARSERS = {
    "chase": _parse_chase,
    "bank_of_america": _parse_boa,
    "citi": _parse_citi,
    "capital_one": _parse_capital_one,
    "generic": _parse_generic,
}


def parse_csv(content: str) -> list[dict]:
    """
    Parse a credit card statement CSV string.
    Returns a list of standardised transaction dicts, or [] on failure.
    """
    try:
        df = pd.read_csv(io.StringIO(content), dtype=str, skip_blank_lines=True)
        df = df.dropna(how="all")
        if df.empty:
            return []
        fmt = _detect_format(df)
        return _PARSERS[fmt](df)
    except Exception as exc:
        print(f"[csv_parser] Parse error: {exc}")
        return []
