"""OpenAPI integrations — turn any REST API into agent tools.

config: {spec_url: str, base_url?: str, headers?: dict, max_tools?: int}
Each operation with an operationId becomes one tool; query/path parameters
become tool arguments, and JSON request bodies are passed as a 'body' arg.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field, create_model

_PRIMITIVES: dict[str, type] = {"string": str, "integer": int, "number": float, "boolean": bool}


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_")[:60] or "op"


def _make_tool(
    method: str,
    path: str,
    operation: dict,
    base_url: str,
    headers: dict,
) -> BaseTool | None:
    operation_id = operation.get("operationId") or f"{method}_{path}"
    name = _sanitize(operation_id)
    description = (
        operation.get("summary") or operation.get("description") or f"{method.upper()} {path}"
    )[:900]

    fields: dict[str, Any] = {}
    for parameter in operation.get("parameters", []):
        if parameter.get("in") not in {"query", "path"}:
            continue
        param_name = _sanitize(parameter.get("name", ""))
        if not param_name:
            continue
        schema = parameter.get("schema", {})
        annotation = _PRIMITIVES.get(schema.get("type", "string"), str)
        default = ... if parameter.get("required") else None
        fields[param_name] = (
            annotation if default is ... else annotation | None,
            Field(default, description=str(parameter.get("description", ""))[:200]),
        )
    has_body = "requestBody" in operation
    if has_body:
        fields["body"] = (
            str,
            Field("{}", description="JSON request body as a string"),
        )
    args_schema = create_model(f"{name}_args", **fields)  # type: ignore[call-overload]

    path_params = {p.get("name") for p in operation.get("parameters", []) if p.get("in") == "path"}

    def _call(**kwargs: Any) -> str:
        url_path = path
        query: dict[str, Any] = {}
        body_payload: Any = None
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "body" and has_body:
                try:
                    body_payload = json.loads(value)
                except json.JSONDecodeError:
                    return "Error: 'body' must be valid JSON."
            elif key in path_params:
                url_path = url_path.replace("{" + key + "}", str(value))
            else:
                query[key] = value
        response = httpx.request(
            method.upper(),
            f"{base_url.rstrip('/')}{url_path}",
            params=query or None,
            json=body_payload,
            headers=headers,
            timeout=30,
        )
        text = response.text[:4000]
        return f"HTTP {response.status_code}\n{text}"

    return StructuredTool.from_function(
        func=_call, name=name, description=description, args_schema=args_schema
    )


async def load_openapi_tools(name: str, config: dict) -> list[BaseTool]:
    spec_url = config.get("spec_url", "")
    if not spec_url:
        raise ValueError("OpenAPI integration needs a 'spec_url'")
    headers = config.get("headers") or {}

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(spec_url, headers=headers)
        response.raise_for_status()
        spec = response.json()

    servers = spec.get("servers") or []
    base_url = config.get("base_url") or (servers[0].get("url") if servers else "")
    if not base_url:
        raise ValueError("Could not determine base_url — set it in the integration config")
    if base_url.startswith("/"):
        origin = httpx.URL(spec_url)
        base_url = f"{origin.scheme}://{origin.host}{'' if origin.is_default_port else f':{origin.port}'}{base_url}"

    tools: list[BaseTool] = []
    max_tools = int(config.get("max_tools", 30))
    for path, operations in (spec.get("paths") or {}).items():
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue
            tool = _make_tool(method.lower(), path, operation, base_url, headers)
            if tool:
                tools.append(tool)
            if len(tools) >= max_tools:
                return tools
    return tools
