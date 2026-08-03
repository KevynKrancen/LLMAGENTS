"""Gmail tools — read, search, send, and reply via the Gmail API."""

from __future__ import annotations

import base64
import json
from email.mime.text import MIMEText

from langchain_core.tools import tool

from ..google_auth import gmail_service


def _header(payload: dict, name: str) -> str:
    return next(
        (h["value"] for h in payload.get("headers", []) if h["name"].lower() == name.lower()),
        "",
    )


def _extract_body(payload: dict) -> str:
    """Walk a Gmail payload tree and return the first text/plain part."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode(errors="replace")
    for part in payload.get("parts", []) or []:
        body = _extract_body(part)
        if body:
            return body
    return ""


@tool(parse_docstring=True)
def list_gmail_messages(query: str = "in:inbox", max_results: int = 10) -> str:
    """List recent Gmail messages matching a Gmail search query.

    Args:
        query: Gmail search syntax, e.g. 'in:inbox is:unread', 'from:boss@x.com',
            'newer_than:2d has:attachment'
        max_results: Number of messages to return (1-25)

    Returns:
        JSON list of {id, from, subject, date, snippet}
    """
    service = gmail_service()
    listing = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=min(max(max_results, 1), 25))
        .execute()
    )
    messages = []
    for ref in listing.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=ref["id"], format="metadata",
                 metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        payload = msg.get("payload", {})
        messages.append(
            {
                "id": msg["id"],
                "from": _header(payload, "From"),
                "subject": _header(payload, "Subject"),
                "date": _header(payload, "Date"),
                "snippet": msg.get("snippet", ""),
            }
        )
    return json.dumps(messages)


@tool(parse_docstring=True)
def read_gmail_message(message_id: str) -> str:
    """Read the full body of a single Gmail message by its id.

    Args:
        message_id: Gmail message id from list_gmail_messages

    Returns:
        JSON with {from, to, subject, date, body}
    """
    service = gmail_service()
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = msg.get("payload", {})
    return json.dumps(
        {
            "from": _header(payload, "From"),
            "to": _header(payload, "To"),
            "subject": _header(payload, "Subject"),
            "date": _header(payload, "Date"),
            "body": _extract_body(payload)[:8000],
        }
    )


def _send(raw_message: MIMEText, thread_id: str | None = None) -> str:
    service = gmail_service()
    body = {"raw": base64.urlsafe_b64encode(raw_message.as_bytes()).decode()}
    if thread_id:
        body["threadId"] = thread_id
    sent = service.users().messages().send(userId="me", body=body).execute()
    return json.dumps({"sent": True, "id": sent["id"]})


@tool(parse_docstring=True)
def send_gmail(to: str, subject: str, body: str) -> str:
    """Send a new email from the user's Gmail account.

    Always confirm recipient and content with the user before sending
    unless they explicitly asked you to send it.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Plain-text email body

    Returns:
        JSON {sent: true, id: <gmail message id>}
    """
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    return _send(message)


@tool(parse_docstring=True)
def draft_gmail_reply(message_id: str, body: str) -> str:
    """Reply to an existing Gmail message, keeping it in the same thread.

    Args:
        message_id: The id of the message being replied to
        body: Plain-text reply body

    Returns:
        JSON {sent: true, id: <gmail message id>}
    """
    service = gmail_service()
    original = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="metadata",
             metadataHeaders=["From", "Subject", "Message-ID"])
        .execute()
    )
    payload = original.get("payload", {})
    reply = MIMEText(body)
    reply["to"] = _header(payload, "From")
    subject = _header(payload, "Subject")
    reply["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    reply["In-Reply-To"] = _header(payload, "Message-ID")
    reply["References"] = _header(payload, "Message-ID")
    return _send(reply, thread_id=original.get("threadId"))
