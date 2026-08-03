"""Shared Google OAuth for Gmail + Google Calendar.

Run ``python -m assistant.google_auth`` once on your machine to complete the
browser OAuth flow; the refresh token is cached in ``assistant/data/``.
"""

from __future__ import annotations

import threading

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]

_lock = threading.Lock()
_credentials: Credentials | None = None


def get_credentials() -> Credentials:
    """Return cached Google credentials, refreshing or running OAuth as needed."""
    global _credentials
    with _lock:
        if _credentials and _credentials.valid:
            return _credentials

        creds: Credentials | None = None
        if settings.google_token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(settings.google_token_path), SCOPES
            )
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            if not settings.google_credentials_path.exists():
                raise FileNotFoundError(
                    f"Google OAuth client file missing: {settings.google_credentials_path}. "
                    "Download it from Google Cloud Console (OAuth client ID, Desktop app)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(settings.google_credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        settings.google_token_path.write_text(creds.to_json())
        _credentials = creds
        return creds


def gmail_service():
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)


def calendar_service():
    return build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)


if __name__ == "__main__":
    get_credentials()
    print(f"Google credentials saved to {settings.google_token_path}")
