"""
Dashboard page component.

Shows a monthly stacked bar chart, summary cards, category breakdown,
and the 10 most recent expenses. Includes a quick-add expense form.

ReactPy pattern: use_effect for async data loading.
The component renders a loading state first, then use_effect fires after
mount to fetch real data from Google Sheets and trigger a re-render.
"""
import hashlib
import json
from collections import defaultdict
from datetime import datetime

from reactpy import component, html, hooks

from database.sheets import get_expenses, get_categories, get_all_users, add_expense
from components.expense_form import ExpenseForm


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _currency(amount) -> str:
    try:
        return f"${float(amount):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _month_label(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%B %Y")


def _display_name(email: str, users: list) -> str:
    """Return the first name for a user email, falling back to email prefix."""
    for u in users:
        if u.get("email") == email:
            n = u.get("name", "").strip()
            if n:
                return n.split()[0]
            break
    return email.split("@")[0].capitalize()


# ---------------------------------------------------------------------------
# Monthly chart helpers
# ---------------------------------------------------------------------------

_CAT_COLORS: dict[str, tuple[int, int, int]] = {
    "food":          (245, 158,  11),
    "groceries":     (249, 115,  22),
    "transport":     ( 16, 185, 129),
    "shopping":      ( 59, 130, 246),
    "clothing":      ( 14, 165, 233),
    "entertainment": (139,  92, 246),
    "leisure":       (124,  58, 237),
    "travel":        (  6, 182, 212),
    "health":        (239,  68,  68),
    "home":          (167, 139, 250),
    "utilities":     (100, 116, 139),
    "insurance":     (132, 204,  22),
    "personal":      (217,  70, 239),
    "gifts":         (236,  72, 153),
    "gambling":      (107, 114, 128),
    "banking":       (  3, 105, 161),
    "education":     ( 21, 128,  61),
}


def _cat_rgba(cat: str, alpha: float) -> str:
    cat_l = cat.lower()
    for k, (r, g, b) in _CAT_COLORS.items():
        if k in cat_l:
            return f"rgba({r},{g},{b},{alpha})"
    return f"rgba(148,163,184,{alpha})"


def _last_6_months() -> list[str]:
    """Return list of YYYY-MM strings for the last 6 months, oldest first."""
    now = datetime.now()
    result = []
    m, y = now.month, now.year
    for _ in range(6):
        result.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(result))


# ---------------------------------------------------------------------------
# MonthlyChart component
# ---------------------------------------------------------------------------

