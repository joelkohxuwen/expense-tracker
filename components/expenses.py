"""
Expenses page component.

Full expense list with:
  - Month/category/user filters
  - Edit and delete actions
  - Add expense form (reuses ExpenseForm)

ReactPy pattern: lifting state.
The filter controls and the expense table share state that lives here in
the parent component. Child components receive the state as props and call
callbacks to request changes — the same pattern as in React.
"""
from datetime import datetime

from reactpy import component, html, hooks

from database.sheets import get_expenses, get_categories, add_expense, delete_expense, update_expense
from components.expense_form import ExpenseForm


def _months_options(expenses: list[dict]) -> list[str]:
    """Return sorted unique YYYY-MM strings from the expense list."""
    months = set()
    for e in expenses:
        d = e.get("date", "")
        if len(d) >= 7:
            months.add(d[:7])
    return sorted(months, reverse=True)


@component
def ExpensesPage(user: dict, on_navigate):
    """
    Full paginated expense list with filters and inline edit/delete.

    ReactPy pattern: controlled filter state.
    Three use_state variables hold the active filter values. The filtered
    list is derived synchronously on every render — no extra effect needed.
    """
    expenses, set_expenses = hooks.use_state(None)
    categories, set_categories = hooks.use_state([])
    loading, set_loading = hooks.use_state(True)
    refresh_key, set_refresh_key = hooks.use_state(0)

    # Filters
    filter_month, set_filter_month = hooks.use_state("")
    filter_category, set_filter_category = hooks.use_state("")
    filter_user, set_filter_user = hooks.use_state("")

    # Form/edit state
    show_add_form, set_show_add_form = hooks.use_state(False)
    editing_id, set_editing_id = hooks.use_state(None)
    confirm_delete_id, set_confirm_delete_id = hooks.use_state(None)

    @hooks.use_effect(dependencies=[refresh_key])
    async def load_data():
        set_loading(True)
        all_exp = await get_expenses(user_email=None)
        cats = await get_categories()
        set_expenses(all_exp)
        set_categories(cats)
        set_loading(False)

    async def handle_add(expense: dict):
        await add_expense(expense)
        set_show_add_form(False)
        set_refresh_key(refresh_key + 1)

    async def handle_edit_save(expense: dict):
        updates = {k: v for k, v in expense.items() if k != "id"}
        await update_expense(expense["id"], updates)
        set_editing_id(None)
        set_refresh_key(refresh_key + 1)

    async def handle_delete(expense_id: str):
        await delete_expense(expense_id)
        set_confirm_delete_id(None)
        set_refresh_key(refresh_key + 1)

    # ---- Derive filtered list -----------------------------------------------
    all_expenses = expenses or []
    users = sorted({e.get("user_email", "").split("@")[0] for e in all_expenses if e.get("user_email")})
    months = _months_options(all_expenses)

    filtered = all_expenses
    if filter_month:
        filtered = [e for e in filtered if e.get("date", "").startswith(filter_month)]
    if filter_category:
        filtered = [e for e in filtered if e.get("category", "") == filter_category]
    if filter_user:
        filtered = [e for e in filtered if filter_user in e.get("user_email", "")]

    total_filtered = sum(float(e.get("amount", 0)) for e in filtered if e.get("amount"))

    # ---- Render -------------------------------------------------------------
    return html.div(
        # Page header
        html.div(
            {"class": "d-flex justify-content-between align-items-center mb-4"},
            html.h3({"class": "mb-0 fw-bold"}, html.i({"class": "bi bi-list-ul me-2"}), "All Expenses"),
            html.button(
                {"class": "btn btn-primary", "onClick": lambda _: set_show_add_form(not show_add_form)},
                html.i({"class": f"bi bi-{'x-lg' if show_add_form else 'plus-lg'} me-2"}),
                "Cancel" if show_add_form else "Add Expense",
            ),
        ),

        # Add form
        html.div(
            {"class": "mb-4", "style": {"display": "block" if show_add_form else "none"}},
            ExpenseForm(
                user_email=user["email"],
                categories=categories,
                on_save=handle_add,
                on_cancel=lambda: set_show_add_form(False),
            ),
        ),

        # Filters
        html.div(
            {"class": "card border-0 shadow-sm mb-4"},
            html.div(
                {"class": "card-body py-3"},
                html.div(
                    {"class": "row g-2 align-items-end"},
                    _filter_select("Month", months, filter_month, set_filter_month, "All months"),
                    _filter_select("Category", categories, filter_category, set_filter_category, "All categories"),
                    _filter_select("Person", users, filter_user, set_filter_user, "All people"),
                    html.div(
                        {"class": "col-auto"},
                        html.button(
                            {
                                "class": "btn btn-outline-secondary btn-sm",
                                "onClick": lambda _: [
                                    set_filter_month(""),
                                    set_filter_category(""),
                                    set_filter_user(""),
                                ],
                            },
                            html.i({"class": "bi bi-x-circle me-1"}),
                            "Clear",
                        ),
                    ),
                ),
            ),
        ),

        # Loading
        html.div(
            {"class": "text-center py-5", "style": {"display": "block" if loading else "none"}},
            html.div({"class": "spinner-border text-primary"}),
        ),

        # Results summary + table
        html.div(
            {"style": {"display": "none" if loading else "block"}},
            html.div(
                {"class": "d-flex justify-content-between align-items-center mb-3"},
                html.small({"class": "text-muted"}, f"{len(filtered)} transaction(s)"),
                html.span({"class": "fw-bold text-danger"}, f"Total: ${total_filtered:,.2f}"),
            ),

            # Expense table
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
                                html.th("Person"),
                                html.th("Source"),
                                html.th({"class": "text-end"}, "Amount"),
                                html.th({"class": "text-end"}, "Actions"),
                            ),
                        ),
                        html.tbody(
                            *[
                                _expense_table_row(
                                    expense=e,
                                    categories=categories,
                                    user_email=user["email"],
                                    is_editing=editing_id == e.get("id"),
                                    is_confirming_delete=confirm_delete_id == e.get("id"),
                                    on_edit_start=lambda eid=e.get("id"): set_editing_id(eid),
                                    on_edit_save=handle_edit_save,
                                    on_edit_cancel=lambda: set_editing_id(None),
                                    on_delete_start=lambda eid=e.get("id"): set_confirm_delete_id(eid),
                                    on_delete_confirm=lambda eid=e.get("id"): handle_delete(eid),
                                    on_delete_cancel=lambda: set_confirm_delete_id(None),
                                )
                                for e in filtered
                            ] if filtered else [
                                html.tr(html.td({"colspan": "7", "class": "text-center text-muted py-5"}, "No expenses match your filters."))
                            ]
                        ),
                    ),
                ),
            ),
        ),
    )


