# Hermes HTTP API

Complete reference for the FastAPI server in `assistant/server/app.py` (plus the
OAuth router in `assistant/server/oauth.py`). The server exposes one streaming
AG-UI endpoint for the iPhone app, a small REST surface for everything the app
renders (threads, artifacts, routines, ledger, connectors, device queue), a
Google OAuth flow, and a WhatsApp webhook.

Run it with:

```bash
uvicorn assistant.server.app:app --host 0.0.0.0 --port 8787
```

Defaults come from `assistant/config.py` (`Settings`): host `0.0.0.0`, port
`8787`. All examples below assume:

```bash
export HERMES=http://localhost:8787
export TOKEN=<value of API_AUTH_TOKEN>
```

## Authentication

A single static bearer token, checked by the `bearer_auth` HTTP middleware:

- Configure `API_AUTH_TOKEN` in `assistant/.env` (generate with
  `openssl rand -hex 32`). If it is **empty, auth is disabled entirely**.
- Every request must send `Authorization: Bearer <token>`; comparison is
  constant-time (`secrets.compare_digest`).
- Failure returns `401 {"detail": "unauthorized"}`.

Public paths (no token required — defined in `_PUBLIC_PATHS`):

| Path | Why public |
|---|---|
| `/health` | liveness probe |
| `/webhooks/whatsapp` | Meta calls it; protected by the verify-token handshake and an owner-phone allowlist |
| `/auth/google/start`, `/auth/google/callback` | opened in a plain browser tab, which cannot attach the header |

Everything else — including `/integrations/status` and the library-added
`GET /agent/health` — requires the bearer token.

A second middleware, `refresh_connector_tools`, runs before each `/agent`
request: if the connector registry version changed since the last run
(`integration_registry.version`), the chat graph is rebuilt so newly installed
connector tools apply to the very next message, without a restart.

## Endpoint index

| Method | Path | Purpose |
|---|---|---|
| POST | `/agent` | AG-UI run endpoint (SSE stream) |
| GET | `/agent/health` | AG-UI agent liveness (added by `add_langgraph_fastapi_endpoint`) |
| GET | `/health` | server liveness |
| GET | `/threads` | list / full-text search chat threads |
| GET | `/threads/{thread_id}/messages` | logged messages of a thread |
| GET | `/artifacts` | list artifacts (optionally by workspace folder) |
| GET | `/workspace` | workspace folder tree |
| GET | `/hub` | composed home surface |
| GET | `/routines` | list routines |
| POST | `/routines` | create a routine |
| PATCH | `/routines/{routine_id}` | enable/disable a routine |
| DELETE | `/routines/{routine_id}` | delete a routine |
| POST | `/device/register` | register an APNs device token |
| GET | `/device/next-command` | claim the next pending device command |
| POST | `/device/results` | report a device command result |
| GET | `/shortcuts/manifest` | Apple Shortcuts pack manifest |
| GET | `/ledger` | action receipts (audit trail) |
| POST | `/ledger/seen` | mark all receipts seen |
| POST | `/ledger/{receipt_id}/undo` | run a receipt's undo descriptor |
| GET | `/apps` | installed connectors + catalog |
| POST | `/apps` | install a connector |
| PATCH | `/apps/{integration_id}` | enable/disable a connector |
| DELETE | `/apps/{integration_id}` | remove a connector |
| GET | `/auth/google/start` | begin Google OAuth (browser) |
| GET | `/auth/google/callback` | OAuth redirect target |
| GET | `/integrations/status` | connection status for Settings screen |
| GET | `/webhooks/whatsapp` | Meta webhook verification handshake |
| POST | `/webhooks/whatsapp` | inbound WhatsApp messages |

---

## POST /agent — the AG-UI endpoint

Mounted at startup (inside `lifespan`) via
`ag_ui_langgraph.add_langgraph_fastapi_endpoint`, wrapping the compiled
`chat`-mode deep agent in a `copilotkit.LangGraphAGUIAgent` named `hermes`.
The request body is an AG-UI `RunAgentInput`; the response is a
`text/event-stream` of AG-UI protocol events. State is checkpointed in
Postgres per `threadId`, so successive runs with the same `threadId` continue
one conversation.

