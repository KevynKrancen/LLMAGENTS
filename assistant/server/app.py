"""Hermes assistant server.

FastAPI app exposing:
- POST /agent          — AG-UI protocol endpoint (SSE) for the iPhone app
- REST                 — threads, artifacts, routines, device queue, shortcuts
- POST /webhooks/whatsapp — inbound WhatsApp (scoped toolset, replies sent
                            outside the agent loop — Hermes trust-tier rule)

Run: uvicorn assistant.server.app:app --host 0.0.0.0 --port 8787
"""

from __future__ import annotations

import logging
import secrets
import uuid
from contextlib import asynccontextmanager

import httpx
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from .. import db
from ..agent.agent import get_assistant_graph
from ..config import settings
from ..integrations import integration_registry
from ..integrations.catalog import CATALOG
from ..routines import Routine, routine_manager
from . import device_queue, push
from .oauth import router as oauth_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_PUBLIC_PATHS = {
    "/health",
    "/webhooks/whatsapp",
    # OAuth runs in a plain browser tab (no way to attach the bearer header).
    "/auth/google/start",
    "/auth/google/callback",
}


async def _run_headless(graph, prompt: str, source: str) -> str:
    """Run a prompt in a fresh thread and return the final text answer."""
    thread_id = f"{source}-{uuid.uuid4().hex[:10]}"
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=prompt)]},
        config={"configurable": {"thread_id": thread_id}, "recursion_limit": 60},
    )
    for message in reversed(result.get("messages", [])):
        if message.type == "ai":
            content = message.content
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict)
                )
            return str(content).strip()
    return "(no answer)"


