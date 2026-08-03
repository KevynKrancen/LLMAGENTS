"""Custom middleware for the Hermes agent.

Cache discipline (ported from Hermes Agent): anything dynamic — semantic
memory recall, per-turn context — is injected into the *user message*, never
the cached system prefix. The bounded memory snapshot is frozen per thread.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from deepagents.middleware import AgentMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from ..config import settings
from ..memory import memory_snapshot, semantic_memory

logger = logging.getLogger(__name__)

MEMORY_FENCE_OPEN = "<memory-context>"
MEMORY_FENCE_CLOSE = "</memory-context>"
SNAPSHOT_HEADER = "## Your curated memory (frozen snapshot for this session)"


def _text_of(content) -> str:
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        ).strip()
    return str(content or "").strip()


def _runtime_context(request) -> dict:
    """Best-effort merged view of runtime context + AG-UI forwarded context."""
    merged: dict = {}
    runtime = getattr(request, "runtime", None)
    context = getattr(runtime, "context", None)
    if isinstance(context, dict):
        merged.update(context)
    state = getattr(request, "state", None)
    if isinstance(state, dict):
        for item in state.get("copilotkit", {}).get("context", []) or []:
            if isinstance(item, dict) and "description" in item:
                merged.setdefault(item["description"], item.get("value"))
    return merged


class ModelSelectMiddleware(AgentMiddleware):
    """Per-request model selection from the app's Settings screen.

    The app forwards {description: "model", value: "provider:model"} in the
    AG-UI context; this hook swaps the model for that run. Instances are
    cached so switching models never rebuilds the graph.
    """

    name = "model-select"

    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[str, object] = {}
        self._lock = threading.Lock()

    async def wrap_model_call(self, request, handler):
        wanted = _runtime_context(request).get("model")
        if isinstance(wanted, str) and wanted and wanted != settings.assistant_model:
            try:
                request = request.override(model=self._model(wanted))
            except Exception as exc:  # unknown provider/model → keep default
                logger.warning("Model %r rejected (%s); using default.", wanted, exc)
        return await handler(request)

    def _model(self, spec: str):
        with self._lock:
            if spec not in self._cache:
                self._cache[spec] = init_chat_model(spec)
            return self._cache[spec]


class MemorySnapshotMiddleware(AgentMiddleware):
    """Injects the bounded MEMORY/USER files, frozen per thread (cache-safe)."""

    name = "memory-snapshot"

    def __init__(self) -> None:
        super().__init__()
        self._frozen: dict[str, str] = {}
        self._lock = threading.Lock()

    async def wrap_model_call(self, request, handler):
        thread_id = self._thread_id(request)
        with self._lock:
            snapshot = self._frozen.get(thread_id)
            if snapshot is None:
                try:
                    snapshot = f"{SNAPSHOT_HEADER}\n{memory_snapshot()}"
                except Exception as exc:  # memory must never break the run
                    logger.warning("memory snapshot failed: %s", exc)
                    snapshot = ""
                self._frozen[thread_id] = snapshot
                if len(self._frozen) > 500:  # bound in-process cache
                    self._frozen.pop(next(iter(self._frozen)))
        if snapshot:
            messages = list(request.messages)
            if not any(
                isinstance(m, SystemMessage) and str(m.content).startswith(SNAPSHOT_HEADER)
                for m in messages
            ):
                insert_at = 1 if messages and isinstance(messages[0], SystemMessage) else 0
                messages.insert(insert_at, SystemMessage(content=snapshot))
                request.messages = messages
        return await handler(request)

    @staticmethod
    def _thread_id(request) -> str:
        runtime = getattr(request, "runtime", None)
        config = getattr(runtime, "config", None) or {}
        return str(config.get("configurable", {}).get("thread_id", "default"))


class Mem0Middleware(AgentMiddleware):
    """Semantic recall into the user message; async persistence after answers."""

    name = "mem0"

    def __init__(self, top_k: int = 5) -> None:
        super().__init__()
        self._top_k = top_k
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mem0")

    async def wrap_model_call(self, request, handler):
        user_message = self._latest_user_message(request.messages)
        user_text = _text_of(user_message.content) if user_message else None

        if user_message and user_text and MEMORY_FENCE_OPEN not in user_text:
            context = self._recall_block(user_text)
            if context:
                index = request.messages.index(user_message)
                messages = list(request.messages)
                messages[index] = HumanMessage(
                    content=f"{user_text}\n\n{context}", id=user_message.id
                )
                request.messages = messages

        response = await handler(request)

        if user_text and not getattr(response, "tool_calls", None):
            answer = _text_of(getattr(response, "content", ""))
            if answer:
                clean = user_text.split(MEMORY_FENCE_OPEN)[0].strip()
                self._executor.submit(self._persist, clean, answer)
        return response

    def _recall_block(self, user_text: str) -> str | None:
        try:
            hits = semantic_memory.search(user_text, limit=self._top_k)
        except Exception as exc:
            logger.warning("mem0 search failed: %s", exc)
            return None
        memories = [m for m in (h.get("memory", h.get("text", "")) for h in hits if h) if m]
        if not memories:
            return None
        listing = "\n".join(f"- {m}" for m in memories)
        return (
            f"{MEMORY_FENCE_OPEN}\nBackground from long-term memory (may be "
            f"irrelevant — use judgement):\n{listing}\n{MEMORY_FENCE_CLOSE}"
        )

    def _persist(self, user_text: str, answer: str) -> None:
        try:
            semantic_memory.add_conversation(
                [
                    {"role": "user", "content": user_text[:2000]},
                    {"role": "assistant", "content": answer[:2000]},
                ]
            )
        except Exception as exc:
            logger.warning("mem0 add failed: %s", exc)

    @staticmethod
    def _latest_user_message(messages) -> HumanMessage | None:
        for message in reversed(list(messages)):
            if isinstance(message, HumanMessage):
                return message
        return None