### Request: RunAgentInput

JSON, camelCase on the wire (the server model accepts snake_case too via
`populate_by_name`):

```json
{
  "threadId": "thread-a1b2c3d4e5f6",
  "runId": "run-9f8e7d6c",
  "messages": [
    { "id": "u-1", "role": "user", "content": "What's on my calendar tomorrow?" }
  ],
  "tools": [
    {
      "name": "show_event_card",
      "description": "Render a calendar-event card (title, start, end, location).",
      "parameters": {
        "type": "object",
        "properties": {
          "title": { "type": "string" },
          "start": { "type": "string" },
          "end": { "type": "string" },
          "location": { "type": "string" }
        },
        "required": ["title", "start"]
      }
    }
  ],
  "context": [
    { "description": "model", "value": "anthropic:claude-sonnet-5" },
    { "description": "memory_enabled", "value": "true" }
  ],
  "state": {},
  "forwardedProps": {}
}
```

Field notes (verified against `ag_ui.core.types.RunAgentInput` and the app's
`HermesApp/src/agui/types.ts`):

| Field | Type | Notes |
|---|---|---|
| `threadId` | string | conversation id; also the LangGraph checkpoint thread |
| `runId` | string | unique per run |
| `messages` | `AgMessage[]` | wire history. Assistant messages may carry `toolCalls: [{id, type: "function", function: {name, arguments}}]`; tool results are `{role: "tool", content, toolCallId}` |
| `tools` | `AgTool[]` | **frontend tools** — `{name, description, parameters}` with JSON-Schema parameters. See round-trip below |
| `context` | `[{description, value}]` | free-form context items; the Hermes app sends the selected `model` and `memory_enabled` |
| `state` | object | shared state echoed back through `STATE_SNAPSHOT` / `STATE_DELTA` |
| `forwardedProps` | object | run options; carries `command.resume` for interrupt resumption. Top-level keys are camel→snake converted server-side (`nodeName` → `node_name`); recognised keys include `command`, `node_name`, `stream_subgraphs` (default `true`) |

### Response: SSE event stream

