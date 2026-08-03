"""Live artifact tools.

Artifacts are documents the agent builds and edits while the user watches:
the artifact lives in graph state (streamed to the app as STATE_DELTA →
live-updating canvas) and is persisted to Postgres for the Artifacts tab.
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

from .. import db

_KINDS = {"html", "markdown", "table", "chart"}


def _persist(artifact: dict) -> None:
    db.execute(
        """INSERT INTO hermes.artifacts (id, kind, title, content, version, thread_id)
           VALUES (%(id)s, %(kind)s, %(title)s, %(content)s, %(version)s, %(thread_id)s)
           ON CONFLICT (id) DO UPDATE
           SET content = EXCLUDED.content, title = EXCLUDED.title,
               version = EXCLUDED.version, updated_at = now()""",
        artifact,
    )


def _command(artifact: dict, tool_call_id: str, note: str) -> Command:
    return Command(
        update={
            "artifact": artifact,
            "messages": [ToolMessage(content=note, tool_call_id=tool_call_id)],
        }
    )


@tool(parse_docstring=True)
def create_artifact(
    kind: str,
    title: str,
    content: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Create a live artifact that renders in the app's artifact canvas.

    Use for anything worth showing as a document rather than chat text:
    reports, analyses, dashboards, plans, generated mini-apps. The user
    watches it render live; update it with update_artifact.

    Args:
        kind: 'html' (full self-contained HTML+CSS+JS), 'markdown',
            'table' (JSON {columns, rows}), or 'chart' (JSON
            {kind: line|bar|pie, series: [{name, points: [{x, y}]}]})
        title: Short artifact title shown in the app
        content: The artifact body in the format matching kind

    Returns:
        Confirmation with the artifact id (use it for updates)
    """
    if kind not in _KINDS:
        return f"Error: kind must be one of {sorted(_KINDS)}"  # type: ignore[return-value]
    artifact = {
        "id": uuid.uuid4().hex[:10],
        "kind": kind,
        "title": title,
        "content": content,
        "version": 1,
        "thread_id": None,
    }
    _persist(artifact)
    return _command(
        artifact, tool_call_id,
        json.dumps({"created": True, "artifact_id": artifact["id"]}),
    )


@tool(parse_docstring=True)
def update_artifact(
    artifact_id: str,
    content: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    title: str = "",
) -> Command:
    """Update an existing artifact — the app canvas refreshes live.

    Args:
        artifact_id: Id returned by create_artifact
        content: Full replacement content (same format as its kind)
        title: Optional new title

    Returns:
        Confirmation with the new version number
    """
    rows = db.query("SELECT * FROM hermes.artifacts WHERE id=%s", (artifact_id,))
    if not rows:
        return f"Error: no artifact {artifact_id!r}"  # type: ignore[return-value]
    existing = rows[0]
    artifact = {
        "id": artifact_id,
        "kind": existing["kind"],
        "title": title or existing["title"],
        "content": content,
        "version": existing["version"] + 1,
        "thread_id": existing["thread_id"],
    }
    _persist(artifact)
    return _command(
        artifact, tool_call_id,
        json.dumps({"updated": True, "version": artifact["version"]}),
    )
