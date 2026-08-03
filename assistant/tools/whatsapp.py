"""WhatsApp tools — send messages via the Meta WhatsApp Cloud API.

Requires a Meta developer app with the WhatsApp product enabled:
https://developers.facebook.com/docs/whatsapp/cloud-api
Note: free-form messages can only be sent inside a 24h window after the
recipient last messaged you; outside it you must use an approved template.
"""

from __future__ import annotations

import json

import httpx
from langchain_core.tools import tool

from ..config import settings

_GRAPH_URL = "https://graph.facebook.com/v23.0"


def _post(payload: dict) -> str:
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        return json.dumps(
            {"error": "WhatsApp is not configured. Set WHATSAPP_TOKEN and "
                      "WHATSAPP_PHONE_NUMBER_ID in assistant/.env."}
        )
    response = httpx.post(
        f"{_GRAPH_URL}/{settings.whatsapp_phone_number_id}/messages",
        headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
        json={"messaging_product": "whatsapp", **payload},
        timeout=30,
    )
    response.raise_for_status()
    return json.dumps({"sent": True, "response": response.json()})


@tool(parse_docstring=True)
def send_whatsapp_message(to_phone: str, text: str) -> str:
    """Send a free-form WhatsApp text message to a phone number.

    Only works within 24h of the recipient's last message to this number;
    otherwise use send_whatsapp_template. Always confirm with the user
    before messaging someone on their behalf.

    Args:
        to_phone: Recipient phone in international format without '+', e.g. '972501234567'
        text: Message text to send

    Returns:
        JSON {sent: true, response} or an error explanation
    """
    return _post({"to": to_phone, "type": "text", "text": {"body": text}})


@tool(parse_docstring=True)
def send_whatsapp_template(to_phone: str, template_name: str, language_code: str = "en_US") -> str:
    """Send an approved WhatsApp template message (works outside the 24h window).

    Args:
        to_phone: Recipient phone in international format without '+', e.g. '972501234567'
        template_name: Name of a template approved in Meta Business Manager
        language_code: Template language code, e.g. 'en_US' or 'fr'

    Returns:
        JSON {sent: true, response} or an error explanation
    """
    return _post(
        {
            "to": to_phone,
            "type": "template",
            "template": {"name": template_name, "language": {"code": language_code}},
        }
    )
