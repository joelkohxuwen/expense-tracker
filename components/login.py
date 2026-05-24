"""
Login page component.

Shown to any visitor who is not authenticated. Clicking the button
performs a full-page redirect to /auth/login which starts the Google
OAuth 2.0 flow. After consent, Google redirects back to /auth/callback,
which sets the session cookie and sends the user to the main app.
"""
from reactpy import component, html
from reactpy.html import make_vdom_constructor

# SVG child elements not exposed directly on html.* in ReactPy 1.1 —
# create them with make_vdom_constructor (same factory used internally).
_path = make_vdom_constructor("path")


@component
def LoginPage(error: str = ""):
    """
    Full-page login screen with a "Sign in with Google" button.

    ReactPy pattern: a pure display component — no state, no effects.
    It renders HTML elements using the html.* helpers which map directly
    to DOM elements (html.div → <div>, html.button → <button>, etc.).
    """
    return html.div(
        {"style": {
            "minHeight": "100vh",
            "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
        }},
        html.div(
            {"class": "card shadow-lg", "style": {"width": "380px", "borderRadius": "16px"}},
            html.div(
                {"class": "card-body p-5 text-center"},
                # App icon / logo
                html.div(
                    {"class": "mb-4"},
                    html.i({"class": "bi bi-wallet2", "style": {"fontSize": "3.5rem", "color": "#667eea"}}),
                ),
                html.h2({"class": "fw-bold mb-1"}, "Family Expense Tracker"),
                html.p(
                    {"class": "text-muted mb-4"},
                    "Track shared expenses with your family",
                ),
                # Error banner (shown if OAuth failed)
                html.div(
                    {"class": "alert alert-danger py-2 mb-3", "style": {"display": "block" if error else "none"}},
                    html.i({"class": "bi bi-exclamation-triangle me-2"}),
                    f"Sign-in failed: {error}" if error else "",
                ),
                # Google sign-in button — href triggers full-page navigation
                html.a(
                    {
                        "href": "/auth/login",
                        "class": "btn btn-lg w-100 d-flex align-items-center justify-content-center gap-2",
                        "style": {
                            "backgroundColor": "#4285F4",
                            "color": "white",
                            "border": "none",
                            "borderRadius": "8px",
                            "padding": "12px",
                            "textDecoration": "none",
                        },
                    },
                    # Google G logo via make_vdom_constructor (html.path not
                    # exposed in ReactPy 1.1 — use _path created at module level)
                    html.svg(
                        {
                            "width": "20", "height": "20", "viewBox": "0 0 48 48",
                            "style": {"flexShrink": "0"},
                        },
                        _path({
                            "fill": "#FFC107",
                            "d": "M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z",
                        }),
                        _path({
                            "fill": "#FF3D00",
                            "d": "M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z",
                        }),
                        _path({
                            "fill": "#4CAF50",
                            "d": "M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z",
                        }),
                        _path({
                            "fill": "#1976D2",
                            "d": "M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571l6.19 5.238C42.021 35.596 44 30.138 44 24c0-1.341-.138-2.65-.389-3.917z",
                        }),
                    ),
                    "Sign in with Google",
                ),
                html.p(
                    {"class": "text-muted mt-4 mb-0", "style": {"fontSize": "0.8rem"}},
                    "Only invited family members can access this app.",
                ),
            ),
        ),
    )