`Content-Type: text/event-stream`; each frame is `data: <json>\n\n` with a
`type` discriminator. Event vocabulary (mirrors `@ag-ui/core`; the full set the
app's reducer handles is in `HermesApp/src/agui/types.ts`):

| Event | Payload fields | Meaning |
|---|---|---|
| `RUN_STARTED` | `threadId`, `runId` | run accepted |
| `TEXT_MESSAGE_START` | `messageId`, `role` | assistant message begins |
| `TEXT_MESSAGE_CONTENT` | `messageId`, `delta` | streamed text chunk |
| `TEXT_MESSAGE_END` | `messageId` | message complete |
| `REASONING_START` / `REASONING_CONTENT` / `REASONING_END` | `delta` on content | extended-thinking stream (older servers emit `THINKING_*` aliases; the app normalises both) |
| `TOOL_CALL_START` | `toolCallId`, `toolCallName`, `parentMessageId` | tool invocation begins |
| `TOOL_CALL_ARGS` | `toolCallId`, `delta` | streamed JSON argument chunk |
| `TOOL_CALL_END` | `toolCallId` | arguments complete |
| `TOOL_CALL_RESULT` | `toolCallId`, `messageId`, `content`, `role: "tool"` | backend tool result |
| `STATE_SNAPSHOT` | `snapshot` | full shared-state replacement |
| `STATE_DELTA` | `delta` (RFC 6902 JSON Patch ops) | incremental state update |
| `MESSAGES_SNAPSHOT` | `messages` | authoritative wire history |
| `STEP_STARTED` / `STEP_FINISHED` | `stepName` | graph node boundaries |
| `CUSTOM` | `name`, `value` | out-of-band events — notably `name: "on_interrupt"` (see below) |
| `RAW` | `event`, `source` | passthrough of raw LangGraph events |
| `RUN_FINISHED` | `threadId`, `runId`, `result` | run complete (also emitted after an interrupt pauses the run) |
| `RUN_ERROR` | `message`, `code` | run failed; stream ends |

Example:

```bash
curl -N "$HERMES/agent" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "threadId": "thread-demo1",
    "runId": "run-1",
    "messages": [{"id": "u-1", "role": "user", "content": "Hi Hermes"}],
    "tools": [], "context": [], "state": {}, "forwardedProps": {}
  }'
```

```
data: {"type":"RUN_STARTED","threadId":"thread-demo1","runId":"run-1"}

data: {"type":"TEXT_MESSAGE_START","messageId":"msg-3f2a","role":"assistant"}

data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-3f2a","delta":"Hello"}

data: {"type":"TEXT_MESSAGE_END","messageId":"msg-3f2a"}

data: {"type":"RUN_FINISHED","threadId":"thread-demo1","runId":"run-1"}
```

### Frontend tool round-trip

Tools listed in `RunAgentInput.tools` are injected into the model's toolset by
`CopilotKitMiddleware` (they land in graph state under `copilotkit.actions`;
request tools win over stale state tools on name collision). They have **no
backend implementation** — when the model calls one:

1. The client receives `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END`
   for the call, and the run ends (`RUN_FINISHED`) without a
   `TOOL_CALL_RESULT`.
2. The client executes the tool (the Hermes app renders a card) and starts a
   **follow-up run** on the same `threadId`, appending a tool-result message to
   `messages`:

```json
{ "id": "tr-1", "role": "tool", "content": "shown", "toolCallId": "call_abc123" }
```

The Hermes app (`HermesApp/src/state/chat.ts`) does this automatically after
`RUN_FINISHED` whenever card tools ran. The frontend tools it declares on every
run (`HermesApp/src/device/frontendTools.ts`): `render_component`,
`show_plan_card`, `show_media_card`, `show_event_card`, `show_email_draft`,
`show_chart`.

Device tools (`play_youtube_video`, `open_iphone_app`, `run_iphone_shortcut`,
`create_iphone_reminder`, `show_on_iphone_map`, `play_youtube_search`) are
**not** frontend tools: they are backend tools that enqueue into the device
queue, and the app drains the queue when it sees their `TOOL_CALL_END` —
keeping one execution path with the headless/shortcut flow.

### Interrupts and resume (human-in-the-loop approvals)

The chat graph is built with `interrupt_on` (`assistant/agent/agent.py`,
`_OUTBOUND_APPROVAL`):

| Tool | Allowed decisions |
|---|---|
| `send_gmail` | approve, edit, reject |
| `send_apple_mail` | approve, edit, reject |
| `send_whatsapp_message` | approve, edit, reject |
| `delete_calendar_event` | approve, reject |
| `install_mcp_connector` | approve, reject |
| `install_api_connector` | approve, reject |

When the model calls one of these, `HumanInTheLoopMiddleware` raises a
LangGraph interrupt. On the wire this appears as a `CUSTOM` event with
`name: "on_interrupt"` whose `value` is the HITL request, followed by
`RUN_FINISHED` (the run is paused at a checkpoint, not failed):

```json
{
  "type": "CUSTOM",
  "name": "on_interrupt",
  "value": {
    "action_requests": [
      {
        "name": "send_gmail",
        "args": { "to": "dana@example.com", "subject": "Friday", "body": "See you at 10." },
        "description": "Tool execution requires approval..."
      }
    ],
    "review_configs": [
      { "action_name": "send_gmail", "allowed_decisions": ["approve", "edit", "reject"] }
    ]
  }
}
```

To resume, POST `/agent` again with the **same `threadId`** and the decision in
`forwardedProps.command.resume`. The value is handed verbatim to LangGraph's
`Command(resume=...)`; `HumanInTheLoopMiddleware` expects a `HITLResponse` —
one decision per `action_request`, in order:

```bash
curl -N "$HERMES/agent" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "threadId": "thread-demo1",
    "runId": "run-2",
    "messages": [], "tools": [], "context": [], "state": {},
    "forwardedProps": {
      "command": { "resume": { "decisions": [ { "type": "approve" } ] } }
    }
  }'
```

Decision shapes (from `langchain.agents.middleware.human_in_the_loop`):

- `{"type": "approve"}` — execute the tool call as-is.
- `{"type": "edit", "edited_action": {"name": "send_gmail", "args": {…}}}` —
  execute with revised name/args.
- `{"type": "reject", "message": "optional reason"}` — skip execution; the
  model receives an error `ToolMessage` and is told not to retry.
- `{"type": "respond", "message": "…"}` — answer on behalf of the tool
  (only where `respond` is allowed; no Hermes tool currently allows it).

The Hermes app surfaces the interrupt as an approval sheet
(`ApprovalSheet.tsx`); its store detects interrupts by scanning `RAW`/`CUSTOM`
events for `__interrupt__` and resumes through this same
`forwardedProps.command.resume` channel.

### GET /agent/health

Added automatically by the AG-UI mount. Requires the bearer token (it is not
in `_PUBLIC_PATHS`).

```json
{ "status": "ok", "agent": { "name": "hermes" } }
```

---

## Health

### GET /health

Public. Returns the configured model spec.

```bash
curl "$HERMES/health"
# {"ok": true, "model": "anthropic:claude-sonnet-5"}
```

## Threads

Threads and messages are mirrored into Postgres by `SessionLogMiddleware`
(`hermes.threads`, `hermes.message_log`); only `source='chat'` threads are
listed. `role` values are LangChain message types: `human`, `ai`, `tool`.

### GET /threads

Query parameters: `query` (optional full-text search over message content,
Postgres `plainto_tsquery`), `limit` (default 30, capped at 50).

```bash
curl -H "Authorization: Bearer $TOKEN" "$HERMES/threads?query=flight&limit=10"
```

```json
[
  {
    "thread_id": "thread-a1b2c3d4e5f6",
    "title": "Find me a flight to Athens in October",
    "updated_at": "2026-08-02 18:41:07.331+03"
  }
]
```

### GET /threads/{thread_id}/messages

```bash
curl -H "Authorization: Bearer $TOKEN" "$HERMES/threads/thread-a1b2c3d4e5f6/messages"
```

```json
[
  { "role": "human", "content": "Find me a flight to Athens in October", "created_at": "2026-08-02 18:39:55+03" },
  { "role": "ai", "content": "Here are three options…", "created_at": "2026-08-02 18:41:07+03" }
]
```

## Artifacts and workspace

### GET /artifacts

Query parameters: `limit` (default 50, capped at 100), `space` (workspace
folder/node id; empty returns all). `kind` is one of `html | markdown | table
| chart`.

```bash
curl -H "Authorization: Bearer $TOKEN" "$HERMES/artifacts?space=n-travel01"
```

```json
[
  {
    "id": "art-7c1d9e",
    "kind": "html",
    "title": "Japan itinerary",
    "content": "<div class=\"itinerary\">…</div>",
    "version": 3,
    "space": "n-travel01",
    "updated_at": "2026-08-01 09:12:44+03"
  }
]
```

### GET /workspace

The recursive folder tree from `hermes.nodes` (built by
`assistant/tools/workspace.py::_tree`). `icon` is an SF Symbol name;
`dashboard` is the artifact id rendered as the folder's custom UI (`""` if
none); `items` counts artifacts filed in the folder.

