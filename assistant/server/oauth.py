"""Google OAuth2 sign-in over the web — connect from the iPhone.

GET /auth/google/start  → redirects to Google's consent screen
GET /auth/google/callback → exchanges the code, stores the refresh token

Requires a "Web application" OAuth client in Google Cloud Console with
redirect URI  {server}/auth/google/callback  (assistant/credentials.json
may contain either the web client or a desktop client for the CLI flow).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

from ..config import settings
from ..google_auth import SCOPES

logger = logging.getLogger(__name__)

router = APIRouter()


def _redirect_uri(request: Request) -> str:
    return str(request.url_for("google_oauth_callback"))


def _flow(request: Request) -> Flow:
    if not settings.google_credentials_path.exists():
        raise HTTPException(
            500,
            "assistant/credentials.json missing — create an OAuth client in "
            "Google Cloud Console (Web application, redirect URI "
            f"{_redirect_uri(request)}) and save the JSON there.",
        )
    return Flow.from_client_secrets_file(
        str(settings.google_credentials_path),
        scopes=SCOPES,
        redirect_uri=_redirect_uri(request),
    )


@router.get("/auth/google/start")
async def google_oauth_start(request: Request) -> RedirectResponse:
    flow = _flow(request)
    url, _state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    return RedirectResponse(url)


@router.get("/auth/google/callback", name="google_oauth_callback")
async def google_oauth_callback(request: Request) -> HTMLResponse:
    flow = _flow(request)
    try:
        flow.fetch_token(authorization_response=str(request.url))
    except Exception as exc:
        raise HTTPException(400, f"OAuth exchange failed: {exc}") from exc
    settings.google_token_path.write_text(flow.credentials.to_json())
    logger.info("Google account connected; token stored.")
    return HTMLResponse(
        "<html><body style='font-family:-apple-system;text-align:center;"
        "padding-top:40vh'><h2>✓ Google connected</h2>"
        "<p>You can close this tab and return to Hermes.</p></body></html>"
    )


@router.get("/integrations/status")
async def integrations_status() -> dict:
    """Connection status for the app's Settings screen."""
    google_connected = settings.google_token_path.exists()
    return {
        "google": {
            "connected": google_connected,
            "connect_url": "/auth/google/start" if not google_connected else None,
        },
        "apple_mail": {
            "connected": bool(settings.icloud_email and settings.icloud_app_password),
            "note": "Apple offers no OAuth for IMAP — set ICLOUD_EMAIL + "
                    "app-specific password in assistant/.env",
        },
        "whatsapp": {
            "connected": bool(settings.whatsapp_token and settings.whatsapp_phone_number_id)
        },
        "web_search": {"connected": bool(settings.tavily_api_key)},
        "youtube": {"connected": bool(settings.youtube_api_key)},
        "push": {
            "connected": bool(settings.apns_key_id and settings.apns_team_id
                              and settings.apns_key_path.exists())
        },
        "sandbox": {"provider": settings.sandbox_provider},
        "memory": {"mode": "mem0-hosted" if settings.mem0_api_key else "mem0-local-pgvector"},
    }
