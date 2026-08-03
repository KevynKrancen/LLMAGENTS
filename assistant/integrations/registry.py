"""Dynamic integration registry — the app platform.

An integration is a row in Postgres: {kind: mcp|openapi|builtin, name,
config}. Enabling one automatically attaches its tools to the agent:
- mcp     → tools discovered from an MCP server (langchain-mcp-adapters)
- openapi → tools generated from a REST API's OpenAPI spec
- builtin → curated catalog apps (weather, telegram, github, …)

The registry keeps a version counter; the agent layer rebuilds its graphs
whenever the version changes, so new tools apply to the very next message.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain_core.tools import BaseTool

from .. import db

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    def __init__(self) -> None:
        self.version = 0
        self._tool_cache: dict[str, list[BaseTool]] = {}

    # --- CRUD ---

    def list(self) -> list[dict]:
        rows = db.query(
            "SELECT id, kind, name, config, enabled, created_at::text AS created_at "
            "FROM hermes.integrations ORDER BY created_at"
        )
        result = []
        for row in rows:
            config = row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])
            result.append({**row, "config": config})
        return result

    def add(self, kind: str, name: str, config: dict) -> str:
        if kind not in {"mcp", "openapi", "builtin"}:
            raise ValueError(f"Unknown integration kind {kind!r}")
        integration_id = uuid.uuid4().hex[:10]
        db.execute(
            "INSERT INTO hermes.integrations (id, kind, name, config) VALUES (%s,%s,%s,%s)",
            (integration_id, kind, name, json.dumps(config)),
        )
        self.invalidate(integration_id)
        return integration_id

    def set_enabled(self, integration_id: str, enabled: bool) -> bool:
        changed = db.execute(
            "UPDATE hermes.integrations SET enabled=%s WHERE id=%s", (enabled, integration_id)
        )
        if changed:
            self.invalidate(integration_id)
        return changed > 0

    def remove(self, integration_id: str) -> bool:
        removed = db.execute("DELETE FROM hermes.integrations WHERE id=%s", (integration_id,))
        if removed:
            self.invalidate(integration_id)
        return removed > 0

    def invalidate(self, integration_id: str | None = None) -> None:
        if integration_id:
            self._tool_cache.pop(integration_id, None)
        else:
            self._tool_cache.clear()
        self.version += 1

    # --- tool loading ---

    async def load_tools(self) -> list[BaseTool]:
        """All tools from enabled integrations. Failures never break the agent."""
        tools: list[BaseTool] = []
        seen_names: set[str] = set()
        for integration in self.list():
            if not integration["enabled"]:
                continue
            integration_tools = await self._tools_for(integration)
            for tool in integration_tools:
                if tool.name in seen_names:
                    continue  # first integration wins on name collisions
                seen_names.add(tool.name)
                tools.append(tool)
        return tools

    async def _tools_for(self, integration: dict) -> list[BaseTool]:
        cached = self._tool_cache.get(integration["id"])
        if cached is not None:
            return cached
        try:
            tools = await self._build_tools(integration)
        except Exception as exc:
            logger.warning("Integration %s (%s) failed to load: %s",
                           integration["name"], integration["kind"], exc)
            tools = []
        self._tool_cache[integration["id"]] = tools
        return tools

    @staticmethod
    async def _build_tools(integration: dict) -> list[BaseTool]:
        kind, config = integration["kind"], integration["config"]
        if kind == "mcp":
            from .mcp import load_mcp_tools

            return await load_mcp_tools(integration["name"], config)
        if kind == "openapi":
            from .openapi import load_openapi_tools

            return await load_openapi_tools(integration["name"], config)
        if kind == "builtin":
            from .catalog import load_builtin_tools

            return load_builtin_tools(config.get("app", integration["name"]), config)
        return []

    async def summary(self) -> list[dict[str, Any]]:
        """Installed apps + their live tool names (for the Apps screen)."""
        result = []
        for integration in self.list():
            tools = await self._tools_for(integration) if integration["enabled"] else []
            safe_config = {
                key: ("•••" if any(s in key.lower() for s in ("token", "key", "secret", "password")) else value)
                for key, value in integration["config"].items()
            }
            result.append(
                {
                    "id": integration["id"],
                    "kind": integration["kind"],
                    "name": integration["name"],
                    "enabled": integration["enabled"],
                    "config": safe_config,
                    "tools": [tool.name for tool in tools],
                }
            )
        return result


integration_registry = IntegrationRegistry()
