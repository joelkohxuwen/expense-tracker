"""
Reusable add/edit expense form component.

Demonstrates controlled inputs in ReactPy: each html.input has a 'value'
bound to a use_state variable and an 'onChange' that calls the state setter.
This mirrors React's controlled component pattern exactly.
"""
from datetime import datetime

from reactpy import component, html, hooks


def _default_category(categories: list, init_cat: str) -> str:
    """Return the best default: use init_cat if set, else find the first food-like category."""
    if init_cat:
        return init_cat
    for cat in (categories or []):
        if "food" in cat.lower():
            return cat
    return "Food & Dining"


@component
def ExpenseForm(
    user_email: str,
    categories: list,
    on_save,           # Callable[dict] — called with the completed expense dict
    on_cancel=None,    # Optional Callable[] — called when user dismisses the form
    initial: dict = None,  # Pre-fill for edit mode
):
    """
    Form for creating or editing a single expense.

    ReactPy pattern: controlled inputs.
    Every text/select input's current value lives in a use_state variable.
    On change, the state is updated → ReactPy diffs → only the changed element
    is patched in the browser over WebSocket.

    Args:
        user_email:  Owner of the new/edited expense.
        categories:  List of category strings from Google Sheets.
        on_save:     Called with the completed expense dict on form submit.
        on_cancel:   Called when the user clicks Cancel (optional).
        initial:     Pre-filled expense dict for edit mode (optional).
    """
    init = initial or {}

    # --- Controlled state for each form field ---
    date, set_date = hooks.use_state(init.get("date", datetime.now().strftime("%Y-%m-%d")))
    amount, set_amount = hooks.use_state(init.get("amount", ""))
    description, set_description = hooks.use_state(init.get("description", ""))
    category, set_category = hooks.use_state(
        _default_category(categories or [], init.get("category", ""))
    )
    notes, set_notes = hooks.use_state(init.get("notes", ""))
    error, set_error = hooks.use_state("")
    saving, set_saving = hooks.use_state(False)

    async def handle_save(_event):
        # Client-side validation
        if not description.strip():
            set_error("Description is required.")
            return
        try:
            amt = float(amount)
            if amt <= 0:
                raise ValueError
        except ValueError:
            set_error("Please enter a valid positive amount.")
            return

        set_error("")
        set_saving(True)

        expense = {
            "date": date,
            "amount": str(amt),
            "description": description.strip(),
            "category": category,
            "user_email": user_email,
            "source": "manual",
            "raw_description": description.strip(),
            "notes": notes.strip(),
        }
        if init.get("id"):
            expense["id"] = init["id"]

        await on_save(expense)
        set_saving(False)

    cat_options = [
        html.option({"value": cat, "selected": cat == category}, cat)
        for cat in (categories or ["Food & Dining", "Shopping", "Transportation", "Other"])
    ]

    return html.div(
        {"class": "card border-0 shadow-sm"},
        html.div(
            {"class": "card-body p-4"},
            html.h5(
                {"class": "card-title mb-4"},
                html.i({"class": "bi bi-pencil-square me-2 text-primary"}),
                "Edit Expense" if init.get("id") else "Add Expense",
            ),
            # Error alert
            html.div(
                {"class": f"alert alert-danger py-2 mb-3{'d-none' if not error else ''}",
                 "style": {"display": "none" if not error else "block"}},
                error,
            ),
            html.div(
                {"class": "row g-3"},
                # Date
                html.div(
                    {"class": "col-md-6"},
                    html.label({"class": "form-label fw-semibold", "for": "exp-date"}, "Date"),
                    html.input({
                        "id": "exp-date",
                        "type": "date",
                        "class": "form-control",
                        "value": date,
                        "onChange": lambda e: set_date(e["target"]["value"]),
                    }),
                ),
                # Amount
                html.div(
                    {"class": "col-md-6"},
                    html.label({"class": "form-label fw-semibold", "for": "exp-amount"}, "Amount"),
                    html.div(
                        {"class": "input-group"},
                        html.span({"class": "input-group-text"}, "$"),
                        html.input({
                            "id": "exp-amount",
                            "type": "number",
                            "step": "0.01",
                            "min": "0",
                            "class": "form-control",
                            "placeholder": "0.00",
                            "value": str(amount),
                            "onChange": lambda e: set_amount(e["target"]["value"]),
                        }),
                    ),
                ),
                # Description
                html.div(
                    {"class": "col-12"},
                    html.label({"class": "form-label fw-semibold", "for": "exp-desc"}, "Description"),
                    html.input({
                        "id": "exp-desc",
                        "type": "text",
                        "class": "form-control",
                        "placeholder": "e.g. Lunch at Hawker Centre",
                        "value": description,
                        "onChange": lambda e: set_description(e["target"]["value"]),
                    }),
                ),
                # Category
                html.div(
                    {"class": "col-md-6"},
                    html.label({"class": "form-label fw-semibold", "for": "exp-cat"}, "Category"),
                    html.select(
                        {
                            "id": "exp-cat",
                            "class": "form-select",
                            "value": category,
                            "onChange": lambda e: set_category(e["target"]["value"]),
                        },
                        *cat_options,
                    ),
                ),
                # Notes
                html.div(
                    {"class": "col-md-6"},
                    html.label({"class": "form-label fw-semibold", "for": "exp-notes"}, "Notes (optional)"),
                    html.input({
                        "id": "exp-notes",
                        "type": "text",
                        "class": "form-control",
                        "placeholder": "Any extra detail",
                        "value": notes,
                        "onChange": lambda e: set_notes(e["target"]["value"]),
                    }),
                ),
                # Action buttons
                html.div(
                    {"class": "col-12 d-flex gap-2 mt-2"},
                    html.button(
                        {
                            "type": "button",
                            "class": "btn btn-primary",
                            "onClick": handle_save,
                            "disabled": saving,
                        },
                        html.span(
                            {"class": "spinner-border spinner-border-sm me-2",
                             "style": {"display": "inline-block" if saving else "none"}},
                        ) if saving else html.i({"class": "bi bi-check-lg me-2"}),
                        "Saving…" if saving else "Save Expense",
                    ),
                    html.button(
                        {
                            "type": "button",
                            "class": "btn btn-outline-secondary",
                            "onClick": lambda _: on_cancel() if on_cancel else None,
                            "style": {"display": "inline-block" if on_cancel else "none"},
                        },
                        "Cancel",
                    ),
                ),
            ),
        ),
    )