```json
[
  {
    "id": "n-travel01",
    "name": "Travel",
    "icon": "airplane",
    "dashboard": "",
    "items": 2,
    "children": [
      { "id": "n-japan02", "name": "Japan", "icon": "airplane", "dashboard": "art-7c1d9e", "items": 4, "children": [] }
    ]
  }
]
```

## GET /hub

The composed home surface: unseen-receipt count, workspace tree, four most
recent chat threads, and up to three enabled routines.

```bash
curl -H "Authorization: Bearer $TOKEN" "$HERMES/hub"
```

```json
{
  "unseen_actions": 2,
  "workspace": [ … as GET /workspace … ],
  "recent_threads": [ { "thread_id": "…", "title": "…", "updated_at": "…" } ],
  "routines": [
    { "id": "rt-4b2a9c8d7e6f", "name": "Morning brief", "cron": "30 7 * * 1-5", "last_result": "Sunny, 2 meetings…" }
  ]
}
```

## Routines

Scheduled agent runs (`assistant/routines/manager.py`, APScheduler + Postgres).
Each fire runs the prompt headlessly in a fresh thread with the `routine`
toolset; results land as a push notification and a ledger receipt.

### GET /routines

```json
[
  {
    "id": "rt-4b2a9c8d7e6f",
    "name": "Morning brief",
    "cron": "30 7 * * 1-5",
    "prompt": "Summarise my calendar and inbox for today.",
    "enabled": true,
    "created_at": "2026-07-14 08:00:00+03",
    "last_run_at": "2026-08-03 07:30:02+03",
    "last_result": "Sunny, 2 meetings, 3 unread emails worth a look."
  }
]
```

