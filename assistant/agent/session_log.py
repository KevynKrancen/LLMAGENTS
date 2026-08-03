"""Session logging middleware: mirrors messages into Postgres for search,
titles the thread, and triggers the post-turn background review.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage

from .. import db
from ..config import settings
from .review import spawn_review

logger = logging.getLogger(__name__)


def _plain_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, list):
        content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(content or "").strip()


class SessionLogMiddleware(AgentMiddleware):
    name = "session-log"

    def __init__(self, source: str = "chat") -> None:
        super().__init__()
        self._source = source
        self._turns_since_review: dict[str, int] = defaultdict(int)

    async def aafter_agent(self, state, runtime) -> None:
        try:
            self._log(state, runtime)
        except Exception as exc:  # logging must never break a run
            logger.warning("session log failed: %s", exc)

    def _log(self, state, runtime) -> None:
        info = getattr(runtime, "execution_info", None)
        thread_id = str(getattr(info, "thread_id", None) or "default")
        messages: list[BaseMessage] = list(state.get("messages", []))
        if not messages:
            return

        rows = db.query(
            "SELECT count(*) AS n FROM hermes.message_log WHERE thread_id=%s",
            (thread_id,),
        )
        already = rows[0]["n"] if rows else 0
        fresh = messages[already:]

        title = next(
            (_plain_text(m)[:80] for m in messages if m.type == "human"), ""
        )
        db.execute(
            """INSERT INTO hermes.threads (thread_id, title, source)
               VALUES (%s, %s, %s)
               ON CONFLICT (thread_id) DO UPDATE
               SET updated_at = now(),
                   title = CASE WHEN hermes.threads.title = ''
                                THEN EXCLUDED.title ELSE hermes.threads.title END""",
            (thread_id, title, self._source),
        )
        for message in fresh:
            text = _plain_text(message)
            if text:
                db.execute(
                    "INSERT INTO hermes.message_log (thread_id, source, role, content) "
                    "VALUES (%s, %s, %s, %s)",
                    (thread_id, self._source, message.type, text[:8000]),
                )

        if self._source == "chat":
            self._turns_since_review[thread_id] += sum(
                1 for m in fresh if m.type == "human"
            )
            if self._turns_since_review[thread_id] >= settings.review_every_n_turns:
                self._turns_since_review[thread_id] = 0
                spawn_review(messages)
