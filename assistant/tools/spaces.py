"""Spaces — dynamic categories the user creates by talking to Hermes.

A space is a living collection surfaced in the app's ＋ sheet (Notes is
built in; "make me a Recipes space" creates another). Items in a space are
artifacts tagged with it — notes are markdown artifacts.
"""

from __future__ import annotations

import json
import re
import uuid

from langchain_core.tools import tool

from .. import db


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or uuid.uuid4().hex[:8]


@tool(parse_docstring=True)
def create_space(name: str, icon: str = "◇") -> str:
    """Create a new space — a category that appears in the app's ＋ menu.

    Use when the user asks for a new collection ('make me a recipes space',
    'I want a place for gift ideas'). Save items into it with save_note.

    Args:
        name: Display name, e.g. 'Recipes'
        icon: A single decorative character/emoji for the space

    Returns:
        JSON of the created space {id, name, icon}
    """
    space_id = _slug(name)
    db.execute(
        "INSERT INTO hermes.spaces (id, name, icon) VALUES (%s,%s,%s) "
        "ON CONFLICT (name) DO NOTHING",
        (space_id, name.strip(), icon[:4]),
    )
    return json.dumps({"id": space_id, "name": name.strip(), "icon": icon[:4]})


@tool(parse_docstring=True)
def list_spaces() -> str:
    """List the user's spaces and how many items each contains.

    Returns:
        JSON list of {id, name, icon, items}
    """
    rows = db.query(
        """SELECT s.id, s.name, s.icon, count(a.id) AS items
           FROM hermes.spaces s
           LEFT JOIN hermes.artifacts a ON a.space = s.id
           GROUP BY s.id, s.name, s.icon ORDER BY s.created_at"""
    )
    return json.dumps(list(rows), default=str)


@tool(parse_docstring=True)
def save_note(title: str, content: str, space: str = "notes") -> str:
    """Save a note (markdown) into a space. Default space is Notes.

    Use for anything the user wants kept: ideas, lists, recipes, notes from
    a conversation. It appears instantly in the app under that space.

    Args:
        title: Note title
        content: Markdown body
        space: Space id from list_spaces (default 'notes')

    Returns:
        JSON {saved: true, id}
    """
    note_id = uuid.uuid4().hex[:10]
    db.execute(
        """INSERT INTO hermes.artifacts (id, kind, title, content, version, space)
           VALUES (%s, 'markdown', %s, %s, 1, %s)""",
        (note_id, title, content, space),
    )
    return json.dumps({"saved": True, "id": note_id, "space": space})


SPACE_TOOLS = [create_space, list_spaces, save_note]
