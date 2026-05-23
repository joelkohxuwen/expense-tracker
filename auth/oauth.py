"""
Google OAuth 2.0 setup using Authlib's Starlette integration.

The oauth object is shared across the app. Register it once here and import
wherever you need to initiate the OAuth flow or exchange tokens.
"""
from authlib.integrations.starlette_client import OAuth
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

oauth = OAuth()

oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    # Google's OpenID Connect discovery document — Authlib reads endpoints from here
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        # prompt=select_account forces the account chooser even when already logged in,
        # which is useful for a shared family device
        "prompt": "select_account",
    },
)
