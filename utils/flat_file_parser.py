"""
Parser for the custom pipe-delimited expense history format:

    YYYY-MM-DD | INITIAL | CATEGORY | AMOUNT | DESCRIPTION | [NOTES]

Example:
    2026-02-18 | J | Transport | 90.73 | Petrol |
    2026-03-07 | E | Food      | 100.00 | Xiangxiang dinner |
    2026-03-10 | J | Transport | 144.47 | Insurance extension | Date corrected to 10 March

Rules:
  - Fields are separated by |
  - The NOTES field (6th) is optional
  - Lines with fewer than 5 fields (after strip) are silently skipped
  - The INITIAL is mapped to a full email via initial_map; unmapped initials
    fall back to "<lowercase-initial>@family" so records are never lost
"""
from datetime import datetime


def _parse_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")


def parse_flat_file(content: str, initial_map: dict[str, str]) -> list[dict]:
    """
    Parse a pipe-delimited history file.

    Args:
        content:     Raw text of the file.
        initial_map: Dict mapping person initials to email addresses.
                     e.g. {"J": "joel@gmail.com", "E": "elaine@gmail.com"}

    Returns:
        List of standardised expense dicts ready for bulk insert.
    """
    transactions = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split("|")]
        # Need at least: date, initial, category, amount, description
        if len(parts) < 5:
            continue

        date_str, initial, category, amount_str, description = parts[:5]
        notes = parts[5] if len(parts) > 5 else ""

        # Skip blank/header-like rows
        if not date_str or not amount_str:
            continue

        # Parse amount — skip non-numeric rows
        try:
            amount = abs(float(amount_str.replace(",", "")))
        except ValueError:
            continue
        if amount == 0:
            continue

        # Resolve person initial → email
        initial_upper = initial.upper()
        user_email = initial_map.get(
            initial_upper,
            f"{initial.lower()}@family",   # fallback — never drop a record
        )

        transactions.append({
            "date":            _parse_date(date_str),
            "amount":          str(round(amount, 2)),
            "description":     description,
            "category":        category,          # keep original category as-is
            "user_email":      user_email,
            "source":          "import",
            "raw_description": description,
            "notes":           notes,
        })

    return transactions


def summarise(transactions: list[dict]) -> dict:
    """Return a human-readable summary dict for the preview step."""
    from collections import defaultdict
    by_person: dict[str, dict] = defaultdict(lambda: {"count": 0, "total": 0.0})
    by_category: dict[str, float] = defaultdict(float)

    for tx in transactions:
        email = tx["user_email"]
        amt = float(tx["amount"])
        by_person[email]["count"] += 1
        by_person[email]["total"] += amt
        by_category[tx["category"]] += amt

    return {
        "total_rows":     len(transactions),
        "total_amount":   sum(float(t["amount"]) for t in transactions),
        "by_person":      dict(by_person),
        "top_categories": sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:8],
    }
