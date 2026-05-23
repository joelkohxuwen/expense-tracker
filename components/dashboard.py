"""
Dashboard page component.

Shows a summary of the current month's spending, a breakdown by category,
and the 10 most recent expenses. Also includes a quick-add expense form.

ReactPy pattern: use_effect for async data loading.
The component renders a loading state first, then use_effect fires after
mount to fetch real data from Google Sheets and trigger a re-render.
"""
from datetime import datetime

from reactpy import component, html, hooks

from database.sheets import get_expenses, get_categories, add_expense
from components.expense_form import ExpenseForm


def _currency(amount) -> str:
    try:
        return f"${float(amount):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _month_label(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%B %Y")


@component
def Dashboard(user: dict, on_navigate):
    """
    Main landing page after login.

    State variables:
      expenses    — full list fetched from Sheets (None = not yet loaded)
      categories  — list of category strings for the quick-add form
      show_form   — toggle the quick-add expense card
      loading     — True while the initial Sheets fetch is in flight
    """
    expenses, set_expenses = hooks.use_state(None)
    categories, set_categories = hooks.use_state([])
    show_form, set_show_form = hooks.use_state(False)
    loading, set_loading = hooks.use_state(True)
    refresh_key, set_refresh_key = hooks.use_state(0)  # bump to trigger a reload

    @hooks.use_effect(dependencies=[refresh_key])
    async def load_data():
        set_loading(True)
        all_exp = await get_expenses(user_email=None)   # all users for shared view
        cats = await get_categories()
        set_expenses(all_exp)
        set_categories(cats)
        set_loading(False)

    async def handle_save(expense: dict):
        await add_expense(expense)
        set_show_form(False)
        set_refresh_key(refresh_key + 1)  # trigger reload

    # ---- Derived stats (computed from loaded data) -------------------------
    now = datetime.now()
    this_month_expenses = []
    this_year_total = 0.0

    if expenses:
        for e in expenses:
            try:
                exp_date = datetime.strptime(e.get("date", ""), "%Y-%m-%d")
                amt = float(e.get("amount", 0))
                if exp_date.year == now.year:
                    this_year_total += amt
                    if exp_date.month == now.month:
                        this_month_expenses.append(e)
            except (ValueError, TypeError):
                continue

    month_total = sum(float(e.get("amount", 0)) for e in this_month_expenses)

    # Category totals for the current month
    cat_totals: dict[str, float] = {}
    for e in this_month_expenses:
        cat = e.get("category", "Other")
        try:
            cat_totals[cat] = cat_totals.get(cat, 0.0) + float(e.get("amount", 0))
        except (TypeError, ValueError):
            pass
    cat_sorted = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)

    recent = (expenses or [])[:10]

    # ---- Render -------------------------------------------------------------
    return html.div(
        # Header row
        html.div(
            {"class": "d-flex justify-content-between align-items-center mb-4"},
            html.div(
                html.h3({"class": "mb-0 fw-bold"}, f"Hello, {user.get('name', '').split()[0] or 'there'} 👋"),
                html.p(
                    {"class": "text-muted mb-0"},
                    _month_label(now.year, now.month),
                ),
            ),
            html.button(
                {
                    "class": "btn btn-primary",
                    "onClick": lambda _: set_show_form(not show_form),
                },
                html.i({"class": f"bi bi-{'x-lg' if show_form else 'plus-lg'} me-2"}),
                "Cancel" if show_form else "Add Expense",
            ),
        ),

        # Quick-add form (toggleable)
        html.div(
            {"style": {"display": "block" if show_form else "none"}, "class": "mb-4"},
            ExpenseForm(
                user_email=user["email"],
                categories=categories,
                on_save=handle_save,
                on_cancel=lambda: set_show_form(False),
            ),
        ),

        # Summary cards
        html.div(
            {"class": "row g-3 mb-4"},
            _stat_card("This Month", _currency(month_total), "calendar-month", "#4f46e5"),
            _stat_card("This Year", _currency(this_year_total), "graph-up-arrow", "#059669"),
            _stat_card("Transactions", str(len(this_month_expenses)), "receipt", "#d97706"),
            _stat_card("Categories", str(len(cat_totals)), "tags", "#7c3aed"),
        ),

        # Loading spinner
        html.div(
            {"class": "text-center py-5", "style": {"display": "block" if loading else "none"}},
            html.div({"class": "spinner-border text-primary"}),
            html.p({"class": "text-muted mt-2"}, "Loading expenses…"),
        ),

        # Content row: category breakdown + recent transactions
        html.div(
            {"class": "row g-4", "style": {"display": "none" if loading else "flex"}},
            # Category breakdown
            html.div(
                {"class": "col-lg-4"},
                html.div(
                    {"class": "card border-0 shadow-sm h-100"},
                    html.div(
                        {"class": "card-body"},
                        html.h5(
                            {"class": "card-title mb-3"},
                            html.i({"class": "bi bi-pie-chart me-2 text-primary"}),
                            f"Spending by Category — {_month_label(now.year, now.month)}",
                        ),
                        html.div(
                            *[_category_row(cat, amt, month_total) for cat, amt in cat_sorted[:8]]
                        ) if cat_sorted else html.p({"class": "text-muted"}, "No expenses this month yet."),
                    ),
                ),
            ),
            # Recent transactions
            html.div(
                {"class": "col-lg-8"},
                html.div(
                    {"class": "card border-0 shadow-sm h-100"},
                    html.div(
                        {"class": "card-body"},
                        html.div(
                            {"class": "d-flex justify-content-between align-items-center mb-3"},
                            html.h5(
                                {"class": "card-title mb-0"},
                                html.i({"class": "bi bi-clock-history me-2 text-primary"}),
                                "Recent Transactions",
                            ),
                            html.button(
                                {"class": "btn btn-sm btn-outline-primary", "onClick": lambda _: on_navigate("expenses")},
                                "View All",
                            ),
                        ),
                        html.div(
                            *[_expense_row(e) for e in recent]
                        ) if recent else html.p({"class": "text-muted"}, "No expenses yet. Add one above!"),
                    ),
                ),
            ),
        ),
    )