@component
def MonthlyChart(expenses: list, users: list):
    """
    Grouped + stacked bar chart using Chart.js (loaded via CDN in app.py).

    Each month has one bar per person (side-by-side), and each person's bar
    is stacked by category. Colours are category-driven; opacity varies by
    person so the two groups are visually distinct.
    """
    if not expenses:
        return html.div(
            {"class": "card border-0 shadow-sm mb-4"},
            html.div(
                {"class": "card-body text-center text-muted py-4"},
                html.i({"class": "bi bi-bar-chart me-2"}),
                "No expense data yet.",
            ),
        )

    # email → first name
    name_map: dict[str, str] = {}
    for u in (users or []):
        em = u.get("email", "")
        n = u.get("name", "").strip()
        name_map[em] = n.split()[0] if n else em.split("@")[0].capitalize()

    months_ym = _last_6_months()
    month_labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months_ym]
    months_set = set(months_ym)

    # Aggregate: email → ym → category → total
    agg: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for e in expenses:
        d = e.get("date", "")
        if len(d) < 7 or d[:7] not in months_set:
            continue
        em = e.get("user_email", "unknown")
        cat = e.get("category", "Other")
        try:
            agg[em][d[:7]][cat] += float(e.get("amount", 0))
        except (ValueError, TypeError):
            pass

    emails = sorted(agg.keys())
    alphas = [0.85, 0.65, 0.50, 0.40]  # opacity per person index

    datasets = []
    for pi, em in enumerate(emails):
        alpha = alphas[min(pi, len(alphas) - 1)]
        stack_name = name_map.get(em, em.split("@")[0].capitalize())
        all_cats = sorted({c for ym_d in agg[em].values() for c in ym_d})
        for cat in all_cats:
            data_vals = [round(agg[em][ym].get(cat, 0.0), 2) for ym in months_ym]
            if all(v == 0.0 for v in data_vals):
                continue
            datasets.append({
                "label":           f"{stack_name} — {cat}",
                "stack":           stack_name,
                "data":            data_vals,
                "backgroundColor": _cat_rgba(cat, alpha),
                "borderWidth":     0,
            })

    if not datasets:
        return html.div()

    data_json = json.dumps({"labels": month_labels, "datasets": datasets})
    chart_id = "mc-" + hashlib.md5(data_json.encode()).hexdigest()[:8]

    # Inline JS — options written as real JS (not JSON) so we can use
    # function callbacks for tooltip/tick formatting.
    script = (
        "(function(){"
        "var _t=0;"
        "function _i(){"
        f"var el=document.getElementById('{chart_id}');"
        "if(!el||!window.Chart){if(_t++<60){setTimeout(_i,100);}return;}"
        "if(el._ci){el._ci.destroy();}"
        "el._ci=new Chart(el,{"
        "type:'bar',"
        f"data:{data_json},"
        "options:{"
        "responsive:true,maintainAspectRatio:false,"
        "plugins:{"
        "legend:{position:'bottom',labels:{boxWidth:10,font:{size:10},padding:8}},"
        "tooltip:{callbacks:{label:function(c){return ' '+c.dataset.label+': $'+c.raw.toFixed(2);}}}"
        "},"
        "scales:{"
        "x:{stacked:true,grid:{display:false}},"
        "y:{stacked:true,beginAtZero:true,ticks:{callback:function(v){return '$'+v.toLocaleString();}}}"
        "}"
        "}"
        "});"
        "}"
        "_i();"
        "})();"
    )

    return html.div(
        {"class": "card border-0 shadow-sm mb-4"},
        html.div(
            {"class": "card-body"},
            html.h5(
                {"class": "card-title mb-3"},
                html.i({"class": "bi bi-bar-chart-line me-2 text-primary"}),
                "Monthly Spending Overview",
            ),
            html.div(
                {"style": {"position": "relative", "height": "300px"}},
                html.canvas({"id": chart_id}),
            ),
            html.script(script),
        ),
    )


# ---------------------------------------------------------------------------
# Dashboard component
# ---------------------------------------------------------------------------

