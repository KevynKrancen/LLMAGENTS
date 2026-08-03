"""Post-turn background review (ported from Hermes Agent).

After a response is delivered — never competing with the user's task — a
cheap-model headless run reviews the recent conversation with ONLY memory
tools available and decides what to persist. Fire-and-forget.
"""

from __future__ import annotations

import logging
import threading

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage

from ..config import settings

logger = logging.getLogger(__name__)

REVIEW_PROMPT = """Review the conversation digest below and consider saving \
to memory if appropriate. Focus on:
1. Has the user revealed things about themselves — persona, preferences,
   relationships, goals, important dates?
2. Has the user expressed expectations about how the assistant should behave?

Rules:
- Write declarative facts, not instructions ('User prefers concise replies' ✓).
- If a fact will be stale in a week, it does not belong in the bounded files —
  use remember_fact.
- Core durable facts → manage_memory_file (MEMORY or USER). Long-tail details
  → remember_fact.
- If nothing is worth saving, reply exactly 'Nothing to save.' and stop.

Conversation digest:
{digest}
"""


def _digest(messages: list[BaseMessage], max_chars: int = 6000) -> str:
    lines = []
    for message in messages:
        role = getattr(message, "type", "message")
        if role == "tool":
            continue  # tool payloads are machine noise for review purposes
        content = message.content
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        text = str(content).strip()
        if text:
            lines.append(f"{role}: {text[:600]}")
    return "\n".join(lines)[-max_chars:]


def _run_review(messages: list[BaseMessage]) -> None:
    from langchain.agents import create_agent

    from ..tools.memory import manage_memory_file, remember_fact

    try:
        reviewer = create_agent(
            model=init_chat_model(settings.review_model),
            tools=[manage_memory_file, remember_fact],
            system_prompt=(
                "You are a silent memory curator for a personal assistant. "
                "You only use the provided memory tools; you never reply to the user."
            ),
        )
        reviewer.invoke(
            {"messages": [{"role": "user",
                           "content": REVIEW_PROMPT.format(digest=_digest(messages))}]},
            config={"recursion_limit": 12},
        )
        logger.info("Background memory review completed.")
    except Exception as exc:
        logger.warning("Background review failed: %s", exc)


def spawn_review(messages: list[BaseMessage]) -> None:
    """Run the review on a daemon thread — never blocks or raises."""
    threading.Thread(
        target=_run_review, args=(list(messages),), daemon=True, name="hermes-review"
    ).start()
