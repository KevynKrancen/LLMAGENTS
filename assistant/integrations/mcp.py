"""MCP integrations — connect any Model Context Protocol server.

config: {url: str, transport?: "streamable_http"|"sse", headers?: dict}
Tools are discovered live from the server via langchain-mcp-adapters.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


async def load_mcp_tools(name: str, config: dict) -> list[BaseTool]:
    url = config.get("url", "")
    if not url:
        raise ValueError("MCP integration needs a 'url'")
    transport = config.get("transport") or ("sse" if url.rstrip("/").endswith("/sse") else "streamable_http")
    client = MultiServerMCPClient(
        {
            name: {
                "url": url,
                "transport": transport,
                **({"headers": config["headers"]} if config.get("headers") else {}),
            }
        }
    )
    return await client.get_tools()
