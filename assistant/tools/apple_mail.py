"""Apple Mail (iCloud) tools — IMAP read + SMTP send with an app-specific password.

Generate the app-specific password at appleid.apple.com → Sign-In & Security.
"""

from __future__ import annotations

import email
import email.utils
import imaplib
import json
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText

from langchain_core.tools import tool

from ..config import settings

_IMAP_HOST = "imap.mail.me.com"
_SMTP_HOST = "smtp.mail.me.com"
_SMTP_PORT = 587


def _require_credentials() -> None:
    if not settings.icloud_email or not settings.icloud_app_password:
        raise ValueError(
            "iCloud mail is not configured. Set ICLOUD_EMAIL and "
            "ICLOUD_APP_PASSWORD (an app-specific password) in assistant/.env."
        )


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    return "".join(
        chunk.decode(enc or "utf-8", errors="replace") if isinstance(chunk, bytes) else chunk
        for chunk, enc in parts
    )


@tool(parse_docstring=True, handle_tool_error=True)
def list_apple_mail_messages(max_results: int = 10, unread_only: bool = False) -> str:
    """List recent messages from the user's iCloud (Apple Mail) inbox.

    Args:
        max_results: Number of most recent messages to return (1-25)
        unread_only: If true, only return unread messages

    Returns:
        JSON list of {uid, from, subject, date, preview}
    """
    _require_credentials()
    with imaplib.IMAP4_SSL(_IMAP_HOST) as imap:
        imap.login(settings.icloud_email, settings.icloud_app_password)
        imap.select("INBOX", readonly=True)
        _, data = imap.uid("search", None, "UNSEEN" if unread_only else "ALL")
        uids = data[0].split()[-min(max(max_results, 1), 25):]

        messages = []
        for uid in reversed(uids):
            _, msg_data = imap.uid("fetch", uid, "(BODY.PEEK[])")
            msg = email.message_from_bytes(msg_data[0][1])
            body = ""
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(errors="replace")
                        break
            messages.append(
                {
                    "uid": uid.decode(),
                    "from": _decode(msg.get("From")),
                    "subject": _decode(msg.get("Subject")),
                    "date": msg.get("Date", ""),
                    "preview": " ".join(body.split())[:300],
                }
            )
    return json.dumps(messages)


@tool(parse_docstring=True, handle_tool_error=True)
def send_apple_mail(to: str, subject: str, body: str) -> str:
    """Send an email from the user's iCloud (Apple Mail) address.

    Always confirm recipient and content with the user before sending
    unless they explicitly asked you to send it.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Plain-text email body

    Returns:
        JSON {sent: true}
    """
    _require_credentials()
    message = MIMEText(body)
    message["From"] = settings.icloud_email
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = email.utils.formatdate(localtime=True)
    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(settings.icloud_email, settings.icloud_app_password)
        smtp.send_message(message)
    return json.dumps({"sent": True})
