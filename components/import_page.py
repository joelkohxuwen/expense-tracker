"""
Import page — two importers side by side:

  Tab A — CC Statement (CSV):
    Upload a bank CSV → dedup check → per-transaction review → bulk insert.

  Tab B — History File (pipe-delimited):
    Upload a pipe-separated history file in the format:
        YYYY-MM-DD | INITIAL | CATEGORY | AMOUNT | DESCRIPTION | [NOTES]
    Map person initials to email addresses → summary preview → bulk insert.
    No per-row review needed for clean historical data.

ReactPy pattern: conditional rendering based on props + tab state.
"""
from reactpy import component, html, hooks

from database.sheets import add_expenses_bulk, delete_expense, get_all_users


def _display_name(email: str, users: list) -> str:
    """Return first name for an email, falling back to email prefix."""
    for u in users:
        if u.get("email") == email:
            n = u.get("name", "").strip()
            if n:
                return n.split()[0]
            break
    return email.split("@")[0].capitalize()


# The import_sessions dict is defined in main.py and injected here at import time.
_import_sessions: dict = {}


def set_import_sessions_ref(sessions: dict) -> None:
    """Called from main.py after creating the import_sessions dict."""
    global _import_sessions
    _import_sessions = sessions


@component
def ImportPage(user: dict, import_id: str = "", on_navigate=None):
    """
    Root of the import page.

    If import_id is set (after a file was POSTed to a FastAPI endpoint and
    the server redirected back), show the appropriate review step.
    Otherwise show the two-tab upload form.
    """
    if import_id:
        data = _import_sessions.get(import_id, {})
        if data.get("type") == "flat":
            return _FlatReviewStep(user=user, import_id=import_id, on_navigate=on_navigate)
        return _ReviewStep(user=user, import_id=import_id, on_navigate=on_navigate)

    return _UploadTabs(user=user)


@component
def _UploadStep():
    """Upload form — a regular HTML multipart form that POSTs to FastAPI."""
    # _UploadTabs replaces the old _UploadStep — this component is now unused
    # but kept to avoid breaking any external references.
    return _UploadTabs(user={})


@component
def _UploadTabs(user: dict):
    """Two-tab upload form: CC Statement CSV | Pipe-delimited history file."""
    active_tab, set_active_tab = hooks.use_state("cc")

    def tab_btn(key: str, label: str, icon: str):
        active = active_tab == key
        return html.button(
            {
                "class": f"nav-link {'active fw-semibold' if active else ''}",
                "type": "button",
                "onClick": lambda _: set_active_tab(key),
            },
            html.i({"class": f"bi bi-{icon} me-2"}),
            label,
        )

    return html.div(
        html.h3({"class": "fw-bold mb-4"},
                html.i({"class": "bi bi-upload me-2"}), "Import Expenses"),

        # Tab switcher
        html.ul(
            {"class": "nav nav-tabs mb-4"},
            html.li({"class": "nav-item"}, tab_btn("cc",   "Credit Card Statement", "credit-card")),
            html.li({"class": "nav-item"}, tab_btn("flat", "History File (.txt)",   "file-text")),
        ),

        # CC Statement tab
        html.div(
            {"style": {"display": "block" if active_tab == "cc" else "none"}},
            _CcUploadPanel(user=user),
        ),

        # Flat file tab
        html.div(
            {"style": {"display": "block" if active_tab == "flat" else "none"}},
            _FlatUploadPanel(user=user),
        ),
    )


