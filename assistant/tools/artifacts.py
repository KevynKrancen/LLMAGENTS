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
        """INSERT INTO hermes.artifacts (id, kind, title, content, version, thread_id, space)
           VALUES (%(id)s, %(kind)s, %(title)s, %(content)s, %(version)s, %(thread_id)s,
                   %(space)s)
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
    path: str = "",
    as_dashboard: bool = False,
) -> Command:
    """Create a live artifact that renders in the app's artifact canvas.

    Use for anything worth showing as a document rather than chat text:
    reports, analyses, dashboards, plans, generated mini-apps. The user
    watches it render live; update it with update_artifact.

    For specialized domains, set path to file it into a workspace folder
    and as_dashboard=true to make it that folder's FACE: it renders as a
    custom UI whenever the user opens the folder — this is how a domain
    (finance, budget, tutor…) gets its own specialized interface.

    Args:
        kind: 'html' (full self-contained HTML+CSS+JS), 'markdown',
            'table' (JSON {columns, rows}), or 'chart' (JSON
            {kind: line|bar|pie, series: [{name, points: [{x, y}]}]})
        title: Short artifact title shown in the app
        content: The artifact body in the format matching kind
        path: Optional workspace folder path, e.g. 'Finance/Polymarket'
            (missing folders are created)
        as_dashboard: Make this artifact the folder's opening view

    Returns:
        Confirmation with the artifact id (use it for updates)
    """
    if kind not in _KINDS:
        return f"Error: kind must be one of {sorted(_KINDS)}"  # type: ignore[return-value]
    node_id = ""
    if path:
        from .workspace import _ensure_path

        node_id = _ensure_path(path) or ""
    artifact = {
        "id": uuid.uuid4().hex[:10],
        "kind": kind,
        "title": title,
        "content": content,
        "version": 1,
        "thread_id": None,
        "space": node_id,
    }
    _persist(artifact)
    if as_dashboard and node_id:
        db.execute(
            "UPDATE hermes.nodes SET dashboard=%s WHERE id=%s", (artifact["id"], node_id)
        )
    return _command(
        artifact, tool_call_id,
        json.dumps({"created": True, "artifact_id": artifact["id"],
                    "dashboard_for": node_id if as_dashboard else None}),
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
        "space": existing.get("space", ""),
    }
    _persist(artifact)
    return _command(
        artifact, tool_call_id,
        json.dumps({"updated": True, "version": artifact["version"]}),
    )
