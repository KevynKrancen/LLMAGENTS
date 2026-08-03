"""Zero-LLM session search over all past conversations (Hermes pattern).

Three arg-inferred modes: discovery (query), scroll (thread_id), browse
(no args). Routine-run sessions are demoted, not excluded.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from .. import db


def _bookends(thread_id: str) -> dict:
    rows = db.query(
        "SELECT role, content FROM hermes.message_log "
        "WHERE thread_id=%s AND role IN ('human','ai') ORDER BY id",
        (thread_id,),
    )
    trim = [{"role": r["role"], "text": r["content"][:200]} for r in rows]
    return {"start": trim[:3], "end": trim[-3:] if len(trim) > 3 else []}


@tool(parse_docstring=True, handle_tool_error=True)
def session_search(query: str = "", thread_id: str = "", limit: int = 5) -> str:
    """Search or browse past conversations. No arguments = browse recent.

    Use when the user references something from a past conversation, or when
    relevant cross-session context probably exists — recall before asking the
    user to repeat themselves. Modes: pass query for full-text discovery;
    pass thread_id to read one conversation; pass neither to browse recent.

    Args:
        query: Full-text search words (discovery mode)
        thread_id: Read this conversation's messages (scroll mode)
        limit: Max results (discovery/browse)

    Returns:
        JSON — discovery: [{thread_id, title, snippet, when, bookends}];
        scroll: [{role, content}]; browse: [{thread_id, title, when}]
    """
    if thread_id:
        rows = db.query(
            "SELECT role, content FROM hermes.message_log "
            "WHERE thread_id=%s ORDER BY id LIMIT 100",
            (thread_id,),
        )
        return json.dumps([{"role": r["role"], "content": r["content"][:600]} for r in rows])

    if query:
        rows = db.query(
            """SELECT m.thread_id,
                      max(t.title) AS title,
                      max(t.updated_at)::text AS "when",
                      max(m.source) AS source,
                      ts_headline('simple', string_agg(left(m.content, 400), ' '),
                                  plainto_tsquery('simple', %(q)s)) AS snippet,
                      max(ts_rank(to_tsvector('simple', m.content),
                                  plainto_tsquery('simple', %(q)s)))
                      * CASE WHEN max(m.source) = 'routine' THEN 0.3 ELSE 1 END AS rank
               FROM hermes.message_log m
               JOIN hermes.threads t ON t.thread_id = m.thread_id
               WHERE to_tsvector('simple', m.content) @@ plainto_tsquery('simple', %(q)s)
               GROUP BY m.thread_id
               ORDER BY rank DESC
               LIMIT %(limit)s""",
            {"q": query, "limit": max(1, min(limit, 10))},
        )
        return json.dumps(
            [
                {
                    "thread_id": r["thread_id"],
                    "title": r["title"],
                    "when": r["when"],
                    "snippet": r["snippet"],
                    "bookends": _bookends(r["thread_id"]),
                }
                for r in rows
            ]
        )

    rows = db.query(
        "SELECT thread_id, title, updated_at::text AS \"when\" FROM hermes.threads "
        "WHERE source='chat' ORDER BY updated_at DESC LIMIT %s",
        (max(1, min(limit, 20)),),
    )
    return json.dumps(list(rows))
