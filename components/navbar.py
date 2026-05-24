"""
Navigation bar component.

Renders a Bootstrap 5 top navbar with nav links for each page.
The on_navigate callback updates the parent App component's page state,
which re-renders the correct page without a full browser reload.
"""
from reactpy import component, html


@component
def Navbar(user: dict, current_page: str, on_navigate):
    """
    Top navigation bar.

    ReactPy pattern: event-driven navigation via a callback prop.
    Clicking a nav link calls on_navigate(page_name), which updates state
    in the parent App component. ReactPy diffs and re-renders only what changed.

    Args:
        user:          Current user dict (email, name, picture, role).
        current_page:  Active page string used to highlight the active link.
        on_navigate:   Callable[str] — parent updates its page state.
    """

    def nav_link(page: str, label: str, icon: str):
        is_active = current_page == page
        return html.li(
            {"class": "nav-item"},
            html.button(
                {
                    "class": f"nav-link btn btn-link {'active fw-semibold' if is_active else 'text-white-50'}",
                    "style": {"textDecoration": "none", "color": "white" if is_active else ""},
                    "onClick": lambda _: on_navigate(page),
                },
                html.i({"class": f"bi bi-{icon} me-1"}),
                label,
            ),
        )

    return html.nav(
        {"class": "navbar navbar-expand-lg", "style": {"backgroundColor": "#4f46e5"}},
        html.div(
            {"class": "container-fluid px-4"},
            # Brand
            html.button(
                {
                    "class": "navbar-brand btn btn-link text-white fw-bold p-0",
                    "style": {"textDecoration": "none", "fontSize": "1.2rem"},
                    "onClick": lambda _: on_navigate("dashboard"),
                },
                html.i({"class": "bi bi-wallet2 me-2"}),
                "Expense Tracker",
            ),
            # Hamburger toggler (Bootstrap JS handles the collapse)
            html.button(
                {
                    "class": "navbar-toggler border-0",
                    "type": "button",
                    "data-bs-toggle": "collapse",
                    "data-bs-target": "#navbarNav",
                    "style": {"color": "white"},
                },
                html.span({"class": "navbar-toggler-icon"}),
            ),
            # Nav links
            html.div(
                {"class": "collapse navbar-collapse", "id": "navbarNav"},
                html.ul(
                    {"class": "navbar-nav me-auto"},
                    nav_link("dashboard", "Dashboard", "speedometer2"),
                    nav_link("expenses", "Expenses", "list-ul"),
                    nav_link("import", "Import Expenses", "upload"),
                ),
                # User avatar + logout
                html.div(
                    {"class": "d-flex align-items-center gap-3"},
                    html.span(
                        {"class": "text-white-50", "style": {"fontSize": "0.875rem"}},
                        user.get("name", user.get("email", "")),
                    ),
                    html.a(
                        {
                            "href": "/auth/logout",
                            "class": "btn btn-sm btn-outline-light",
                        },
                        html.i({"class": "bi bi-box-arrow-right me-1"}),
                        "Logout",
                    ),
                ),
            ),
        ),
    )
