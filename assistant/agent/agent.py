"""Assembles the Hermes deep agent (deepagents 0.7+).

build_assistant_graph() returns a compiled LangGraph graph. Three variants
share the same construction with different toolsets (Hermes trust tiers):
'chat' (everything), 'routine' (no routine management — recursion guard),
'webhook' (minimal, for untrusted inbound WhatsApp messages).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from copilotkit import CopilotKitMiddleware, CopilotKitState
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend, StoreBackend
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

from ..config import settings
from ..tools import BACKEND_TOOLS, ROUTINE_RUN_TOOLS, WEBHOOK_TOOLS
from ..tools.device import DEVICE_TOOLS
from .middleware import Mem0Middleware, MemorySnapshotMiddleware, ModelSelectMiddleware
from .prompt import SYSTEM_PROMPT
from .session_log import SessionLogMiddleware
from .subagents import build_subagents

_SKILLS_DIR = Path(__file__).parent / "skills"

Mode = Literal["chat", "routine", "webhook"]


class AssistantState(CopilotKitState):
    """Graph state: CopilotKit bridge fields + our shared-state keys."""

    artifact: dict | None


@lru_cache(maxsize=1)
def _checkpointer() -> PostgresSaver:
    saver = PostgresSaver.from_conn_string(settings.database_url)
    if hasattr(saver, "__enter__"):
        saver = saver.__enter__()
    saver.setup()
    return saver


@lru_cache(maxsize=1)
def _store() -> PostgresStore:
    store = PostgresStore.from_conn_string(settings.database_url)
    if hasattr(store, "__enter__"):
        store = store.__enter__()
    store.setup()
    return store


def _workspace_backend():
    """Sandbox for code execution when configured; plain disk workspace otherwise."""
    if settings.sandbox_provider == "daytona":
        from langchain_daytona import DaytonaSandbox  # type: ignore[import-not-found]

        return DaytonaSandbox()
    if settings.sandbox_provider == "e2b":
        from langchain_e2b import E2BSandbox  # type: ignore[import-not-found]

        return E2BSandbox()
    if settings.sandbox_provider == "modal":
        from langchain_modal import ModalSandbox  # type: ignore[import-not-found]

        return ModalSandbox()
    return FilesystemBackend(root_dir=str(settings.workspace_dir), virtual_mode=True)


def _backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/skills/": StoreBackend(runtime, namespace=lambda rt: (settings.user_id, "skills")),
            "/workspace/": _workspace_backend(),
        },
    )


_TOOLSETS = {
    "chat": lambda: [*BACKEND_TOOLS, *DEVICE_TOOLS],
    "routine": lambda: [*ROUTINE_RUN_TOOLS, *DEVICE_TOOLS],
    "webhook": lambda: list(WEBHOOK_TOOLS),
}

_OUTBOUND_APPROVAL = {
    "send_gmail": {"allowed_decisions": ["approve", "edit", "reject"]},
    "send_apple_mail": {"allowed_decisions": ["approve", "edit", "reject"]},
    "send_whatsapp_message": {"allowed_decisions": ["approve", "edit", "reject"]},
    "delete_calendar_event": {"allowed_decisions": ["approve", "reject"]},
}


@lru_cache(maxsize=3)
def build_assistant_graph(mode: Mode = "chat"):
    """Build (once per mode) and return the compiled assistant graph."""
    middleware = [
        CopilotKitMiddleware(),
        ModelSelectMiddleware(),
        MemorySnapshotMiddleware(),
        Mem0Middleware(),
        SessionLogMiddleware(source=mode),
    ]
    return create_deep_agent(
        model=settings.assistant_model,
        tools=_TOOLSETS[mode](),
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        subagents=build_subagents(),
        skills=[str(_SKILLS_DIR), "/skills/"],  # bundled (read-only) + agent-authored (writable)
        backend=_backend,
        state_schema=AssistantState,
        checkpointer=_checkpointer(),
        store=_store(),
        interrupt_on=_OUTBOUND_APPROVAL if mode == "chat" else None,
        name=f"hermes-{mode}",
    )
