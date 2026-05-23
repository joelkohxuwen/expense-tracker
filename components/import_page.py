"""
Credit card statement import page.

Two-step flow:
  Step 1 — Upload:   User selects a CSV file. The form POSTs to the FastAPI
                     endpoint /api/import-csv which parses the file, runs
                     deduplication, and redirects back to this page with
                     ?page=import&import_id=<uuid>.

  Step 2 — Review:   When import_id is present in the URL, this component
                     fetches the pre-parsed transactions from the in-memory
                     import_sessions store and shows a review table.
                     The user toggles which transactions to import and can
                     choose "Replace" for confirmed duplicates (deletes the
                     manual entry and imports the CC version instead).

ReactPy pattern: conditional rendering based on props.
The import_id prop (derived from URL query params in app.py) determines
which step is shown. Step 2 uses use_effect to load the pending transactions
from the server-side store on first mount.
"""
import asyncio

from reactpy import component, html, hooks

from database.sheets import add_expenses_bulk, delete_expense


# The import_sessions dict is defined in main.py and injected here at import time.
# We access it via a module-level reference set by main.py on startup.
_import_sessions: dict = {}


def set_import_sessions_ref(sessions: dict) -> None:
    """Called from main.py after creating the import_sessions dict."""
    global _import_sessions
    _import_sessions = sessions


@component
def ImportPage(user: dict, import_id: str = "", on_navigate=None):
    """
    Handles both the upload step and the review step.

    When import_id is empty: show the upload form.
    When import_id is set:   load pending transactions and show review table.
    """
    if import_id:
        return _ReviewStep(user=user, import_id=import_id, on_navigate=on_navigate)
    return _UploadStep()


@component
def _UploadStep():
    """Upload form — a regular HTML multipart form that POSTs to FastAPI."""
    return html.div(
        html.div(
            {"class": "row justify-content-center"},
            html.div(
                {"class": "col-lg-7"},
                html.h3(
                    {"class": "fw-bold mb-1"},
                    html.i({"class": "bi bi-upload me-2"}),
                    "Import Credit Card Statement",
                ),
                html.p(
                    {"class": "text-muted mb-4"},
                    "Upload a CSV export from your bank. Supported formats: Chase, "
                    "Bank of America, Citi, Capital One, and most generic CSV exports "
                    "(DBS, OCBC, UOB, etc.).",
                ),
                html.div(
                    {"class": "card border-0 shadow-sm"},
                    html.div(
                        {"class": "card-body p-4"},
                        # Traditional multipart form — navigates to FastAPI endpoint
                        html.form(
                            {
                                "action": "/api/import-csv",
                                "method": "post",
                                "enctype": "multipart/form-data",
                            },
                            html.div(
                                {"class": "mb-3"},
                                html.label(
                                    {"class": "form-label fw-semibold", "for": "csv-file"},
                                    "Select CSV file",
                                ),
                                html.input({
                                    "id": "csv-file",
                                    "type": "file",
                                    "name": "file",
                                    "accept": ".csv,text/csv",
                                    "class": "form-control form-control-lg",
                                    "required": True,
                                }),
                                html.div(
                                    {"class": "form-text"},
                                    "Export instructions: ",
                                    html.strong("Chase"), " — Account Activity → Download → CSV  |  ",
                                    html.strong("DBS/POSB"), " — Card Transactions → Download  |  ",
                                    html.strong("OCBC"), " — Account Statement → Export CSV",
                                ),
                            ),
                            html.button(
                                {"type": "submit", "class": "btn btn-primary btn-lg w-100"},
                                html.i({"class": "bi bi-cloud-upload me-2"}),
                                "Parse Statement",
                            ),
                        ),
                    ),
                ),
                html.div(
                    {"class": "alert alert-info mt-4"},
                    html.i({"class": "bi bi-info-circle me-2"}),
                    html.strong("How deduplication works: "),
                    "After parsing, we compare each transaction against your manually-logged "
                    "expenses. Transactions that share the same amount, a nearby date, and a "
                    "similar description are flagged as potential duplicates for your review.",
                ),
            ),
        ),
    )


