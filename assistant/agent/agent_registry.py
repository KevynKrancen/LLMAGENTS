"""Spawned-agent registry.

Specialists the assistant creates at runtime persist here and join the
deep agent's subagent roster (routable via the task() tool) on the next
message. Tool grants are by name, validated against the backend tool
inventory — a spawned agent can never hold a tool that doesn't exist.
"""

from __future__ import annotations

import json
import uuid

from langchain_core.tools import BaseTool

from .. import db


def tool_inventory() -> dict[str, BaseTool]:
    """All grantable backend tools by name (device tools included)."""
    from ..tools import BACKEND_TOOLS
    from ..tools.device import DEVICE_TOOLS

    return {tool.name: tool for tool in [*BACKEND_TOOLS, *DEVICE_TOOLS]}


class AgentRegistry:
    def __init__(self) -> None:
        self.version = 0

    def list(self) -> list[dict]:
        rows = db.query(
            "SELECT id, name, description, system_prompt, tools, model, enabled "
            "FROM hermes.agents ORDER BY created_at"
        )
        result = []
        for row in rows:
            tools = row["tools"] if isinstance(row["tools"], list) else json.loads(row["tools"])
            result.append({**row, "tools": tools})
        return result

    def spawn(self, name: str, description: str, system_prompt: str,
              tools: list[str], model: str = "") -> dict:
        inventory = tool_inventory()
        unknown = [t for t in tools if t not in inventory]
        if unknown:
            raise ValueError(
                f"Unknown tools {unknown}. Available: {sorted(inventory)}"
            )
        if len(tools) > 8:
            raise ValueError("Grant at most 8 tools — focused specialists work better.")
        agent_id = uuid.uuid4().hex[:10]
        db.execute(
            """INSERT INTO hermes.agents (id, name, description, system_prompt, tools, model)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (name) DO UPDATE SET description=EXCLUDED.description,
                 system_prompt=EXCLUDED.system_prompt, tools=EXCLUDED.tools,
                 model=EXCLUDED.model, enabled=TRUE""",
            (agent_id, name.strip(), description.strip(), system_prompt, json.dumps(tools), model),
        )
        self.version += 1
        return {"id": agent_id, "name": name.strip(), "tools": tools}

    def retire(self, name: str) -> bool:
        removed = db.execute("DELETE FROM hermes.agents WHERE name ILIKE %s", (name.strip(),))
        if removed:
            self.version += 1
        return removed > 0

    def build_subagent_specs(self) -> list[dict]:
        """Persisted agents as deepagents declarative subagent specs."""
        inventory = tool_inventory()
        specs = []
        for record in self.list():
            if not record["enabled"]:
                continue
            spec: dict = {
                "name": record["name"],
                "description": record["description"],
                "system_prompt": record["system_prompt"],
                "tools": [inventory[t] for t in record["tools"] if t in inventory],
            }
            if record["model"]:
                spec["model"] = record["model"]
            specs.append(spec)
        return specs


agent_registry = AgentRegistry()
