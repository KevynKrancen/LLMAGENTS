"""Action receipts — the agent's auditable, reversible action ledger.

Every consequential tool call becomes a receipt: what was done, how
reversible it is, and (when possible) an undo descriptor the server can
execute later. This is the trust surface: the user can always see what
their agent did and unwind what can be unwound.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain.agents.middleware import AgentMiddleware

from .. import db

logger = logging.getLogger(__name__)

# tool -> (reversibility, summary template keys)
_CONSEQUENTIAL: dict[str, str] = {
    "send_gmail": "none",
    "draft_gmail_reply": "none",
    "send_apple_mail": "none",
    "send_whatsapp_message": "none",
    "create_calendar_event": "full",
    "delete_calendar_event": "none",
    "create_routine": "full",
    "delete_routine": "none",
    "pause_or_resume_routine": "full",
    "save_note": "full",
    "create_artifact": "full",
    "shape_workspace": "partial",
    "install_mcp_connector": "full",
    "install_api_connector": "full",
    "play_youtube_video": "none",
    "play_youtube_search": "none",
    "run_iphone_shortcut": "none",
    "create_iphone_reminder": "partial",
    "manage_memory_file": "partial",
}

_SUMMARY_KEYS = ("title", "summary", "subject", "name", "to", "query", "fact", "path")


def _summarize(tool: str, args: dict) -> str:
    detail = next((str(args[k])[:80] for k in _SUMMARY_KEYS if args.get(k)), "")
    verb = tool.replace("_", " ")
    return f"{verb}{': ' + detail if detail else ''}"


def _undo_descriptor(tool: str, args: dict, result_text: str) -> dict | None:
    """Best-effort undo instructions, derived from the tool result."""
    try:
        result = json.loads(result_text) if result_text.startswith("{") else {}
    except json.JSONDecodeError:
        result = {}
    if tool == "create_calendar_event" and result.get("id"):
        return {"kind": "delete_calendar_event", "args": {"event_id": result["id"]}}
    if tool == "create_routine" and result.get("id"):
        return {"kind": "delete_routine", "args": {"routine_id": result["id"]}}
    if tool == "pause_or_resume_routine" and result.get("id"):
        return {"kind": "toggle_routine",
                "args": {"routine_id": result["id"], "enabled": not result.get("enabled", True)}}
    if tool in {"save_note", "create_artifact"} and (result.get("id") or result.get("artifact_id")):
        return {"kind": "delete_artifact",
                "args": {"artifact_id": result.get("id") or result.get("artifact_id")}}
    if tool in {"install_mcp_connector", "install_api_connector"} and result.get("id"):
        return {"kind": "remove_connector", "args": {"integration_id": result["id"]}}
    return None


def record_receipt(tool: str, args: dict, result_text: str, source: str) -> None:
    reversibility = _CONSEQUENTIAL.get(tool)
    if reversibility is None:
        return
    if "Error" in result_text[:60] or '"error"' in result_text[:120]:
        return  # failed calls leave no receipt
    undo = _undo_descriptor(tool, args, result_text) if reversibility != "none" else None
    db.execute(
        "INSERT INTO hermes.receipts (id, tool, summary, reversibility, undo, source) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (uuid.uuid4().hex[:12], tool, _summarize(tool, args),
         reversibility if undo or reversibility == "none" else "partial",
         json.dumps(undo) if undo else None, source),
    )


def execute_undo(receipt_id: str) -> str:
    """Run a receipt's undo descriptor. Returns a human-readable outcome."""
    rows = db.query("SELECT * FROM hermes.receipts WHERE id=%s AND NOT undone", (receipt_id,))
    if not rows or not rows[0]["undo"]:
        return "Nothing to undo."
    undo = rows[0]["undo"] if isinstance(rows[0]["undo"], dict) else json.loads(rows[0]["undo"])
    kind, args = undo.get("kind"), undo.get("args", {})

    if kind == "delete_calendar_event":
        from ..google_auth import calendar_service

        calendar_service().events().delete(
            calendarId="primary", eventId=args["event_id"]
        ).execute()
    elif kind == "delete_routine":
        from ..routines import routine_manager

        routine_manager.delete(args["routine_id"])
    elif kind == "toggle_routine":
        from ..routines import routine_manager

        routine_manager.set_enabled(args["routine_id"], args["enabled"])
    elif kind == "delete_artifact":
        db.execute("DELETE FROM hermes.artifacts WHERE id=%s", (args["artifact_id"],))
    elif kind == "remove_connector":
        from ..integrations import integration_registry

        integration_registry.remove(args["integration_id"])
    else:
        return f"Unknown undo kind {kind!r}."

    db.execute("UPDATE hermes.receipts SET undone=TRUE WHERE id=%s", (receipt_id,))
    return "Undone."


class ReceiptMiddleware(AgentMiddleware):
    """Records a receipt after every consequential tool execution."""

    name = "receipts"

    def __init__(self, source: str = "chat") -> None:
        super().__init__()
        self._source = source

    async def awrap_tool_call(self, request, handler):
        response = await handler(request)
        try:
            tool_call: dict[str, Any] = dict(request.tool_call or {})
            tool_name = str(tool_call.get("name", ""))
            tool_args = dict(tool_call.get("args") or {})
            # Response is a ToolMessage, or a Command whose update carries one.
            message = response
            if hasattr(response, "update"):
                messages = (getattr(response, "update", {}) or {}).get("messages", [])
                message = messages[-1] if messages else None
            content = getattr(message, "content", "") if message else ""
            if isinstance(content, list):
                content = " ".join(str(part) for part in content)
            if tool_name:
                record_receipt(tool_name, tool_args, str(content), self._source)
        except Exception as exc:  # receipts must never break tool execution
            logger.warning("receipt capture failed: %s", exc)
        return response
