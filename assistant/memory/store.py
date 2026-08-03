"""Long-term memory: mem0 semantic store + Hermes-style bounded memory files.

Two complementary layers (ported from the Hermes Agent architecture):

1. **Bounded curated files** — MEMORY (agent notes) and USER (user profile),
   char-budgeted, entry-delimited, edited explicitly by the agent through the
   ``manage_memory_file`` tool and frozen into context once per session.
2. **mem0 semantic memory** — unbounded long-tail facts with vector search
   (pgvector), searched per turn and injected into the user message.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from .. import db
from ..config import settings

ENTRY_DELIMITER = "\n§\n"

_FILE_LIMITS = {
    "MEMORY": settings.memory_char_limit,
    "USER": settings.user_profile_char_limit,
}


# ---------------------------------------------------------------------------
# Bounded memory files (Hermes pattern)
# ---------------------------------------------------------------------------

@dataclass
class MemoryFileError(Exception):
    message: str
    entries: list[str]

    def __str__(self) -> str:
        listing = "\n".join(f"- {e}" for e in self.entries) or "(empty)"
        return f"{self.message}\nCurrent entries:\n{listing}"


class BoundedMemoryFile:
    """Char-budgeted, §-delimited memory file stored in Postgres."""

    def __init__(self, name: str) -> None:
        if name not in _FILE_LIMITS:
            raise ValueError(f"Unknown memory file {name!r}; use MEMORY or USER.")
        self.name = name
        self.limit = _FILE_LIMITS[name]

    # -- reads --

    def entries(self) -> list[str]:
        rows = db.query("SELECT content FROM hermes.memory_files WHERE name=%s", (self.name,))
        content = rows[0]["content"] if rows else ""
        return [e.strip() for e in content.split(ENTRY_DELIMITER.strip()) if e.strip()]

    def render(self) -> str:
        """Render for prompt injection with a usage header, Hermes-style."""
        entries = self.entries()
        used = len(self._join(entries))
        pct = int(100 * used / self.limit) if self.limit else 0
        label = "MEMORY (your personal notes)" if self.name == "MEMORY" else "USER (profile)"
        body = "\n".join(f"- {e}" for e in entries) or "(empty)"
        return f"{label} [{pct}% — {used:,}/{self.limit:,} chars]\n{body}"

    # -- writes --

    def add(self, text: str) -> None:
        self._write(self.entries() + [text.strip()])

    def replace(self, old_text: str, new_text: str) -> None:
        entries = self.entries()
        index = self._find(entries, old_text)
        entries[index] = new_text.strip()
        self._write(entries)

    def remove(self, old_text: str) -> None:
        entries = self.entries()
        del entries[self._find(entries, old_text)]
        self._write(entries)

    # -- internals --

    def _find(self, entries: list[str], needle: str) -> int:
        matches = [i for i, e in enumerate(entries) if needle in e]
        if not matches:
            raise MemoryFileError(f"No entry contains {needle!r}.", entries)
        if len(matches) > 1:
            raise MemoryFileError(
                f"{needle!r} matches {len(matches)} entries — use a longer unique substring.",
                entries,
            )
        return matches[0]

    def _write(self, entries: list[str]) -> None:
        content = self._join(entries)
        if len(content) > self.limit:
            raise MemoryFileError(
                f"{self.name} would be {len(content)} chars (limit {self.limit}). "
                "Consolidate or remove entries in this same turn, then retry.",
                entries,
            )
        db.execute(
            "UPDATE hermes.memory_files SET content=%s, updated_at=now() WHERE name=%s",
            (content, self.name),
        )

    @staticmethod
    def _join(entries: list[str]) -> str:
        return ENTRY_DELIMITER.join(entries)


def memory_snapshot() -> str:
    """Both files rendered together — frozen into context once per session."""
    return BoundedMemoryFile("MEMORY").render() + "\n\n" + BoundedMemoryFile("USER").render()


# ---------------------------------------------------------------------------
# mem0 semantic memory
# ---------------------------------------------------------------------------

class SemanticMemory:
    """Lazy mem0 client: hosted platform if MEM0_API_KEY, else local + pgvector."""

    def __init__(self) -> None:
        self._client: Any = None
        self._lock = threading.Lock()

    @property
    def client(self) -> Any:
        with self._lock:
            if self._client is None:
                self._client = self._build()
            return self._client

    @staticmethod
    def _build() -> Any:
        if settings.mem0_api_key:
            from mem0 import MemoryClient

            return MemoryClient(api_key=settings.mem0_api_key)
        from urllib.parse import urlparse

        from mem0 import Memory

        parsed = urlparse(settings.database_url)
        return Memory.from_config(
            {
                "vector_store": {
                    "provider": "pgvector",
                    "config": {
                        "dbname": parsed.path.lstrip("/"),
                        "user": parsed.username,
                        "password": parsed.password,
                        "host": parsed.hostname,
                        "port": parsed.port or 5432,
                        "collection_name": "hermes_memories",
                    },
                },
            }
        )

    def add(self, text: str, metadata: dict | None = None) -> Any:
        return self.client.add(
            [{"role": "user", "content": text}],
            user_id=settings.user_id,
            metadata=metadata or {},
        )

    def add_conversation(self, messages: list[dict]) -> Any:
        return self.client.add(messages, user_id=settings.user_id)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        result = self.client.search(query, user_id=settings.user_id, limit=limit)
        # Local engine returns {"results": [...]}; the platform client a list.
        return result.get("results", result) if isinstance(result, dict) else result

    def delete(self, memory_id: str) -> None:
        self.client.delete(memory_id=memory_id)


semantic_memory = SemanticMemory()
