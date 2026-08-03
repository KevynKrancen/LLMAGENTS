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
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

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


def _lg_pool() -> AsyncConnectionPool:
    """Unopened async pool for LangGraph persistence — opened via setup_persistence()."""
    return AsyncConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=6,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )


@lru_cache(maxsize=1)
def _checkpointer() -> AsyncPostgresSaver:
    return AsyncPostgresSaver(_lg_pool())


@lru_cache(maxsize=1)
def _store() -> AsyncPostgresStore:
    return AsyncPostgresStore(_lg_pool())


async def setup_persistence() -> None:
    """Open pools and create LangGraph tables. Call once at server startup."""
    for component in (_checkpointer(), _store()):
        await component.conn.open()  # no-op if already open
        await component.setup()


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


def _backend():
    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": StoreBackend(namespace=lambda rt: (settings.user_id, "skills")),
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
    # Connector installs attach arbitrary new tools — always ask first.
    "install_mcp_connector": {"allowed_decisions": ["approve", "reject"]},
    "install_api_connector": {"allowed_decisions": ["approve", "reject"]},
    # Spawning a persistent specialist is a standing change — ask first.
    "spawn_agent": {"allowed_decisions": ["approve", "edit", "reject"]},
}

# Graphs cached per (mode, integrations version) so connector changes apply
# on the very next message without a restart.
_graph_cache: dict[tuple[str, int], object] = {}


def build_assistant_graph(mode: Mode = "chat", extra_tools: list | None = None):
    """Build and return the compiled assistant graph (sync, static tools only)."""
    from ..tools.agents import AGENT_TOOLS
    from ..tools.apps import APP_TOOLS
    from .agent_registry import agent_registry
    from .receipts import ReceiptMiddleware

    middleware = [
        CopilotKitMiddleware(),
        ModelSelectMiddleware(),
        MemorySnapshotMiddleware(),
        Mem0Middleware(),
        SessionLogMiddleware(source=mode),
        ReceiptMiddleware(source=mode),
    ]
    tools = [*_TOOLSETS[mode](), *(extra_tools or [])]
    if mode == "chat":
        tools.extend(APP_TOOLS)
        tools.extend(AGENT_TOOLS)
    return create_deep_agent(
        model=settings.assistant_model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        subagents=[*build_subagents(), *agent_registry.build_subagent_specs()],
        skills=[str(_SKILLS_DIR), "/skills/"],  # bundled (read-only) + agent-authored (writable)
        backend=_backend(),
        state_schema=AssistantState,
        checkpointer=_checkpointer(),
        store=_store(),
        interrupt_on=_OUTBOUND_APPROVAL if mode == "chat" else None,
        name=f"hermes-{mode}",
    )


async def get_assistant_graph(mode: Mode = "chat"):
    """Graph with connector tools + spawned agents, rebuilt on any change."""
    from ..integrations import integration_registry
    from .agent_registry import agent_registry

    key = (mode, integration_registry.version, agent_registry.version)
    graph = _graph_cache.get(key)
    if graph is None:
        connector_tools = await integration_registry.load_tools() if mode != "webhook" else []
        graph = build_assistant_graph(mode, extra_tools=connector_tools)
        _graph_cache.clear()  # keep only the current version's graphs
        _graph_cache[key] = graph
    return graph
