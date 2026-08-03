"""Memory tools: bounded curated files (Hermes pattern) + mem0 semantic search."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from ..memory import BoundedMemoryFile, MemoryFileError, semantic_memory


@tool(parse_docstring=True)
def manage_memory_file(file: str, action: str, text: str = "", old_text: str = "") -> str:
    """Edit your bounded memory files: MEMORY (your notes) or USER (user profile).

    These files are injected into your context every session — keep them dense.
    Write declarative facts, not instructions to yourself ('User prefers concise
    replies' ✓, 'Always reply concisely' ✗). If a fact will be stale in a week,
    it does not belong here — use remember_fact instead. Over-limit writes fail
    with the current entries so you can consolidate and retry in the same turn.

    Args:
        file: 'MEMORY' or 'USER'
        action: 'add', 'replace', or 'remove'
        text: Entry text for add/replace
        old_text: Short unique substring identifying the entry for replace/remove

    Returns:
        The updated rendered file, or an actionable error with current entries
    """
    memory_file = BoundedMemoryFile(file.upper())
    try:
        if action == "add":
            memory_file.add(text)
        elif action == "replace":
            memory_file.replace(old_text, text)
        elif action == "remove":
            memory_file.remove(old_text)
        else:
            return f"Error: unknown action {action!r}; use add/replace/remove."
    except MemoryFileError as exc:
        return f"Error: {exc}"
    return memory_file.render()


@tool(parse_docstring=True)
def remember_fact(fact: str, category: str = "general") -> str:
    """Store a long-tail fact in semantic memory (mem0, vector-searchable).

    Use for facts that don't fit the bounded MEMORY/USER files: one-off
    details, people, dates, past decisions. For durable core preferences,
    prefer manage_memory_file.

    Args:
        fact: The fact as a standalone sentence, e.g. 'Kevyn's sister Dana
            lives in Paris'
        category: One of 'preference', 'person', 'goal', 'date', 'general'

    Returns:
        JSON confirmation of what was stored
    """
    semantic_memory.add(fact, metadata={"category": category})
    return json.dumps({"remembered": fact, "category": category})


@tool(parse_docstring=True)
def recall_memories(query: str, limit: int = 5) -> str:
    """Semantic search over long-tail memories (mem0).

    Relevant memories are auto-injected each turn; call this only when you
    need to dig deeper on a specific topic.

    Args:
        query: What to look for, e.g. 'sister birthday' or 'flight preferences'
        limit: Maximum number of memories to return

    Returns:
        JSON list of {id, memory, score}
    """
    results = semantic_memory.search(query, limit=limit)
    return json.dumps(
        [
            {
                "id": r.get("id"),
                "memory": r.get("memory", r.get("text", "")),
                "score": r.get("score"),
            }
            for r in results
        ]
    )


@tool(parse_docstring=True)
def forget_memory(memory_id: str) -> str:
    """Delete one semantic memory by id, when the user asks to forget something.

    Args:
        memory_id: The id returned by recall_memories

    Returns:
        JSON {deleted: true}
    """
    semantic_memory.delete(memory_id)
    return json.dumps({"deleted": True})
