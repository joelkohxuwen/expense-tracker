"""
Duplicate detection between imported CC transactions and manual entries.

When a user uploads a credit card statement we check every transaction against
existing manually-logged expenses. Two expenses are considered potential
duplicates when they share a very similar amount AND close dates AND similar
descriptions.

find_duplicates() returns a list of match dicts for the caller to present as
a review step before confirming the import.
"""
from datetime import datetime
from difflib import SequenceMatcher


def _parse_date(raw: str) -> datetime | None:
    try:
        return datetime.strptime((raw or "").strip(), "%Y-%m-%d")
    except ValueError:
        return None


def _seq_similarity(a: str, b: str) -> float:
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _word_overlap(a: str, b: str) -> float:
    """Jaccard similarity on word sets."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _confidence(new_tx: dict, existing: dict) -> float:
    """
    Compute a 0–1 match confidence between a new transaction and an existing
    expense. Returns 0.0 immediately if the amounts differ by more than 2%.
    """
    try:
        a1 = float(new_tx.get("amount", 0))
        a2 = float(existing.get("amount", 0))
    except (TypeError, ValueError):
        return 0.0

    if max(a1, a2) == 0:
        return 0.0

    amount_ratio = min(a1, a2) / max(a1, a2)
    if amount_ratio < 0.98:
        return 0.0  # amounts too different — not a duplicate

    d1 = _parse_date(new_tx.get("date", ""))
    d2 = _parse_date(existing.get("date", ""))
    if d1 and d2:
        diff_days = abs((d1 - d2).days)
        if diff_days > 5:
            return 0.0  # more than 5 days apart — not a duplicate
        date_score = 1.0 - (diff_days / 5.0)
    else:
        date_score = 0.5  # can't compare dates

    desc_new = new_tx.get("description", "") or new_tx.get("raw_description", "")
    desc_old = existing.get("description", "") or existing.get("raw_description", "")
    desc_score = max(
        _seq_similarity(desc_new, desc_old),
        _word_overlap(desc_new, desc_old),
    )

    return round(amount_ratio * 0.45 + date_score * 0.30 + desc_score * 0.25, 3)


def find_duplicates(
    new_transactions: list[dict],
    existing_expenses: list[dict],
    threshold: float = 0.70,
) -> list[dict]:
    """
    For each new transaction find the best-matching manual expense (if any).

    Only matches against source='manual' entries — previously imported CC
    transactions are excluded to avoid false positives.

    Returns a list of dicts:
      {
        "new":        <transaction dict>,
        "existing":   <expense dict>,
        "confidence": float 0–1,
      }
    """
    manual = [e for e in existing_expenses if e.get("source", "manual") == "manual"]

    results = []
    for tx in new_transactions:
        best_exp, best_conf = None, 0.0
        for exp in manual:
            conf = _confidence(tx, exp)
            if conf > best_conf:
                best_conf, best_exp = conf, exp

        if best_exp is not None and best_conf >= threshold:
            results.append({
                "new": tx,
                "existing": best_exp,
                "confidence": best_conf,
            })

    return results
