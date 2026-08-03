"""Workspace — an agent-shaped tree, no preset structure.

The app renders whatever tree exists here: folders inside folders at any
depth, holding notes and artifacts. Everything is created, moved, renamed,
and deleted by conversation. Paths are the interaction primitive:
'Travel/Japan/Food' materializes every missing folder along the way.
"""

from __future__ import annotations

import json
import re
import uuid

from langchain_core.tools import tool

from .. import db


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32]
    return base or uuid.uuid4().hex[:8]


def _ensure_path(path: str, icon: str = "◇") -> str | None:
    """Create every missing folder along a path; return the leaf node id."""
    parent_id: str | None = None
    for part in [p.strip() for p in path.split("/") if p.strip()]:
        rows = db.query(
            "SELECT id FROM hermes.nodes WHERE name ILIKE %s AND parent_id IS NOT DISTINCT FROM %s",
            (part, parent_id),
        )
        if rows:
            parent_id = rows[0]["id"]
            continue
        node_id = f"{_slug(part)}-{uuid.uuid4().hex[:4]}"
        db.execute(
            "INSERT INTO hermes.nodes (id, parent_id, name, icon) VALUES (%s,%s,%s,%s)",
            (node_id, parent_id, part, icon[:4]),
        )
        parent_id = node_id
    return parent_id


def _tree(parent_id: str | None = None) -> list[dict]:
    rows = db.query(
        """SELECT n.id, n.name, n.icon, n.dashboard,
                  (SELECT count(*) FROM hermes.artifacts a WHERE a.space = n.id) AS items
           FROM hermes.nodes n
           WHERE n.parent_id IS NOT DISTINCT FROM %s
           ORDER BY n.created_at""",
        (parent_id,),
    )
    return [
        {**row, "children": _tree(row["id"])}
        for row in rows
    ]


@tool(parse_docstring=True)
def shape_workspace(operations: str) -> str:
    """Reshape the user's workspace tree — create/rename/move/delete folders.

    The workspace is a tree of folders at any depth, shown in the app's ＋
    menu. It starts EMPTY; only shape it when the user asks ('make me a
    recipes folder', 'put Japan inside Travel', 'rename X to Y').

    Args:
        operations: JSON array of operations, each one of:
            {"op":"create","path":"Travel/Japan","icon":"🗾"}
            {"op":"rename","path":"Travel/Japan","name":"Nippon"}
            {"op":"move","path":"Recipes","into":"Kitchen"}
            {"op":"delete","path":"Old stuff"}

    Returns:
        JSON of the resulting workspace tree
    """
    try:
        ops = json.loads(operations)
    except json.JSONDecodeError as exc:
        return f"Error: operations must be valid JSON — {exc}"
    if isinstance(ops, dict):
        ops = [ops]

    for op in ops:
        kind = op.get("op")
        path = str(op.get("path", ""))
        if kind == "create":
            _ensure_path(path, op.get("icon", "◇"))
        elif kind in {"rename", "move", "delete"}:
            node_id = _find_by_path(path)
            if node_id is None:
                return f"Error: no folder at path {path!r}. Current tree: {json.dumps(_tree())}"
            if kind == "rename":
                db.execute(
                    "UPDATE hermes.nodes SET name=%s, icon=COALESCE(NULLIF(%s,''), icon) WHERE id=%s",
                    (op.get("name", path.split("/")[-1]), op.get("icon", ""), node_id),
                )
            elif kind == "move":
                target = _ensure_path(str(op.get("into", "")))
                db.execute("UPDATE hermes.nodes SET parent_id=%s WHERE id=%s", (target, node_id))
            else:
                db.execute("DELETE FROM hermes.nodes WHERE id=%s", (node_id,))
        else:
            return f"Error: unknown op {kind!r}"
    return json.dumps(_tree())


def _find_by_path(path: str) -> str | None:
    parent_id: str | None = None
    node_id: str | None = None
    for part in [p.strip() for p in path.split("/") if p.strip()]:
        rows = db.query(
            "SELECT id FROM hermes.nodes WHERE name ILIKE %s AND parent_id IS NOT DISTINCT FROM %s",
            (part, parent_id),
        )
        if not rows:
            return None
        node_id = rows[0]["id"]
        parent_id = node_id
    return node_id


@tool(parse_docstring=True)
def view_workspace() -> str:
    """See the user's current workspace tree with item counts.

    Returns:
        JSON tree of {id, name, icon, items, children}
    """
    return json.dumps(_tree())


@tool(parse_docstring=True)
def save_note(title: str, content: str, path: str = "") -> str:
    """Save a note (markdown) into the workspace, creating folders as needed.

    Use for anything the user wants kept: ideas, lists, recipes, plans.
    'path' places it anywhere in the tree — 'Travel/Japan' creates both
    folders if missing. Empty path saves at the workspace root.

    Args:
        title: Note title
        content: Markdown body
        path: Folder path like 'Recipes' or 'Travel/Japan/Food' (optional)

    Returns:
        JSON {saved: true, id, path}
    """
    node_id = _ensure_path(path) if path else None
    note_id = uuid.uuid4().hex[:10]
    db.execute(
        """INSERT INTO hermes.artifacts (id, kind, title, content, version, space)
           VALUES (%s, 'markdown', %s, %s, 1, %s)""",
        (note_id, title, content, node_id or ""),
    )
    return json.dumps({"saved": True, "id": note_id, "path": path or "(root)"})


WORKSPACE_TOOLS = [shape_workspace, view_workspace, save_note]