### POST /routines

Body (`RoutineIn`): `{name, cron, prompt}`. `cron` is standard 5-field crontab,
validated with `CronTrigger.from_crontab` in the server's timezone
(`settings.timezone`, default `Asia/Jerusalem`). Invalid cron → `422
{"detail": "Invalid cron: …"}`.

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Evening digest", "cron": "0 21 * * *", "prompt": "Summarise today."}' \
  "$HERMES/routines"
# {"id": "rt-1f2e3d4c5b6a"}
```

### PATCH /routines/{routine_id}

Body (`RoutinePatch`): `{"enabled": false}`. Returns `{"ok": true}`; `404
{"detail": "routine not found"}` for unknown ids.

### DELETE /routines/{routine_id}

Returns `{"ok": true}` or `404`.

## Device queue

Backs the on-phone executor and the Apple Shortcuts pack. Device tools enqueue
commands into `hermes.device_commands` and ring an APNs "doorbell" push; the
app (live chat) or the `AI: Poll` shortcut (zero-tap) claims and executes them.

### POST /device/register

Body (`DeviceRegistration`): `{"token": "<apns-device-token-hex>"}` → stores
the APNs token (idempotent). Returns `{"ok": true}`.

### GET /device/next-command

Atomically claims the oldest `pending` command (marks it `delivered`).

```bash
curl -H "Authorization: Bearer $TOKEN" "$HERMES/device/next-command"
# with work queued:
# {"id": "9f8e7d6c5b4a", "name": "send_imessage", "payload": {"to": "+972501234567", "text": "On my way"}}
# empty queue:
# {"id": null}
```

### POST /device/results

Body (`DeviceResult`): `{"command_id": "9f8e7d6c5b4a", "status": "success",
"output": "sent"}`. `status` is `success | error` (stored as `done` /
`failed`; output truncated to 2000 chars). Returns `{"ok": true}`; `404
{"detail": "unknown command"}` for unknown ids.

## GET /shortcuts/manifest

Static manifest of the shortcut pack the app offers to install (`icloud_url`
values are filled in once each shortcut is built and shared — see
`shortcuts/README.md`).

```json
{
  "pack_version": 1,
  "shortcuts": [
    { "name": "AI: Setup", "purpose": "Store server URL + token in Data Jar, warm permissions", "icloud_url": "" },
    { "name": "AI: Poll", "purpose": "Fetch and execute pending device commands", "icloud_url": "" }
  ]
}
```

(Nine entries total: Setup, Poll, Send iMessage, Send Email, Set Focus, Timer,
Home Scene, Navigate, Prefill WhatsApp.)

## Action ledger

Audit trail of everything the agent did (`hermes.receipts`, written by
`ReceiptMiddleware`), with best-effort undo.

### GET /ledger

Query parameters: `limit` (default 30, capped at 100), `unseen_only`
(boolean). `reversibility` is `full | partial | none`; `can_undo` is computed
(`undo IS NOT NULL AND NOT undone`).

```bash
curl -H "Authorization: Bearer $TOKEN" "$HERMES/ledger?unseen_only=true"
```

```json
[
  {
    "id": "rc-0a1b2c3d4e5f",
    "tool": "create_calendar_event",
    "summary": "Added 'Dentist' Tue 10:00",
    "reversibility": "full",
    "undone": false,
    "seen": false,
    "source": "chat",
    "created_at": "2026-08-03 09:15:31+03",
    "can_undo": true
  }
]
```

### POST /ledger/seen

Marks every unseen receipt seen. Returns `{"ok": true}`.

### POST /ledger/{receipt_id}/undo

Executes the receipt's stored undo descriptor
(`assistant/agent/receipts.py::execute_undo`; kinds:
`delete_calendar_event`, `delete_routine`, `toggle_routine`,
`delete_artifact`, `remove_connector`). Returns a human-readable outcome, or
`500 {"detail": "Undo failed: …"}`.

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" "$HERMES/ledger/rc-0a1b2c3d4e5f/undo"
# {"result": "Undone."}
```