@component
def _filter_select(label: str, options: list, value: str, on_change, placeholder: str):
    return html.div(
        {"class": "col-auto"},
        html.label({"class": "form-label mb-1", "style": {"fontSize": "0.8rem"}}, label),
        html.select(
            {
                "class": "form-select form-select-sm",
                "value": value,
                "onChange": lambda e: on_change(e["target"]["value"]),
            },
            html.option({"value": ""}, placeholder),
            *[html.option({"value": opt}, opt) for opt in options],
        ),
    )


@component
def _expense_table_row(
    expense: dict,
    categories: list,
    user_email: str,
    is_editing: bool,
    is_confirming_delete: bool,
    on_edit_start,
    on_edit_save,
    on_edit_cancel,
    on_delete_start,
    on_delete_confirm,
    on_delete_cancel,
):
    source_badge = {
        "manual": ("success", "Manual"),
        "import": ("info", "Imported"),
    }.get(expense.get("source", "manual"), ("secondary", "?"))

    if is_editing:
        return html.tr(
            html.td(
                {"colspan": "7", "class": "p-0"},
                html.div(
                    {"class": "p-3"},
                    ExpenseForm(
                        user_email=user_email,
                        categories=categories,
                        on_save=on_edit_save,
                        on_cancel=on_edit_cancel,
                        initial=expense,
                    ),
                ),
            ),
        )

    if is_confirming_delete:
        return html.tr(
            {"class": "table-danger"},
            html.td({"colspan": "5"}, f"Delete \"{expense.get('description', '')}\"? This cannot be undone."),
            html.td(
                {"class": "text-end", "colspan": "2"},
                html.button(
                    {"class": "btn btn-danger btn-sm me-2", "onClick": lambda _: on_delete_confirm()},
                    "Yes, Delete",
                ),
                html.button(
                    {"class": "btn btn-outline-secondary btn-sm", "onClick": lambda _: on_delete_cancel()},
                    "Cancel",
                ),
            ),
        )

    return html.tr(
        html.td({"style": {"fontSize": "0.875rem"}}, expense.get("date", "—")),
        html.td(
            html.div({"class": "fw-semibold", "style": {"fontSize": "0.875rem", "maxWidth": "240px"}},
                     expense.get("description", "—")),
            html.small({"class": "text-muted"}, expense.get("notes", "") or ""),
        ),
        html.td(html.span({"class": "badge bg-light text-dark"}, expense.get("category", "Other"))),
        html.td({"style": {"fontSize": "0.875rem"}}, expense.get("user_email", "").split("@")[0]),
        html.td(html.span({"class": f"badge bg-{source_badge[0]}"}, source_badge[1])),
        html.td({"class": "text-end fw-semibold text-danger"},
                f"${float(expense.get('amount', 0)):,.2f}"),
        html.td(
            {"class": "text-end"},
            html.button(
                {"class": "btn btn-sm btn-outline-secondary me-1", "onClick": lambda _: on_edit_start(),
                 "title": "Edit"},
                html.i({"class": "bi bi-pencil"}),
            ),
            html.button(
                {"class": "btn btn-sm btn-outline-danger", "onClick": lambda _: on_delete_start(),
                 "title": "Delete"},
                html.i({"class": "bi bi-trash"}),
            ),
        ),
    )