@component
def Dashboard(user: dict, on_navigate):
    """
    Main landing page after login.

    State variables:
      expenses    — full list fetched from Sheets (None = not yet loaded)
      categories  — list of category strings for the quick-add form
      users       — all registered users (for display names in chart/table)
      show_form   — toggle the quick-add expense card
      loading     — True while the initial Sheets fetch is in flight
    """
    expenses,   set_expenses   = hooks.use_state(None)
    categories, set_categories = hooks.use_state([])
    users,      set_users      = hooks.use_state([])
    show_form,  set_show_form  = hooks.use_state(False)
    loading,    set_loading    = hooks.use_state(True)
    sheets_error, set_sheets_error = hooks.use_state("")
    refresh_key, set_refresh_key   = hooks.use_state(0)

    @hooks.use_effect(dependencies=[refresh_key])
    async def load_data():
        set_loading(True)
        set_sheets_error("")
        try:
            all_exp  = await get_expenses(user_email=None)
            cats     = await get_categories()
            user_list = await get_all_users()
            set_expenses(all_exp)
            set_categories(cats)
            set_users(user_list)
        except Exception as exc:
            set_sheets_error(str(exc))
            set_expenses([])
            set_categories([])
            set_users([])
        set_loading(False)

    async def handle_save(expense: dict):
        await add_expense(expense)
        set_show_form(False)
        set_refresh_key(refresh_key + 1)

    # ---- Derived stats -------------------------------------------------------
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

    cat_totals: dict[str, float] = {}
    for e in this_month_expenses:
        cat = e.get("category", "Other")
        try:
            cat_totals[cat] = cat_totals.get(cat, 0.0) + float(e.get("amount", 0))
        except (TypeError, ValueError):
            pass
    cat_sorted = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)

    recent = (expenses or [])[:10]

    # ---- Render --------------------------------------------------------------
    return html.div(
        # Sheets error banner
        html.div(
            {
                "class": "alert alert-danger d-flex align-items-start gap-3 mb-4",
                "style": {"display": "none" if not sheets_error else "flex"},
            },
            html.i({"class": "bi bi-exclamation-triangle-fill flex-shrink-0 mt-1"}),
            html.div(
                html.strong("Google Sheets not accessible. "),
                "Share your ",
                html.strong("\"Expense Logs\""),
                " spreadsheet with the service account email and reload.",
                html.br(),
                html.code(
                    {"style": {"fontSize": "0.8rem", "wordBreak": "break-all"}},
                    "expense-tracker-sheets@claude-code-497312.iam.gserviceaccount.com",
                ),
                html.br(),
                html.small({"class": "text-muted"}, sheets_error),
            ),
        ) if sheets_error else html.div(),

        # Header row
        html.div(
            {"class": "d-flex justify-content-between align-items-center mb-4"},
            html.div(
                html.h3(
                    {"class": "mb-0 fw-bold"},
                    f"Hello, {user.get('name', '').split()[0] or 'there'} \U0001f44b",
                ),
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
            _stat_card("This Month",   _currency(month_total),      "calendar-month",  "#4f46e5"),
            _stat_card("This Year",    _currency(this_year_total),  "graph-up-arrow",  "#059669"),
            _stat_card("Transactions", str(len(this_month_expenses)), "receipt",        "#d97706"),
            _stat_card("Categories",   str(len(cat_totals)),         "tags",            "#7c3aed"),
        ),

        # Loading spinner
        html.div(
            {"class": "text-center py-5", "style": {"display": "block" if loading else "none"}},
            html.div({"class": "spinner-border text-primary"}),
            html.p({"class": "text-muted mt-2"}, "Loading expenses…"),
        ),

        # Main content (hidden while loading)
        html.div(
            {"style": {"display": "none" if loading else "block"}},

            # Monthly chart (full width)
            MonthlyChart(expenses=(expenses or []), users=users),

            # Category breakdown + recent transactions
            html.div(
                {"class": "row g-4"},
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
                            ) if cat_sorted else html.p(
                                {"class": "text-muted"},
                                "No expenses this month yet.",
                            ),
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
                                    {
                                        "class": "btn btn-sm btn-outline-primary",
                                        "onClick": lambda _: on_navigate("expenses"),
                                    },
                                    "View All",
                                ),
                            ),
                            html.div(
                                *[_expense_row(e, users=users) for e in recent]
                            ) if recent else html.p(
                                {"class": "text-muted"},
                                "No expenses yet. Add one above!",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Sub-components
# ---------------------------------------------------------------------------

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
                            "backgroundColor": color + "20",
                            "display": "flex", "alignItems": "center",
                            "justifyContent": "center", "flexShrink": "0",
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
def _expense_row(expense: dict, users: list = None):
    cat_colors = {
        "Food & Dining": "#f59e0b", "Shopping": "#3b82f6", "Transportation": "#10b981",
        "Entertainment": "#8b5cf6", "Health & Medical": "#ef4444", "Travel": "#06b6d4",
        "Utilities": "#64748b",     "Insurance": "#84cc16", "Other": "#94a3b8",
    }
    color = cat_colors.get(expense.get("category", "Other"), "#94a3b8")
    name = _display_name(expense.get("user_email", ""), users or [])

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
                f"{expense.get('date', '')}  ·  {expense.get('category', 'Other')}  ·  {name}",
            ),
        ),
        html.span(
            {"class": "fw-semibold text-danger"},
            f"${float(expense.get('amount', 0)):,.2f}",
        ),
    )