## Connectors (/apps)

The connector platform (`assistant/integrations/`). A connector is
`{kind: mcp | openapi | builtin, name, config}`; enabling one attaches its
tools to the agent on the next message (registry version bump + the `/agent`
hot-swap middleware).

### GET /apps

Returns installed connectors (with live tool names and **masked secrets** —
config keys containing `token`/`key`/`secret`/`password` render as `•••`) plus
the curated catalog.

```json
{
  "installed": [
    {
      "id": "9a8b7c6d5e",
      "kind": "builtin",
      "name": "Weather",
      "enabled": true,
      "config": { "app": "weather" },
      "tools": ["get_weather_forecast"]
    }
  ],
  "catalog": [
    { "app": "weather", "title": "Weather", "description": "Forecasts anywhere via Open-Meteo. No key needed.", "fields": [] },
    { "app": "telegram", "title": "Telegram", "description": "Send yourself Telegram messages via a bot.",
      "fields": [
        { "key": "bot_token", "label": "Bot token (from @BotFather)", "secret": true },
        { "key": "chat_id", "label": "Your chat id (from @userinfobot)" }
      ] },
    { "app": "notion", "title": "Notion (via MCP)", "description": "Connect Notion's hosted MCP server.",
      "mcp_url": "https://mcp.notion.com/mcp", "fields": [] }
  ]
}
```

Catalog apps: `weather`, `telegram`, `github`, `spotify`, `notion`
(`assistant/integrations/catalog.py`).

### POST /apps

Body (`ConnectorIn`): `{kind, name, config}`.

- `kind: "mcp"` — `config.url` points at an MCP server; tools are discovered
  via `langchain-mcp-adapters`.
- `kind: "openapi"` — tools generated from a REST API's OpenAPI spec.
- `kind: "builtin"` — a catalog app; `config` holds its declared fields (plus
  `app` to name the catalog entry when it differs from `name`). A builtin
  whose catalog entry has an `mcp_url` (e.g. Notion) is transparently stored
  as an `mcp` connector pointing at that URL.

Unknown `kind` → `422`. Returns `{"id": "<10-hex id>"}`.

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"kind": "builtin", "name": "Weather", "config": {"app": "weather"}}' \
  "$HERMES/apps"
