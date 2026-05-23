"""
Root ReactPy component — the entry point mounted by FastAPI.

This component does three things:
  1. Reads the session cookie from the WebSocket ASGI scope to get the
     current user (or None if not logged in).
  2. Reads URL query params from the same scope to handle the initial page
     and any import_id produced by the CSV upload redirect.
  3. Renders either the login page or the main layout (navbar + page content)
     depending on authentication state.

ReactPy architecture note:
  ReactPy renders components on the *server*. The browser connects via
  WebSocket and receives HTML patches. This means:
    - Components can call Python functions and databases directly.
    - The ASGI scope (cookies, query params, headers) is readable via
      use_connection().scope from the reactpy.backend.hooks module.
    - Routing is state-based (no URL changes on navigation) because the
      WebSocket session persists for the lifetime of the browser tab.
"""
from reactpy import component, html, hooks
from reactpy.backend.hooks import use_connection

from auth.session import get_user_from_scope
from components.login import LoginPage
from components.navbar import Navbar
from components.dashboard import Dashboard
from components.expenses import ExpensesPage
from components.import_page import ImportPage


def _parse_query_params(scope: dict) -> dict:
    """Extract URL query parameters from the ASGI WebSocket scope."""
    qs = scope.get("query_string", b"").decode("utf-8", errors="ignore")
    params: dict[str, str] = {}
    if qs:
        for part in qs.split("&"):
            if "=" in part:
                key, _, val = part.partition("=")
                params[key.strip()] = val.strip()
    return params


@component
def App():
    """
    Root component — mounted once per browser tab.

    State:
      page       — which page is currently rendered ("dashboard" | "expenses" | "import")
      import_id  — UUID from the CSV upload redirect (cleared after the import step)
    """
    # Read auth + routing info from the initial WebSocket handshake headers
    connection = use_connection()
    scope = connection.scope
    user = get_user_from_scope(scope)
    params = _parse_query_params(scope)

    # Initialise page from URL params so a CSV upload redirect lands on the
    # review step immediately. Use state so subsequent in-app navigation works.
    page, set_page = hooks.use_state(params.get("page", "dashboard"))
    import_id, set_import_id = hooks.use_state(params.get("import_id", ""))

    def navigate(target_page: str):
        """Navigate to a page. Clears import_id when leaving the import page."""
        if target_page != "import":
            set_import_id("")
        set_page(target_page)

    # Shared CDN assets injected once at the root so all child components can
    # use Bootstrap classes and Bootstrap Icons without repeating these tags.
    cdn_assets = [
        html.link({
            "rel": "stylesheet",
            "href": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css",
        }),
        html.link({
            "rel": "stylesheet",
            "href": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        }),
        html.meta({"name": "viewport", "content": "width=device-width, initial-scale=1"}),
    ]

    # ---- Not authenticated: show full-page login screen --------------------
    if not user:
        error = params.get("error", "")
        return html.div(
            *cdn_assets,
            LoginPage(error=error),
        )

    # ---- Authenticated: pick the active page component ---------------------
    def page_content():
        if page == "expenses":
            return ExpensesPage(user=user, on_navigate=navigate)
        if page == "import":
            return ImportPage(user=user, import_id=import_id, on_navigate=navigate)
        # Default: dashboard
        return Dashboard(user=user, on_navigate=navigate)

    return html.div(
        *cdn_assets,
        # Global style override — remove the default body margin
        html.style("body { background-color: #f8f9fa; }"),
        Navbar(user=user, current_page=page, on_navigate=navigate),
        html.div(
            {"class": "container-xl py-4 px-3 px-md-4"},
            page_content(),
        ),
        # Bootstrap JS bundle (needed for navbar collapse on mobile)
        html.script({
            "src": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js",
            "defer": True,
        }),
    )