async def _run_routine(routine: Routine) -> str:
    graph = await get_assistant_graph("routine")
    return await _run_headless(graph, routine.prompt, "routine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_schema()
    from ..agent.agent import setup_persistence

    await setup_persistence()
    # Async persistence must be created inside the event loop, so the graph
    # and its AG-UI endpoint are mounted here rather than at import time.
    global _agui_agent
    _agui_agent = LangGraphAGUIAgent(
        name="hermes",
        description="Kevyn's personal deep-agent assistant.",
        graph=await get_assistant_graph("chat"),
    )
    add_langgraph_fastapi_endpoint(app=app, agent=_agui_agent, path="/agent")
    routine_manager.start(_run_routine)
    logger.info("Hermes server ready on :%d", settings.port)
    yield
    routine_manager.shutdown()
    await db.close_pools()


app = FastAPI(title="Hermes Assistant", lifespan=lifespan)
app.include_router(oauth_router)

_agui_agent: LangGraphAGUIAgent | None = None
_agui_graph_version = -1


@app.middleware("http")
async def refresh_connector_tools(request: Request, call_next):
    """Hot-swap the chat graph when connectors changed since the last run."""
    global _agui_graph_version
    if request.url.path == "/agent" and _agui_agent is not None:
        if _agui_graph_version != integration_registry.version:
            _agui_agent.graph = await get_assistant_graph("chat")
            _agui_graph_version = integration_registry.version
    return await call_next(request)


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    if request.url.path not in _PUBLIC_PATHS and settings.api_auth_token:
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not secrets.compare_digest(supplied, settings.api_auth_token):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


# --- Health -----------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"ok": True, "model": settings.assistant_model}


# --- Threads ----------------------------------------------------------------

@app.get("/threads")
async def list_threads(query: str = "", limit: int = 30) -> list[dict]:
    if query:
        return db.query(
            """SELECT DISTINCT m.thread_id, t.title, t.updated_at::text AS updated_at
               FROM hermes.message_log m JOIN hermes.threads t USING (thread_id)
               WHERE t.source = 'chat'
                 AND to_tsvector('simple', m.content) @@ plainto_tsquery('simple', %s)
               ORDER BY updated_at DESC LIMIT %s""",
            (query, min(limit, 50)),
        )
    return db.query(
        "SELECT thread_id, title, updated_at::text AS updated_at FROM hermes.threads "
        "WHERE source='chat' ORDER BY updated_at DESC LIMIT %s",
        (min(limit, 50),),
    )


@app.get("/threads/{thread_id}/messages")
async def thread_messages(thread_id: str) -> list[dict]:
    return db.query(
        "SELECT role, content, created_at::text AS created_at "
        "FROM hermes.message_log WHERE thread_id=%s ORDER BY id",
        (thread_id,),
    )


# --- Artifacts --------------------------------------------------------------

@app.get("/artifacts")
async def list_artifacts(limit: int = 50, space: str = "") -> list[dict]:
    if space:
        return db.query(
            "SELECT id, kind, title, content, version, space, updated_at::text AS updated_at "
            "FROM hermes.artifacts WHERE space=%s ORDER BY updated_at DESC LIMIT %s",
            (space, min(limit, 100)),
        )
    return db.query(
        "SELECT id, kind, title, content, version, space, updated_at::text AS updated_at "
        "FROM hermes.artifacts ORDER BY updated_at DESC LIMIT %s",
        (min(limit, 100),),
    )


@app.get("/spaces")
async def list_spaces_route() -> list[dict]:
    return db.query(
        """SELECT s.id, s.name, s.icon, count(a.id) AS items
           FROM hermes.spaces s
           LEFT JOIN hermes.artifacts a ON a.space = s.id
           GROUP BY s.id, s.name, s.icon ORDER BY s.created_at"""
    )


# --- Routines ---------------------------------------------------------------

class RoutineIn(BaseModel):
    name: str
    cron: str
    prompt: str


class RoutinePatch(BaseModel):
    enabled: bool


@app.get("/routines")
async def get_routines() -> list[dict]:
    return routine_manager.list_full()


@app.post("/routines")
async def create_routine_route(body: RoutineIn) -> dict:
    try:
        routine = routine_manager.create(body.name, body.cron, body.prompt)
    except ValueError as exc:
        raise HTTPException(422, f"Invalid cron: {exc}") from exc
    return {"id": routine.id}


@app.patch("/routines/{routine_id}")
async def patch_routine(routine_id: str, body: RoutinePatch) -> dict:
    if not routine_manager.set_enabled(routine_id, body.enabled):
        raise HTTPException(404, "routine not found")
    return {"ok": True}


@app.delete("/routines/{routine_id}")
async def delete_routine_route(routine_id: str) -> dict:
    if not routine_manager.delete(routine_id):
        raise HTTPException(404, "routine not found")
    return {"ok": True}


# --- Device queue (shortcut pack + app executor) ----------------------------

class DeviceRegistration(BaseModel):
    token: str


class DeviceResult(BaseModel):
    command_id: str
    status: str  # success | error
    output: str = ""


@app.post("/device/register")
async def register_device(body: DeviceRegistration) -> dict:
    push.register_device_token(body.token)
    return {"ok": True}


@app.get("/device/next-command")
async def next_command() -> dict:
    command = device_queue.next_pending()
    return command or {"id": None}


@app.post("/device/results")
async def device_result(body: DeviceResult) -> dict:
    if not device_queue.record_result(body.command_id, body.status, body.output):
        raise HTTPException(404, "unknown command")
    return {"ok": True}


# --- Shortcut pack manifest -------------------------------------------------

@app.get("/shortcuts/manifest")
async def shortcuts_manifest() -> dict:
    """Shortcut pack the app offers to install. iCloud links are filled in
    once the user builds and shares each shortcut (see shortcuts/README.md)."""
    rows = db.query("SELECT name, payload FROM hermes.device_commands WHERE FALSE")  # noqa: F841
    return {
        "pack_version": 1,
        "shortcuts": [
            {"name": "AI: Setup", "purpose": "Store server URL + token in Data Jar, warm permissions", "icloud_url": ""},
            {"name": "AI: Poll", "purpose": "Fetch and execute pending device commands", "icloud_url": ""},
            {"name": "AI: Send iMessage", "purpose": "Silent iMessage send {to, text}", "icloud_url": ""},
            {"name": "AI: Send Email", "purpose": "Silent Apple Mail send {to, subject, body}", "icloud_url": ""},
            {"name": "AI: Set Focus", "purpose": "Set a focus mode {mode, minutes}", "icloud_url": ""},
            {"name": "AI: Timer", "purpose": "Start a timer {minutes}", "icloud_url": ""},
            {"name": "AI: Home Scene", "purpose": "Run a HomeKit scene {scene}", "icloud_url": ""},
            {"name": "AI: Navigate", "purpose": "Start navigation {destination}", "icloud_url": ""},
            {"name": "AI: Prefill WhatsApp", "purpose": "Open WhatsApp with message prefilled {phone, text}", "icloud_url": ""},
        ],
    }


# --- Connectors (the app platform) ------------------------------------------

class ConnectorIn(BaseModel):
    kind: str  # mcp | openapi | builtin
    name: str
    config: dict = {}


class ConnectorPatch(BaseModel):
    enabled: bool


@app.get("/apps")
async def list_apps() -> dict:
    return {"installed": await integration_registry.summary(), "catalog": CATALOG}


@app.post("/apps")
async def add_app(body: ConnectorIn) -> dict:
    # Catalog entries that are actually hosted MCP servers translate here.
    if body.kind == "builtin":
        entry = next((e for e in CATALOG if e["app"] == body.config.get("app", body.name)), None)
        if entry and entry.get("mcp_url"):
            return {"id": integration_registry.add("mcp", body.name, {"url": entry["mcp_url"]})}
    try:
        return {"id": integration_registry.add(body.kind, body.name, body.config)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.patch("/apps/{integration_id}")
async def toggle_app(integration_id: str, body: ConnectorPatch) -> dict:
    if not integration_registry.set_enabled(integration_id, body.enabled):
        raise HTTPException(404, "connector not found")
    return {"ok": True}


@app.delete("/apps/{integration_id}")
async def delete_app(integration_id: str) -> dict:
    if not integration_registry.remove(integration_id):
        raise HTTPException(404, "connector not found")
    return {"ok": True}


# --- WhatsApp webhook (untrusted inbound → scoped toolset) ------------------

@app.get("/webhooks/whatsapp")
async def whatsapp_verify(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.whatsapp_verify_token
    ):
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(403, "verification failed")


@app.post("/webhooks/whatsapp")
async def whatsapp_inbound(request: Request) -> dict:
    body = await request.json()
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            for message in change.get("value", {}).get("messages", []) or []:
                sender = message.get("from", "")
                text = (message.get("text") or {}).get("body", "")
                if not text or sender != settings.whatsapp_owner_phone:
                    continue  # only the owner may talk to the agent
                answer = await _run_headless(
                    await get_assistant_graph("webhook"), text, "webhook"
                )
                # Outbound send happens OUTSIDE the agent loop (trust tier).
                await _send_whatsapp_reply(sender, answer)
    return {"ok": True}


async def _send_whatsapp_reply(to_phone: str, text: str) -> None:
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        return
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"https://graph.facebook.com/v23.0/{settings.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_phone,
                "type": "text",
                "text": {"body": text[:4000]},
            },
        )