@component
def _CcUploadPanel(user: dict):
    """
    CC statement upload form.

    Supports both CSV and PDF files.  When a PDF is selected, a cardholder
    mapping section appears so the user can link each cardholder name (as it
    appears in the PDF) to a family member's email address.  This is needed
    for UOB consolidated statements that cover multiple cards.  Citi individual
    PDFs can leave the mapping empty — all transactions default to the
    uploading user.
    """
    is_pdf,      set_is_pdf      = hooks.use_state(False)
    # Each entry: {"name": str, "email": str}
    cardholders, set_cardholders = hooks.use_state([
        {"name": (user.get("name") or "").upper(), "email": user.get("email", "")}
    ])

    def on_file_change(e):
        val = (e["target"]["value"] or "").lower()
        set_is_pdf(val.endswith(".pdf"))

    def add_cardholder(_event):
        set_cardholders([*cardholders, {"name": "", "email": ""}])

    def remove_cardholder(idx: int, _event):
        if len(cardholders) > 1:
            set_cardholders([c for i, c in enumerate(cardholders) if i != idx])

    def update_name(idx: int, val: str):
        updated = [dict(c) for c in cardholders]
        updated[idx]["name"] = val.upper()
        set_cardholders(updated)

    def update_ch_email(idx: int, val: str):
        updated = [dict(c) for c in cardholders]
        updated[idx]["email"] = val
        set_cardholders(updated)

    cardholder_rows = [
        html.div(
            {"class": "row g-2 align-items-center mb-2", "key": str(idx)},
            # Name as in PDF (all caps)
            html.div(
                {"class": "col"},
                html.input({
                    "type":        "text",
                    "name":        f"ch_name_{idx}",
                    "value":       ch["name"],
                    "placeholder": "FULL NAME AS IN PDF",
                    "class":       "form-control form-control-sm",
                    "style":       {"textTransform": "uppercase"},
                    "onChange":    lambda e, i=idx: update_name(i, e["target"]["value"]),
                }),
            ),
            html.div({"class": "col-auto"}, html.span({"class": "text-muted"}, "→")),
            # Email
            html.div(
                {"class": "col"},
                html.input({
                    "type":        "email",
                    "name":        f"ch_email_{idx}",
                    "value":       ch["email"],
                    "placeholder": "person@email.com",
                    "class":       "form-control form-control-sm",
                    "onChange":    lambda e, i=idx: update_ch_email(i, e["target"]["value"]),
                }),
            ),
            # Remove button
            html.div(
                {"class": "col-auto"},
                html.button(
                    {
                        "type":     "button",
                        "class":    "btn btn-sm btn-outline-danger",
                        "onClick":  lambda e, i=idx: remove_cardholder(i, e),
                        "disabled": len(cardholders) <= 1,
                        "title":    "Remove",
                    },
                    html.i({"class": "bi bi-x-lg"}),
                ),
            ),
        )
        for idx, ch in enumerate(cardholders)
    ]

    return html.div(
        html.div(
            {"class": "row justify-content-center"},
            html.div(
                {"class": "col-lg-8"},
                html.p(
                    {"class": "text-muted mb-4"},
                    "Upload a bank statement in ",
                    html.strong("CSV"),
                    " or ",
                    html.strong("PDF"),
                    " format.  Supported: UOB consolidated PDF, Citi individual PDF, "
                    "DBS/POSB CSV, OCBC CSV, Chase CSV, and most generic CSV formats.",
                ),
                html.div(
                    {"class": "card border-0 shadow-sm"},
                    html.div(
                        {"class": "card-body p-4"},
                        html.form(
                            {
                                "action":  "/api/import-csv",
                                "method":  "post",
                                "enctype": "multipart/form-data",
                            },

                            # ---- File picker ----
                            html.div(
                                {"class": "mb-4"},
                                html.label(
                                    {"class": "form-label fw-semibold", "for": "cc-file"},
                                    "Select statement file (.csv or .pdf)",
                                ),
                                html.input({
                                    "id":       "cc-file",
                                    "type":     "file",
                                    "name":     "file",
                                    "accept":   ".csv,.pdf,text/csv,application/pdf",
                                    "class":    "form-control form-control-lg",
                                    "required": True,
                                    "onChange": on_file_change,
                                }),
                                html.div(
                                    {"class": "form-text"},
                                    html.strong("PDF: "),
                                    "UOB consolidated or Citi individual statement.  ",
                                    html.strong("CSV: "),
                                    "DBS/POSB — Card Transactions → Download  |  "
                                    "OCBC — Account Statement → Export CSV",
                                ),
                            ),

                            # ---- Cardholder mapping (PDF only) ----
                            html.div(
                                {
                                    "class": "mb-4",
                                    "style": {"display": "block" if is_pdf else "none"},
                                },
                                html.div(
                                    {"class": "d-flex justify-content-between align-items-center mb-2"},
                                    html.div(
                                        html.h6(
                                            {"class": "fw-semibold mb-0"},
                                            html.i({"class": "bi bi-person-badge me-2"}),
                                            "Cardholder name mapping",
                                        ),
                                        html.div(
                                            {"class": "form-text mt-0"},
                                            "Enter each name exactly as it appears in the PDF "
                                            "(all caps).  Leave blank for Citi — only your account is imported.",
                                        ),
                                    ),
                                    html.button(
                                        {
                                            "type":    "button",
                                            "class":   "btn btn-sm btn-outline-primary ms-3 flex-shrink-0",
                                            "onClick": add_cardholder,
                                        },
                                        html.i({"class": "bi bi-plus-circle me-1"}),
                                        "Add cardholder",
                                    ),
                                ),
                                *cardholder_rows,
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
def _FlatUploadPanel(user: dict):
    """
    Upload form for the custom pipe-delimited history file.

    Starts with one person row (the logged-in user pre-filled for the first
    initial). The "Add person" button appends extra rows dynamically.
    Form fields are named initial_0 / email_0, initial_1 / email_1, … so the
    FastAPI endpoint can parse any number of mappings.
    """
    # Each entry: {"initial": str, "email": str}
    people, set_people = hooks.use_state([
        {"initial": "J", "email": user.get("email", "")}
    ])

    def add_person(_event):
        set_people([*people, {"initial": "", "email": ""}])

    def remove_person(idx: int, _event):
        if len(people) > 1:
            set_people([p for i, p in enumerate(people) if i != idx])

    def update_initial(idx: int, val: str):
        updated = [dict(p) for p in people]
        updated[idx]["initial"] = val.upper()[:3]
        set_people(updated)

    def update_email(idx: int, val: str):
        updated = [dict(p) for p in people]
        updated[idx]["email"] = val
        set_people(updated)

    person_rows = [
        html.div(
            {"class": "row g-2 align-items-center mb-2", "key": str(idx)},
            # Initial box
            html.div(
                {"class": "col-auto"},
                html.input({
                    "type":        "text",
                    "name":        f"initial_{idx}",
                    "value":       p["initial"],
                    "maxLength":   "3",
                    "placeholder": "J",
                    "class":       "form-control form-control-sm fw-bold text-center",
                    "style":       {"width": "60px", "textTransform": "uppercase"},
                    "onChange":    lambda e, i=idx: update_initial(i, e["target"]["value"]),
                }),
            ),
            # Arrow label
            html.div(
                {"class": "col-auto"},
                html.span({"class": "text-muted px-1"}, "→"),
            ),
            # Email input
            html.div(
                {"class": "col"},
                html.input({
                    "type":        "email",
                    "name":        f"email_{idx}",
                    "value":       p["email"],
                    "placeholder": "person@email.com",
                    "class":       "form-control form-control-sm",
                    "onChange":    lambda e, i=idx: update_email(i, e["target"]["value"]),
                }),
            ),
            # Remove button
            html.div(
                {"class": "col-auto"},
                html.button(
                    {
                        "type":     "button",
                        "class":    "btn btn-sm btn-outline-danger",
                        "onClick":  lambda e, i=idx: remove_person(i, e),
                        "disabled": len(people) <= 1,
                        "title":    "Remove this person",
                    },
                    html.i({"class": "bi bi-x-lg"}),
                ),
            ),
        )
        for idx, p in enumerate(people)
    ]

    return html.div(
        html.div(
            {"class": "row justify-content-center"},
            html.div(
                {"class": "col-lg-7"},
                html.p(
                    {"class": "text-muted mb-3"},
                    "Upload a pipe-separated history file in this format:",
                ),
                html.pre(
                    {
                        "class": "rounded p-3 mb-4",
                        "style": {"background": "#f1f5f9", "fontSize": "0.8rem"},
                    },
                    "YYYY-MM-DD | INITIAL | CATEGORY | AMOUNT | DESCRIPTION | [NOTES]\n"
                    "2026-02-18 | J | Transport | 90.73 | Petrol |\n"
                    "2026-03-07 | E | Food      | 100.00 | Xiangxiang dinner |",
                ),

                html.div(
                    {"class": "card border-0 shadow-sm"},
                    html.div(
                        {"class": "card-body p-4"},
                        html.form(
                            {
                                "action":  "/api/import-flat",
                                "method":  "post",
                                "enctype": "multipart/form-data",
                            },

                            # ---- Person mapping section ----
                            html.div(
                                {"class": "mb-4"},
                                html.div(
                                    {"class": "d-flex justify-content-between align-items-center mb-3"},
                                    html.h6(
                                        {"class": "fw-semibold mb-0"},
                                        html.i({"class": "bi bi-people me-2"}),
                                        "Map person initials to email addresses",
                                    ),
                                    html.button(
                                        {
                                            "type":    "button",
                                            "class":   "btn btn-sm btn-outline-primary",
                                            "onClick": add_person,
                                        },
                                        html.i({"class": "bi bi-plus-circle me-1"}),
                                        "Add person",
                                    ),
                                ),
                                *person_rows,
                            ),

                            # ---- File picker ----
                            html.div(
                                {"class": "mb-4"},
                                html.label(
                                    {"class": "form-label fw-semibold", "for": "flat-file"},
                                    "Select history file (.txt or .csv)",
                                ),
                                html.input({
                                    "id":       "flat-file",
                                    "type":     "file",
                                    "name":     "file",
                                    "accept":   ".txt,.csv,text/plain,text/csv",
                                    "class":    "form-control form-control-lg",
                                    "required": True,
                                }),
                            ),

                            html.button(
                                {"type": "submit", "class": "btn btn-primary btn-lg w-100"},
                                html.i({"class": "bi bi-cloud-upload me-2"}),
                                "Parse History File",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


@component
def _FlatReviewStep(user: dict, import_id: str, on_navigate):
    """
    Summary preview for flat-file imports.
    Shows row counts and totals per person + top categories.
    User confirms to bulk-insert everything, or cancels.
    """
    summary,      set_summary      = hooks.use_state(None)
    transactions, set_transactions = hooks.use_state([])
    users_list,   set_users_list   = hooks.use_state([])
    saving,       set_saving       = hooks.use_state(False)
    done,         set_done         = hooks.use_state(False)
    error,        set_error        = hooks.use_state("")

    @hooks.use_effect(dependencies=[import_id])
    async def load_summary():
        data = _import_sessions.get(import_id)
        if data and data.get("user_email") == user["email"]:
            from utils.flat_file_parser import summarise
            txs = data.get("transactions", [])
            set_transactions(txs)
            set_summary(summarise(txs))
        try:
            ul = await get_all_users()
            set_users_list(ul)
        except Exception:
            pass

    async def confirm(_event):
        set_saving(True)
        set_error("")
        try:
            await add_expenses_bulk(transactions)
            _import_sessions.pop(import_id, None)
            set_done(True)
        except Exception as exc:
            set_error(f"Import failed: {exc}")
        finally:
            set_saving(False)

    # Loading
    if summary is None:
        return html.div(
            {"class": "text-center py-5"},
            html.div({"class": "spinner-border text-primary"}),
            html.p({"class": "text-muted mt-2"}, "Parsing file…"),
        )

    # Done
    if done:
        return html.div(
            {"class": "text-center py-5"},
            html.i({"class": "bi bi-check-circle-fill text-success", "style": {"fontSize": "4rem"}}),
            html.h3({"class": "mt-3 fw-bold"},
                    f"{summary['total_rows']} transaction(s) imported!"),
            html.p({"class": "text-muted mb-4"},
                   f"Total value: ${summary['total_amount']:,.2f}"),
            html.div(
                {"class": "d-flex gap-3 justify-content-center"},
                html.button(
                    {"class": "btn btn-primary",
                     "onClick": lambda _: on_navigate("dashboard") if on_navigate else None},
                    html.i({"class": "bi bi-speedometer2 me-2"}), "Go to Dashboard",
                ),
                html.button(
                    {"class": "btn btn-outline-primary",
                     "onClick": lambda _: on_navigate("import") if on_navigate else None},
                    html.i({"class": "bi bi-upload me-2"}), "Import More",
                ),
            ),
        )

    # Preview
    data_store = _import_sessions.get(import_id, {})
    filename = data_store.get("filename", "history file")

    return html.div(
        # Header
        html.div(
            {"class": "d-flex justify-content-between align-items-start mb-4"},
            html.div(
                html.h3({"class": "fw-bold mb-1"},
                        html.i({"class": "bi bi-clipboard-check me-2"}),
                        "Confirm History Import"),
                html.p({"class": "text-muted mb-0"},
                       f"Parsed from {filename}"),
            ),
            html.button(
                {
                    "class": "btn btn-success",
                    "onClick": confirm,
                    "disabled": saving,
                },
                html.span(
                    {"class": "spinner-border spinner-border-sm me-2",
                     "style": {"display": "inline-block" if saving else "none"}},
                ) if saving else html.i({"class": "bi bi-check-lg me-2"}),
                "Importing…" if saving else f"Import all {summary['total_rows']} transactions",
            ),
        ),

        html.div(
            {"class": "alert alert-danger", "style": {"display": "block" if error else "none"}},
            error,
        ),

        # Summary cards
        html.div(
            {"class": "row g-3 mb-4"},
            html.div(
                {"class": "col-sm-4"},
                html.div(
                    {"class": "card border-0 shadow-sm text-center"},
                    html.div(
                        {"class": "card-body py-3"},
                        html.h2({"class": "fw-bold mb-0"}, str(summary["total_rows"])),
                        html.p({"class": "text-muted mb-0"}, "Transactions"),
                    ),
                ),
            ),
            html.div(
                {"class": "col-sm-4"},
                html.div(
                    {"class": "card border-0 shadow-sm text-center"},
                    html.div(
                        {"class": "card-body py-3"},
                        html.h2({"class": "fw-bold mb-0 text-danger"},
                                f"${summary['total_amount']:,.2f}"),
                        html.p({"class": "text-muted mb-0"}, "Total Amount"),
                    ),
                ),
            ),
            html.div(
                {"class": "col-sm-4"},
                html.div(
                    {"class": "card border-0 shadow-sm text-center"},
                    html.div(
                        {"class": "card-body py-3"},
                        html.h2({"class": "fw-bold mb-0"},
                                str(len(summary["by_person"]))),
                        html.p({"class": "text-muted mb-0"}, "People"),
                    ),
                ),
            ),
        ),

        html.div(
            {"class": "row g-4"},
            # Per-person breakdown
            html.div(
                {"class": "col-md-5"},
                html.div(
                    {"class": "card border-0 shadow-sm h-100"},
                    html.div(
                        {"class": "card-body"},
                        html.h6({"class": "fw-semibold mb-3"},
                                html.i({"class": "bi bi-people me-2"}), "Per Person"),
                        *[
                            html.div(
                                {"class": "d-flex justify-content-between border-bottom py-2"},
                                html.span(
                                    {"style": {"fontSize": "0.875rem"}},
                                    html.i({"class": "bi bi-person-circle me-2 text-muted"}),
                                    _display_name(email, users_list),
                                ),
                                html.span(
                                    {"class": "text-end"},
                                    html.span({"class": "badge bg-light text-dark me-2"},
                                              f"{stats['count']} rows"),
                                    html.strong({"class": "text-danger"},
                                                f"${stats['total']:,.2f}"),
                                ),
                            )
                            for email, stats in summary["by_person"].items()
                        ],
                    ),
                ),
            ),
            # Top categories
            html.div(
                {"class": "col-md-7"},
                html.div(
                    {"class": "card border-0 shadow-sm h-100"},
                    html.div(
                        {"class": "card-body"},
                        html.h6({"class": "fw-semibold mb-3"},
                                html.i({"class": "bi bi-tags me-2"}), "Top Categories"),
                        *[
                            html.div(
                                {"class": "d-flex justify-content-between border-bottom py-2"},
                                html.span({"style": {"fontSize": "0.875rem"}}, cat),
                                html.strong({"class": "text-danger"},
                                            f"${amt:,.2f}"),
                            )
                            for cat, amt in summary["top_categories"]
                        ],
                    ),
                ),
            ),
        ),

        # Sample rows
        html.div(
            {"class": "card border-0 shadow-sm mt-4"},
            html.div(
                {"class": "card-header bg-light fw-semibold"},
                f"Preview (first 10 of {summary['total_rows']} rows)",
            ),
            html.div(
                {"class": "table-responsive"},
                html.table(
                    {"class": "table table-sm table-hover align-middle mb-0"},
                    html.thead(
                        {"class": "table-light"},
                        html.tr(
                            html.th("Date"), html.th("Person"),
                            html.th("Category"), html.th("Description"),
                            html.th({"class": "text-end"}, "Amount"),
                        ),
                    ),
                    html.tbody(
                        *[
                            html.tr(
                                html.td({"style": {"fontSize": "0.8rem"}}, tx["date"]),
                                html.td(
                                    {"style": {"fontSize": "0.8rem", "maxWidth": "140px",
                                               "overflow": "hidden", "textOverflow": "ellipsis",
                                               "whiteSpace": "nowrap"}},
                                    _display_name(tx["user_email"], users_list),
                                ),
                                html.td(html.span({"class": "badge bg-light text-dark"},
                                                  tx["category"])),
                                html.td({"style": {"fontSize": "0.8rem"}}, tx["description"]),
                                html.td({"class": "text-end fw-semibold text-danger"},
                                        f"${float(tx['amount']):,.2f}"),
                            )
                            for tx in transactions[:10]
                        ]
                    ),
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
