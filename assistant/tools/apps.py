"""Connector tools — the agent can inspect and install apps itself.

Installs are gated behind interrupt_on approval (configured in agent.py),
so nothing attaches without the user seeing it.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from ..integrations import integration_registry


@tool(parse_docstring=True)
def list_connected_apps() -> str:
    """List installed connectors (apps) and the tools each one provides.

    Returns:
        JSON list of {id, kind, name, enabled, tools}
    """
    rows = [
        {"id": i["id"], "kind": i["kind"], "name": i["name"], "enabled": i["enabled"]}
        for i in integration_registry.list()
    ]
    return json.dumps(rows)


@tool(parse_docstring=True)
def install_mcp_connector(name: str, url: str) -> str:
    """Connect an MCP server as a new app — its tools attach automatically.

    Use when the user asks to 'add' or 'connect' a service that has an MCP
    server (e.g. Notion at https://mcp.notion.com/mcp). Takes effect on the
    next message.

    Args:
        name: Short app name, e.g. 'notion'
        url: The MCP server URL (streamable HTTP or SSE endpoint)

    Returns:
        JSON with the new connector id
    """
    integration_id = integration_registry.add("mcp", name, {"url": url})
    return json.dumps({"installed": True, "id": integration_id,
                       "note": "Tools attach on the next message."})


@tool(parse_docstring=True)
def install_api_connector(name: str, spec_url: str, auth_header: str = "") -> str:
    """Connect any REST API as a new app by its OpenAPI spec URL.

    Each documented endpoint becomes a tool automatically. Use when the
    user wants to integrate a service that publishes an OpenAPI/Swagger
    spec. Takes effect on the next message.

    Args:
        name: Short app name, e.g. 'petstore'
        spec_url: URL of the OpenAPI JSON spec
        auth_header: Optional 'Header-Name: value' line for authenticated APIs

    Returns:
        JSON with the new connector id
    """
    config: dict = {"spec_url": spec_url}
    if auth_header and ":" in auth_header:
        key, _, value = auth_header.partition(":")
        config["headers"] = {key.strip(): value.strip()}
    integration_id = integration_registry.add("openapi", name, config)
    return json.dumps({"installed": True, "id": integration_id,
                       "note": "Tools attach on the next message."})


APP_TOOLS = [list_connected_apps, install_mcp_connector, install_api_connector]