@component
def _stat_card(label: str, value: str, icon: str, color: str):
    return html.div(
        {"class": "col-sm-6 col-xl-3"},
        html.div(
            {"class": "card border-0 shadow-sm"},
            html.div(
                {"class": "card-body d-flex align-items-center gap-3 py-3"},
                html.div(
                    {
                        "style": {
                            "width": "48px", "height": "48px",
                            "borderRadius": "12px",
                            "backgroundColor": color + "20",  # 20 = ~12% opacity hex
                            "display": "flex", "alignItems": "center", "justifyContent": "center",
                            "flexShrink": "0",
                        },
                    },
                    html.i({"class": f"bi bi-{icon}", "style": {"color": color, "fontSize": "1.4rem"}}),
                ),
                html.div(
                    html.p({"class": "text-muted mb-0", "style": {"fontSize": "0.8rem"}}, label),
                    html.h4({"class": "fw-bold mb-0"}, value),
                ),
            ),
        ),
    )


@component
def _category_row(category: str, amount: float, month_total: float):
    pct = int((amount / month_total * 100)) if month_total else 0
    return html.div(
        {"class": "mb-3"},
        html.div(
            {"class": "d-flex justify-content-between mb-1"},
            html.small({"class": "fw-semibold"}, category),
            html.small({"class": "text-muted"}, f"${amount:,.2f} ({pct}%)"),
        ),
        html.div(
            {"class": "progress", "style": {"height": "6px"}},
            html.div({
                "class": "progress-bar",
                "style": {"width": f"{pct}%", "backgroundColor": "#4f46e5"},
            }),
        ),
    )


@component
def _expense_row(expense: dict):
    cat_colors = {
        "Food & Dining": "#f59e0b", "Shopping": "#3b82f6", "Transportation": "#10b981",
        "Entertainment": "#8b5cf6", "Health & Medical": "#ef4444", "Travel": "#06b6d4",
        "Utilities": "#64748b", "Insurance": "#84cc16", "Other": "#94a3b8",
    }
    color = cat_colors.get(expense.get("category", "Other"), "#94a3b8")
    return html.div(
        {"class": "d-flex align-items-center py-2 border-bottom"},
        html.div(
            {
                "style": {
                    "width": "8px", "height": "8px", "borderRadius": "50%",
                    "backgroundColor": color, "flexShrink": "0", "marginRight": "12px",
                },
            },
        ),
        html.div(
            {"class": "flex-grow-1 me-3", "style": {"overflow": "hidden"}},
            html.p(
                {"class": "mb-0 fw-semibold text-truncate", "style": {"fontSize": "0.9rem"}},
                expense.get("description", "—"),
            ),
            html.small(
                {"class": "text-muted"},
                f"{expense.get('date', '')}  ·  {expense.get('category', 'Other')}  ·  {expense.get('user_email', '').split('@')[0]}",
            ),
        ),
        html.span({"class": "fw-semibold text-danger"}, f"${float(expense.get('amount', 0)):,.2f}"),
    )
