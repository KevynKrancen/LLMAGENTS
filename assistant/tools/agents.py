"""Agent-spawning tools — Hermes builds its own team.

Spawned specialists persist and join the subagent roster on the next
message; delegate to them with task(). Spawning is approval-gated.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from ..agent.agent_registry import agent_registry, tool_inventory


@tool(parse_docstring=True)
def spawn_agent(
    name: str,
    description: str,
    system_prompt: str,
    tools: str,
    model: str = "",
) -> str:
    """Spawn a persistent specialist agent you can delegate to with task().

    Use when the user wants a dedicated agent ("spawn a crypto analyst",
    "I want a nutrition coach agent") or when building a domain that
    deserves its own specialist. The agent persists across sessions and
    becomes routable on the next message. Keep it FOCUSED: one clear job,
    few tools.

    Args:
        name: Short kebab-case name, e.g. 'crypto-analyst'
        description: One precise sentence — the router uses this to decide
            when to delegate to it, so say exactly what it handles
        system_prompt: The specialist's full instructions: role, process,
            rules, output format
        tools: JSON array of backend tool names it may use, e.g.
            '["search_web","fetch_web_page","save_note"]' (max 8;
            call list_agent_tools to see what exists)
        model: Optional 'provider:model' override; empty inherits the main model

    Returns:
        JSON of the spawned agent, or an error listing valid tool names
    """
    try:
        tool_names = json.loads(tools)
        if not isinstance(tool_names, list):
            raise ValueError("tools must be a JSON array of names")
        spawned = agent_registry.spawn(name, description, system_prompt, tool_names, model)
    except (ValueError, json.JSONDecodeError) as exc:
        return f"Error: {exc}"
    return json.dumps({"spawned": True, **spawned,
                       "note": "Routable via task() from the next message."})


@tool(parse_docstring=True)
def list_agents() -> str:
    """List spawned specialist agents and the built-in roster.

    Returns:
        JSON {spawned: [{name, description, tools, model}], builtin: [...]}
    """
    return json.dumps(
        {
            "spawned": [
                {"name": a["name"], "description": a["description"],
                 "tools": a["tools"], "model": a["model"] or "(inherit)"}
                for a in agent_registry.list()
            ],
            "builtin": ["researcher", "analyst", "general-purpose"],
        }
    )


@tool(parse_docstring=True)
def retire_agent(name: str) -> str:
    """Permanently remove a spawned agent by name. Ask the user first.

    Args:
        name: The spawned agent's name from list_agents

    Returns:
        JSON {retired: true|false}
    """
    return json.dumps({"retired": agent_registry.retire(name)})


@tool(parse_docstring=True)
def list_agent_tools() -> str:
    """List every backend tool name grantable to a spawned agent.

    Returns:
        JSON array of tool names with one-line descriptions
    """
    return json.dumps(
        [{"name": name, "about": (tool.description or "").split("\n")[0][:90]}
         for name, tool in sorted(tool_inventory().items())]
    )


AGENT_TOOLS = [spawn_agent, list_agents, retire_agent, list_agent_tools]