@component
def _ReviewStep(user: dict, import_id: str, on_navigate):
    """
    Review table: shown after the CSV has been parsed server-side.
    Loads the pending transactions from the shared import_sessions dict.
    """
    transactions, set_transactions = hooks.use_state(None)
    # Map of tx index → decision: "import" | "skip" | "replace"
    decisions, set_decisions = hooks.use_state({})
    saving, set_saving = hooks.use_state(False)
    done, set_done = hooks.use_state(False)
    error, set_error = hooks.use_state("")

    @hooks.use_effect(dependencies=[import_id])
    async def load_pending():
        data = _import_sessions.get(import_id)
        if data and data.get("user_email") == user["email"]:
            txs = data.get("transactions", [])
            # Default decision: skip duplicates, import non-duplicates
            default_decisions = {
                i: ("skip" if tx.get("potential_duplicate") else "import")
                for i, tx in enumerate(txs)
            }
            set_transactions(txs)
            set_decisions(default_decisions)

    def set_decision(idx: int, decision: str):
        set_decisions({**decisions, idx: decision})

    async def confirm_import(_event):
        if not transactions:
            return
        set_saving(True)
        set_error("")

        to_import = []
        to_replace_ids = []

        for i, tx in enumerate(transactions):
            decision = decisions.get(i, "skip")
            if decision in ("import", "replace"):
                to_import.append({
                    "date": tx["date"],
                    "amount": str(tx["amount"]),
                    "description": tx["description"],
                    "category": tx["category"],
                    "user_email": user["email"],
                    "source": "import",
                    "raw_description": tx.get("raw_description", tx["description"]),
                    "notes": "",
                })
                if decision == "replace" and tx.get("potential_duplicate"):
                    to_replace_ids.append(tx["potential_duplicate"]["id"])

        try:
            # Delete replaced manual entries first
            for eid in to_replace_ids:
                await delete_expense(eid)
            # Bulk insert the new transactions
            await add_expenses_bulk(to_import)
            # Clean up the session
            _import_sessions.pop(import_id, None)
            set_done(True)
        except Exception as exc:
            set_error(f"Import failed: {exc}")
        finally:
            set_saving(False)

    # ---- Loading state -----
    if transactions is None:
        return html.div(
            {"class": "text-center py-5"},
            html.div({"class": "spinner-border text-primary"}),
            html.p({"class": "text-muted mt-2"}, "Loading parsed transactions…"),
        )

    # ---- Done state -----
    if done:
        imported_count = sum(1 for d in decisions.values() if d in ("import", "replace"))
        return html.div(
            {"class": "row justify-content-center"},
            html.div(
                {"class": "col-lg-6 text-center py-5"},
                html.i({"class": "bi bi-check-circle-fill text-success", "style": {"fontSize": "4rem"}}),
                html.h3({"class": "mt-3 fw-bold"}, f"{imported_count} transaction(s) imported!"),
                html.p({"class": "text-muted mb-4"}, "Your expenses have been saved to the sheet."),
                html.div(
                    {"class": "d-flex gap-3 justify-content-center"},
                    html.button(
                        {"class": "btn btn-primary", "onClick": lambda _: on_navigate("dashboard") if on_navigate else None},
                        html.i({"class": "bi bi-speedometer2 me-2"}),
                        "Go to Dashboard",
                    ),
                    html.button(
                        {"class": "btn btn-outline-primary", "onClick": lambda _: on_navigate("import") if on_navigate else None},
                        html.i({"class": "bi bi-upload me-2"}),
                        "Import Another",
                    ),
                ),
            ),
        )

    # ---- Review table -----
    total_to_import = sum(1 for d in decisions.values() if d in ("import", "replace"))
    total_amount = sum(
        float(tx.get("amount", 0))
        for i, tx in enumerate(transactions)
        if decisions.get(i) in ("import", "replace")
    )
    duplicates_count = sum(1 for tx in transactions if tx.get("potential_duplicate"))

    return html.div(
        html.div(
            {"class": "d-flex justify-content-between align-items-start mb-4"},
            html.div(
                html.h3({"class": "fw-bold mb-1"}, html.i({"class": "bi bi-clipboard-check me-2"}), "Review Transactions"),
                html.p(
                    {"class": "text-muted mb-0"},
                    f"{len(transactions)} transactions parsed  ·  "
                    f"{duplicates_count} potential duplicate(s) flagged",
                ),
            ),
            html.div(
                {"class": "text-end"},
                html.div({"class": "fw-bold"}, f"{total_to_import} selected  ·  ${total_amount:,.2f}"),
                html.button(
                    {
                        "class": "btn btn-success mt-2",
                        "onClick": confirm_import,
                        "disabled": saving or total_to_import == 0,
                    },
                    html.span(
                        {"class": "spinner-border spinner-border-sm me-2",
                         "style": {"display": "inline-block" if saving else "none"}},
                    ) if saving else html.i({"class": "bi bi-check-lg me-2"}),
                    f"{'Importing…' if saving else f'Import {total_to_import} Transaction(s)'}",
                ),
            ),
        ),

        # Legend
        html.div(
            {"class": "d-flex gap-3 mb-3"},
            html.span({"class": "badge bg-success"}, "Import"),
            html.small({"class": "text-muted"}, "= will be saved"),
            html.span({"class": "badge bg-secondary"}, "Skip"),
            html.small({"class": "text-muted"}, "= won't be saved"),
            html.span({"class": "badge bg-warning text-dark"}, "Replace"),
            html.small({"class": "text-muted"}, "= saves this, deletes the manual entry"),
        ),

        # Error
        html.div(
            {"class": "alert alert-danger", "style": {"display": "block" if error else "none"}},
            error,
        ),

        # Transaction rows
        html.div(
            {"class": "card border-0 shadow-sm"},
            html.div(
                {"class": "table-responsive"},
                html.table(
                    {"class": "table table-hover align-middle mb-0"},
                    html.thead(
                        {"class": "table-light"},
                        html.tr(
                            html.th("Date"),
                            html.th("Description"),
                            html.th("Category"),
                            html.th({"class": "text-end"}, "Amount"),
                            html.th("Status"),
                            html.th("Decision"),
                        ),
                    ),
                    html.tbody(
                        *[
                            _review_row(
                                idx=i,
                                tx=tx,
                                decision=decisions.get(i, "skip"),
                                on_decision=set_decision,
                            )
                            for i, tx in enumerate(transactions)
                        ]
                    ),
                ),
            ),
        ),
    )