# {"id": "9a8b7c6d5e"}
```

### PATCH /apps/{integration_id}

Body (`ConnectorPatch`): `{"enabled": false}` → `{"ok": true}`; `404
{"detail": "connector not found"}`.

### DELETE /apps/{integration_id}

Returns `{"ok": true}` or `404`.

## Google OAuth and integration status

From `assistant/server/oauth.py`. The flow is browser-based (the app opens the
URL in a tab), which is why the two `/auth/google/*` routes are public.

### GET /auth/google/start

`302` redirect to Google's consent screen (`access_type=offline`,
`prompt=consent`, `include_granted_scopes=true`, scopes from
`assistant/google_auth.py::SCOPES`). Requires a **Web application** OAuth
client saved at `assistant/credentials.json` with redirect URI
`{server}/auth/google/callback`; missing credentials → `500` with setup
instructions.

### GET /auth/google/callback

Google's redirect target. Exchanges the authorization code, writes the
credentials JSON (including the refresh token) to
`assistant/data/google_token.json`, and returns a small HTML "Google
connected" page. Exchange failure → `400 {"detail": "OAuth exchange failed:
…"}`.

### GET /integrations/status

Connection status for the app's Settings screen (bearer-authenticated).

```bash
curl -H "Authorization: Bearer $TOKEN" "$HERMES/integrations/status"
```

```json
{
  "google": { "connected": false, "connect_url": "/auth/google/start" },
  "apple_mail": { "connected": false, "note": "Apple offers no OAuth for IMAP — set ICLOUD_EMAIL + app-specific password in assistant/.env" },
  "whatsapp": { "connected": true },
  "web_search": { "connected": true },
  "youtube": { "connected": false },
  "push": { "connected": true },
  "sandbox": { "provider": "none" },
  "memory": { "mode": "mem0-local-pgvector" }
}
```

`google.connect_url` is `null` once connected. `memory.mode` is
`mem0-hosted` when `MEM0_API_KEY` is set, else `mem0-local-pgvector`.

## WhatsApp webhook

Public endpoint for the Meta WhatsApp Cloud API. Inbound messages are treated
as **untrusted**: they run against the minimal `webhook` toolset, and the
reply is sent outside the agent loop (the Hermes trust-tier rule — the agent
never holds a raw send-message capability on this path).

### Verification flow — GET /webhooks/whatsapp

When you register the webhook URL in the Meta developer console, Meta sends a
handshake:

```
GET /webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=1158201444
```

The server compares `hub.verify_token` to `WHATSAPP_VERIFY_TOKEN` and, if
`hub.mode == "subscribe"` and the token matches, echoes `hub.challenge` back
as plain text (`200`). Any mismatch → `403 {"detail": "verification failed"}`.

```bash
curl "$HERMES/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=$WHATSAPP_VERIFY_TOKEN&hub.challenge=42"
# 42
```

### Inbound — POST /webhooks/whatsapp

Accepts the standard Cloud API delivery body
(`entry[].changes[].value.messages[]`). For each **text** message:

1. Messages from any number other than `WHATSAPP_OWNER_PHONE` are silently
   ignored — only the owner may talk to the agent.
2. The text runs headlessly on the `webhook`-mode graph in a fresh thread
   (`webhook-<10 hex>`, recursion limit 60); no chat history, no connector
   tools.
3. The final answer is sent back via the Graph API
   (`POST https://graph.facebook.com/v23.0/{phone_number_id}/messages`),
   truncated to 4000 characters — skipped entirely if `WHATSAPP_TOKEN` /
   `WHATSAPP_PHONE_NUMBER_ID` are unconfigured.

Always returns `{"ok": true}` so Meta does not retry. Note there is no
`X-Hub-Signature-256` HMAC check; protection is the verify-token handshake,
the owner-phone allowlist, and the scoped webhook toolset.

```bash
curl -X POST -H "Content-Type: application/json" "$HERMES/webhooks/whatsapp" -d '{
  "entry": [{ "changes": [{ "value": { "messages": [
    { "from": "972501234567", "text": { "body": "Remind me to call mum at 6" } }
  ] } }] }]
}'
# {"ok": true}
```

## Error shapes

FastAPI conventions throughout: errors are `{"detail": "<message>"}` with the
status codes noted per endpoint (`401` unauthorized, `404` not found, `422`
validation/invalid cron/unknown connector kind, `500` undo or OAuth-setup
failures). Request-body validation errors return FastAPI's standard `422`
payload. `RUN_ERROR` inside the `/agent` SSE stream reports agent failures
without an HTTP error status.