@component
def _review_row(idx: int, tx: dict, decision: str, on_decision):
    """Single transaction row in the review table with a 3-way toggle."""
    has_dup = bool(tx.get("potential_duplicate"))
    dup = tx.get("potential_duplicate", {})
    confidence = tx.get("duplicate_confidence", 0.0)

    row_bg = {
        "import": "",
        "skip": "table-secondary",
        "replace": "table-warning",
    }.get(decision, "")

    return html.tr(
        {"class": row_bg},
        html.td({"style": {"fontSize": "0.875rem"}}, tx.get("date", "—")),
        html.td(
            html.div({"class": "fw-semibold", "style": {"fontSize": "0.875rem"}}, tx.get("description", "—")),
            # Show matched manual entry if flagged
            html.div(
                {"style": {"display": "block" if has_dup else "none"}},
                html.small(
                    {"class": "text-warning"},
                    html.i({"class": "bi bi-exclamation-triangle me-1"}),
                    f"Possible duplicate of: \"{dup.get('description', '')}\" "
                    f"on {dup.get('date', '')} (${float(dup.get('amount', 0)):,.2f}) "
                    f"— {int(confidence * 100)}% match",
                ),
            ),
        ),
        html.td(html.span({"class": "badge bg-light text-dark"}, tx.get("category", "Other"))),
        html.td({"class": "text-end fw-semibold"}, f"${float(tx.get('amount', 0)):,.2f}"),
        html.td(
            html.span(
                {"class": f"badge {'bg-warning text-dark' if has_dup else 'bg-success'}"},
                "⚠ Duplicate" if has_dup else "New",
            ),
        ),
        html.td(
            html.div(
                {"class": "btn-group btn-group-sm", "role": "group"},
                _decision_btn("import", "Import", "success", decision, idx, on_decision),
                _decision_btn("skip", "Skip", "secondary", decision, idx, on_decision),
                *(
                    [_decision_btn("replace", "Replace", "warning", decision, idx, on_decision)]
                    if has_dup else []
                ),
            ),
        ),
    )


@component
def _decision_btn(value: str, label: str, variant: str, current: str, idx: int, on_decision):
    active = current == value
    return html.button(
        {
            "type": "button",
            "class": f"btn btn-{'outline-' if not active else ''}{variant}",
            "onClick": lambda _: on_decision(idx, value),
        },
        label,
    )
