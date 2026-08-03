# Hermes Backend Architecture

The backend (`assistant/`) is a single FastAPI process hosting a DeepAgents 0.7
agent behind the AG-UI protocol, with Postgres as the only stateful dependency.
The iPhone app (`HermesApp/`) is a thin AG-UI SSE client; everything the agent
knows, owns, or has done lives server-side.

This document covers the full system: topology, the life of a chat message,
trust tiers, persistence, memory, device control, connector hot-swap, and the
action-receipt ledger.

---

## 1. System diagram

```
┌─────────────────────────── iPhone (HermesApp, Expo) ────────────────────────────┐
│  Chat UI ── AG-UI SSE client (src/agui/client.ts, expo/fetch streaming)         │
│  Generated components (render_component / show_* frontend tools)                │
│  ApprovalSheet (LangGraph interrupts)   ArtifactCanvas (STATE_DELTA)            │
│  Device executor (src/device/toolExecutor.ts): deep links, x-callback           │
│  shortcuts, EventKit reminders — fed by TOOL_CALL stream + device queue         │
└──────────┬────────────────────────▲─────────────────────────────▲───────────────┘
           │ POST /agent (SSE)      │ REST (threads, hub, ledger,  │ APNs pushes
           │ + REST (Bearer auth)   │ artifacts, routines, apps,   │ (doorbell /
           ▼                        │ device queue, shortcuts)     │ routine result)
┌──────────────────────────── FastAPI server (:8787) ─────────────┼───────────────┐
│  assistant/server/app.py                                        │               │
│   ├─ bearer_auth middleware (all non-public paths)              │               │
│   ├─ refresh_connector_tools middleware (graph hot-swap)        │               │
│   ├─ AG-UI endpoint  ──► LangGraphAGUIAgent("hermes")           │               │
│   ├─ REST routes ──► db helpers / routine_manager / registry    │               │
│   ├─ /webhooks/whatsapp ──► webhook-tier graph (headless)       │               │
│   └─ oauth.py (/auth/google/*)          push.py (ApnsClient) ───┘               │
│                                                                                 │
│  Agent layer  assistant/agent/                                                  │
│   get_assistant_graph(mode) — cache keyed (mode, connector version)             │
│   ┌─────────────────────────────────────────────────────────────┐               │
│   │ create_deep_agent (deepagents 0.7)                          │               │
│   │  middleware: CopilotKit → ModelSelect → MemorySnapshot      │               │
│   │              → Mem0 → SessionLog → Receipts                 │               │
│   │  subagents: researcher, analyst                             │               │
│   │  skills: bundled dir + /skills/ (store-backed, writable)    │               │
│   │  backend: Composite(State | /skills/→Store |                │               │
│   │           /workspace/→Filesystem-or-sandbox)                │               │
│   │  tools: core + device + apps + connector tools (per tier)   │               │
│   │  interrupt_on: outbound sends + connector installs (chat)   │               │
│   └─────────────────────────────────────────────────────────────┘               │
│                                                                                 │
│  Routines  routines/manager.py (APScheduler, cron)                              │
│  Connectors  integrations/ (registry + mcp + openapi + catalog)                 │
│  Memory  memory/store.py (bounded files + mem0)                                 │
└───────┬────────────────────────────────────────────┬────────────────────────────┘
        │                                            │
        ▼                                            ▼
┌─  Postgres (+pgvector) ─────────────┐   ┌─ External services ─────────────────┐
│ hermes.* application tables         │   │ LLM providers (Anthropic/OpenAI/…)  │
│ LangGraph checkpoints + store       │   │ Gmail / Calendar / YouTube (Google) │
│ mem0 collection: hermes_memories    │   │ WhatsApp Cloud API   iCloud IMAP    │
└─────────────────────────────────────┘   │ Tavily  APNs  MCP servers  OpenAPI  │
                                          └─────────────────────────────────────┘
```

---

## 2. Request lifecycle of a chat message

Everything in one round trip, streamed. File references are given at each step.

1. **App composes a `RunAgentInput`** (`HermesApp/src/agui/types.ts`) —
   `threadId`, `runId`, message history, the frontend tool declarations
   (`render_component`, `show_plan_card`, `show_media_card`, … from
   `src/device/frontendTools.ts`), and context items such as
   `{description: "model", value: "openai:gpt-5"}` from the Settings screen.
   It POSTs this to `/agent` with `Accept: text/event-stream` and the Bearer
   token (`src/agui/client.ts`, hand-rolled over `expo/fetch` because React
   Native's built-in fetch cannot stream).

2. **HTTP middleware** (`assistant/server/app.py`):
   - `refresh_connector_tools` — if the connector registry version changed
     since the last run, the AG-UI agent's graph is replaced with a freshly
     built one *before* the request proceeds (see §7).
   - `bearer_auth` — constant-time comparison against `settings.api_auth_token`;
     only `/health`, `/webhooks/whatsapp` and the Google OAuth routes are public.

3. **AG-UI endpoint** — `add_langgraph_fastapi_endpoint` (ag-ui-langgraph) wraps
   the compiled graph in a `LangGraphAGUIAgent` named `hermes`. It translates
   the run input into a LangGraph invocation on the thread's checkpoint and
   translates graph output into typed SSE events.

4. **Agent middleware chain** (order as registered in
   `assistant/agent/agent.py::build_assistant_graph`), on every model call:

   | Middleware | Hook | Effect |
   |---|---|---|
   | `CopilotKitMiddleware` | — | Bridges CopilotKit state (frontend tools, context items, shared `artifact` state key) into the run. |
   | `ModelSelectMiddleware` | `awrap_model_call` | Reads `model` from the forwarded AG-UI context; swaps in a cached `init_chat_model` instance for this run only. Unknown specs fall back to `settings.assistant_model`. |
   | `MemorySnapshotMiddleware` | `awrap_model_call` | Prepends the bounded MEMORY/USER files as a `SystemMessage`, **frozen per thread** (see §5). |
   | `Mem0Middleware` | `awrap_model_call` | Injects top-5 semantic recall into the latest **user message** inside a `<memory-context>` fence; after a final (tool-call-free) answer, persists the user/assistant pair to mem0 on a background executor. |
   | `SessionLogMiddleware` | `aafter_agent` | Mirrors new messages into `hermes.message_log`, upserts `hermes.threads` (title = first human message), and every `review_every_n_turns` (default 6) human turns spawns the background memory review (§5). |
   | `ReceiptMiddleware` | `awrap_tool_call` | After every tool execution, records an action receipt if the tool is consequential (§8). |

5. **The deep agent runs** — planning (`write_todos`), filesystem ops routed by
   the `CompositeBackend` (`/skills/` → Postgres store namespace
   `(user_id, "skills")`, `/workspace/` → disk under
   `assistant/data/workspace` or a Daytona/E2B/Modal sandbox when
   `sandbox_provider` is set, everything else → ephemeral graph state), and
   tool calls. Broad research is delegated to the `researcher` subagent;
   number-crunching to `analyst` (which runs on the cheap `review_model`)
   — both defined in `assistant/agent/subagents/__init__.py`.

6. **Tool execution paths** diverge by tool type:
   - *Backend tools* (Gmail, Calendar, WhatsApp, web, memory, artifacts,
     workspace, routines, session search) execute in-process.
   - *Device tools* (`assistant/tools/device.py`) enqueue a command and return
     immediately (§6).
   - *Frontend tools* (declared by the app in the run input) are not executed
     server-side at all — the `TOOL_CALL_*` events reach the app, which renders
     the generated component and returns the tool result on the follow-up run.
   - *Approval-gated tools* — `send_gmail`, `send_apple_mail`,
     `send_whatsapp_message`, `delete_calendar_event`,
     `install_mcp_connector`, `install_api_connector` — hit `interrupt_on`
     (chat tier only). The graph pauses on a LangGraph interrupt; the app's
     ApprovalSheet shows approve/edit/reject and resumes the run.

7. **Events stream back** as SSE frames (`HermesApp/src/agui/types.ts` mirrors
   `@ag-ui/core`): `RUN_STARTED`, `TEXT_MESSAGE_START/CONTENT/END` (streamed
   tokens), `TOOL_CALL_START/ARGS/END/RESULT`, `STATE_SNAPSHOT` /
   `STATE_DELTA` (RFC 6902 patches — this is how the `artifact` state key
   live-updates the ArtifactCanvas), `REASONING_*`, and finally
   `RUN_FINISHED` or `RUN_ERROR`. The app applies patches with
   `src/agui/jsonPatch.ts` and executes device `TOOL_CALL`s inline.

8. **After the reply** — the checkpointer has already persisted the full graph
   state per super-step; `SessionLogMiddleware` has mirrored the transcript;
   `Mem0Middleware` persists the exchange asynchronously; receipts are in the
   ledger. Nothing else needs to be flushed.

---

## 3. Trust tiers

One agent construction, three toolsets (`assistant/agent/agent.py`,
`assistant/tools/__init__.py`). Trust is enforced *structurally* — by which
tools exist in the graph — not by prompting.

| Tier | Entry point | Toolset | Connector tools | Approvals | Notes |
|---|---|---|---|---|---|
| **chat** | `POST /agent` (owner's app, Bearer-authenticated) | `BACKEND_TOOLS` + `DEVICE_TOOLS` + `APP_TOOLS` (connector self-install) | yes | `interrupt_on` for outbound sends, event deletion, connector installs | Full capability; the only tier with human-in-the-loop available. |
| **routine** | APScheduler cron fire (`_run_routine`) | `ROUTINE_RUN_TOOLS` (= core, **no routine management**) + `DEVICE_TOOLS` | yes | none (headless) | Each fire runs in a fresh thread `routine-<hex>` — no chat history. Removing the routine tools inside a routine is the recursion guard: a routine can never schedule more routines. Results go to push + receipt, never into chat threads. |
| **webhook** | `POST /webhooks/whatsapp` (untrusted inbound) | `WEBHOOK_TOOLS`: `search_web`, `fetch_web_page`, `list_calendar_events`, `find_free_time_slots`, `recall_memories`, `session_search` | **no** | none | Read-mostly, no outbound sends, no device control, no connectors — prompt-injection blast-radius control. Sender must equal `whatsapp_owner_phone` or the message is dropped. The reply is sent by the *server* (`_send_whatsapp_reply`) **outside the agent loop**, so the agent in this tier holds no send capability at all. |

All three tiers share the same middleware chain; `SessionLogMiddleware` and
`ReceiptMiddleware` tag rows with the tier as `source`, and the background
memory review only triggers from `chat`.

---

## 4. Persistence layout

Single Postgres instance (with pgvector), `settings.database_url`. Three
distinct owners write to it:

**1. `hermes` schema — application tables** (created idempotently by
`db.init_schema()` at startup; DDL in `assistant/db.py`):

| Table | Purpose |
|---|---|
| `hermes.routines` | id, name, cron, prompt, enabled, last_run_at, last_result. |
| `hermes.device_commands` | Device queue: name, JSONB payload, status `pending → delivered → done/failed`, result. |
| `hermes.device_tokens` | APNs device tokens registered by the app. |
| `hermes.message_log` | Transcript mirror for search: thread_id, source (chat/routine/webhook), role, content. Indexed `(thread_id, id)` plus a GIN full-text index on `to_tsvector('simple', content)`. |
| `hermes.threads` | Thread directory: title (first human message), source, updated_at. |
| `hermes.artifacts` | Artifacts and notes: kind (html/markdown/table/chart), content, version, thread_id, `space` (workspace node id). |
| `hermes.nodes` | Workspace tree: self-referencing parent_id (any depth, `ON DELETE CASCADE`), SF Symbol icon, `dashboard` (artifact id rendered as the folder's opening view). |
| `hermes.integrations` | Connectors: kind (mcp/openapi/builtin), JSONB config, enabled. |
| `hermes.receipts` | Action ledger: tool, summary, reversibility (full/partial/none), JSONB undo descriptor, source, undone, seen. |
| `hermes.push_log` | Proactive-push budget accounting. |
| `hermes.memory_files` | Exactly two rows, `MEMORY` and `USER` — the bounded memory files. |

Access goes through `db.query()` / `db.execute()` on a sync `psycopg_pool`
(tools run in worker threads); the server also keeps an async pool.

**2. LangGraph tables** (default schema) — created by
`setup_persistence()` in `assistant/agent/agent.py`, which opens a dedicated
async pool (autocommit, `prepare_threshold=0`, dict rows) and runs `.setup()`
on both components:

- `AsyncPostgresSaver` — checkpoint tables (`checkpoints`,
  `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`). This is
  conversational ground truth: full graph state per thread per super-step.
  `hermes.message_log` is only a searchable mirror.
- `AsyncPostgresStore` — key-value store tables (`store`,
  `store_migrations`). Backs the `/skills/` virtual path, i.e. agent-authored
  skills, under namespace `(settings.user_id, "skills")`.

**3. mem0** — in local mode (`MEM0_API_KEY` unset) mem0 uses the pgvector
provider with collection `hermes_memories` in the same database
(`assistant/memory/store.py::SemanticMemory._build`). With an API key it uses
the hosted mem0 platform instead and stores nothing locally.

---

## 5. Memory architecture

Three complementary layers (`assistant/memory/store.py`,
`assistant/tools/memory.py`, `assistant/tools/session_search.py`), governed by
one cache discipline inherited from the Hermes Agent design: **anything
dynamic is injected into the user message, never the cached system prefix; the
curated snapshot is frozen per thread.**

### 5.1 Bounded files — MEMORY and USER

- Two char-budgeted files in `hermes.memory_files`: `MEMORY` (agent notes,
  2,200 chars) and `USER` (user profile, 1,375 chars); limits in
  `assistant/config.py`.
- Entries are `§`-delimited. `manage_memory_file(file, action, text, old_text)`
  supports add / replace / remove, where replace/remove locate an entry by a
  unique substring. An over-limit write **fails with the current entries in
  the error**, so the agent can consolidate and retry in the same turn.
- `render()` prepends a usage header, e.g.
  `MEMORY (your personal notes) [64% — 1,408/2,200 chars]`, keeping budget
  pressure visible to the model.
- `MemorySnapshotMiddleware` renders both files once per thread, caches the
  string in-process (bounded to 500 threads), and inserts it as a
  `SystemMessage` on every model call. Frozen-per-thread means mid-session
  edits become visible in the *next* conversation — deliberate, for prompt
  cache stability.

### 5.2 mem0 semantic memory (pgvector)

- Unbounded long-tail facts. `Mem0Middleware` searches top-5 for each new user
  message and appends a fenced block to that user message:

  ```
  <memory-context>
  Background from long-term memory (may be irrelevant — use judgement):
  - Kevyn's sister Dana lives in Paris
  - User prefers window seats on flights
  </memory-context>
  ```

- After a final answer (an `AIMessage` with no tool calls), the clean user
  text (fence stripped) and the answer are persisted via
  `semantic_memory.add_conversation` on a single-worker
  `ThreadPoolExecutor` — mem0's own LLM-based fact extraction decides what to
  keep. Explicit control is available through the tools `remember_fact`,
  `recall_memories`, and `forget_memory`.

### 5.3 Session search

`session_search` (`assistant/tools/session_search.py`) is zero-LLM Postgres
full-text search over `hermes.message_log`, with three argument-inferred
modes: **discovery** (query → ranked threads with `ts_headline` snippets and
first/last-3-message "bookends"), **scroll** (thread_id → that conversation's
messages), and **browse** (no args → recent chat threads). Routine-run
sessions are demoted (rank × 0.3), not excluded.

### 5.4 Background review

`SessionLogMiddleware` counts human turns per thread; every 6 (chat tier only)
it calls `spawn_review` (`assistant/agent/review.py`), which runs a headless
`create_agent` on `settings.review_model` (Haiku-class) on a daemon thread with
**only** `manage_memory_file` and `remember_fact` available. It reviews a
tool-message-free digest of the conversation and routes facts: durable →
bounded files, long-tail → mem0, nothing → `"Nothing to save."`. It never
blocks the user's turn and never raises.

---

## 6. Device control paths

The phone is a tool target. Every device tool
(`assistant/tools/device.py`: `play_youtube_video`, `play_youtube_search`,
`open_iphone_app`, `run_iphone_shortcut`, `create_iphone_reminder`,
`show_on_iphone_map`) does the same thing: `device_queue.enqueue(name,
payload)` → insert into `hermes.device_commands` → fire an APNs doorbell →
return `{"dispatched": true, "command_id": …}` immediately. Delivery then
happens by whichever path is live first:

**Path A — live chat (instant).** The app is already consuming the run's SSE
stream, sees the device `TOOL_CALL` events, and executes at once via
`HermesApp/src/device/toolExecutor.ts` — deep links (`youtube://watch?v=…`,
`maps:?q=…`), EventKit reminders, or Apple Shortcuts via
`shortcuts://x-callback-url/run-shortcut` with `x-success`/`x-error` callbacks
back into the app (30 s timeout). It acknowledges with
`POST /device/results {command_id, status, output}`.

**Path B — zero-tap while away (doorbell).** `enqueue` also calls
`send_doorbell` (`assistant/server/push.py`): a time-sensitive APNs alert with
payload `{"type": "device_poll"}`. An iOS 26 notification automation runs the
**AI: Poll** shortcut, which calls `GET /device/next-command` — a single
atomic `UPDATE … RETURNING` that flips the oldest pending command to
`delivered` — executes it, and reports via `POST /device/results`. The app
also drains the queue on foreground (`drainDeviceQueue`, up to 5 commands).

**The shortcut pack** (`shortcuts/`, manifest at `GET /shortcuts/manifest`) is
how the agent acts *inside* other apps: AI: Setup, AI: Poll, AI: Send
iMessage, AI: Send Email, AI: Set Focus, AI: Timer, AI: Home Scene,
AI: Navigate, AI: Prefill WhatsApp. `run_iphone_shortcut` invokes any of these
(or anything else in the user's library) by exact name with JSON text input.

**Push budget.** Doorbells are user-initiated and exempt. Proactive
routine-result pushes are capped at 4 per rolling 24 h (`hermes.push_log`);
overflow is silent — the result still lands in the ledger and on the routine
row.

APNs itself is a minimal token-auth (`.p8`, ES256 JWT cached ~40 min) HTTP/2
client (`ApnsClient`); tokens are registered via `POST /device/register`.

---

## 7. Connectors and the hot-swap mechanism

A connector is a row in `hermes.integrations`:
`{kind: mcp | openapi | builtin, name, config, enabled}`
(`assistant/integrations/registry.py`).

- **mcp** — tools discovered live from any MCP server via
  `langchain-mcp-adapters` `MultiServerMCPClient`; transport inferred
  (`…/sse` → SSE, otherwise streamable HTTP), optional headers
  (`integrations/mcp.py`).
- **openapi** — the spec is fetched and every operation with a supported
  method becomes a `StructuredTool`: query/path parameters become typed args,
  JSON request bodies a `body` string arg; capped at `max_tools` (default 30)
  (`integrations/openapi.py`).
- **builtin** — a curated catalogue (`integrations/catalog.py`): Weather
  (Open-Meteo, keyless), Telegram, GitHub, Spotify — plain `@tool` closures
  over the stored config — plus Notion, which is really a hosted MCP entry
  (`mcp_url`) that `POST /apps` translates into an mcp connector.

**Hot swap.** The registry keeps a monotonically increasing `version`,
bumped by every add/enable/disable/remove (which also invalidates that
connector's tool cache). Two mechanisms make changes take effect on the very
next message, with no restart:

1. `get_assistant_graph(mode)` (`agent/agent.py`) caches compiled graphs keyed
   by `(mode, integration_registry.version)`. A version bump means a cache
   miss → connector tools are reloaded (`load_tools()`, failures degrade to an
   empty toolset, first connector wins on tool-name collisions) → a new graph
   is compiled and the cache is cleared down to the current version.
2. The `refresh_connector_tools` HTTP middleware (`server/app.py`) compares
   the version before each `/agent` request and re-points the mounted
   `LangGraphAGUIAgent.graph` at the current build.

Checkpointer and store are `lru_cache`d module singletons, so rebuilt graphs
share persistence — thread history survives every swap.

Connectors are installed three ways: the app's Connectors screen
(`GET/POST/PATCH/DELETE /apps`), the catalogue, or **by the agent itself** via
`install_mcp_connector` / `install_api_connector`
(`assistant/tools/apps.py`) — both gated behind `interrupt_on` approval, since
an install attaches arbitrary new tools. Secrets in configs are masked (`•••`)
in the `/apps` summary.

---

## 8. Receipts and the action ledger

The trust surface: the user can always see what the agent did, and unwind what
can be unwound (`assistant/agent/receipts.py`).

**Capture.** `ReceiptMiddleware.awrap_tool_call` runs after every tool
execution in every tier. If the tool is in the `_CONSEQUENTIAL` map (sends,
calendar changes, routine changes, notes/artifacts, workspace shaping,
connector installs, device actions, memory-file edits) and the result is not
an error, a receipt is inserted into `hermes.receipts` with:

- a one-line **summary** (verb + best identifying argument),
- a **reversibility** class — `full`, `partial`, or `none`,
- an optional **undo descriptor** `{kind, args}` derived from the tool's JSON
  result — e.g. `create_calendar_event` → `{kind: "delete_calendar_event",
  args: {event_id}}`; likewise for routines (delete/toggle), notes/artifacts
  (delete), and connectors (remove).

Failed tool calls leave no receipt, and receipt capture itself can never break
tool execution. Routine fires additionally insert a `routine_run` receipt so
headless activity is visible in the same ledger.

**Surface.** REST (`server/app.py`):

- `GET /ledger?unseen_only=true` — the app's "while you were away" list; each
  row carries `can_undo = (undo IS NOT NULL AND NOT undone)`.
- `POST /ledger/seen` — mark everything seen.
- `POST /ledger/{id}/undo` — `execute_undo` dispatches on the descriptor's
  `kind` (delete the calendar event, delete/toggle the routine, delete the
  artifact, remove the connector), then sets `undone = TRUE`. Undo is
  server-side and LLM-free.

The unseen count also heads the `/hub` payload, alongside the workspace tree,
recent threads, and enabled routines — the app's agent-composed home surface.

---

## 9. Supporting cast (brief)

- **Routines** (`assistant/routines/manager.py`) — cron + natural-language
  prompt, validated with `CronTrigger.from_crontab` at create time, scheduled
  on APScheduler (`misfire_grace_time=300`) in `settings.timezone`. Managed by
  chat tools (`create_routine`, `list_routines`, `pause_or_resume_routine`,
  `delete_routine`) and REST. Fires run the routine-tier graph headlessly;
  results update the row, insert a receipt, and (budget permitting) push.
- **Auth** — single-user Bearer token for the app; Google OAuth web flow
  (`server/oauth.py`) for Gmail/Calendar/YouTube; iCloud app-specific password
  for Apple Mail; WhatsApp Cloud API token with a webhook verify handshake.
- **Config** (`assistant/config.py`) — pydantic-settings over env /
  `assistant/.env`; defaults: model `anthropic:claude-sonnet-5`, review model
  Haiku-class, Postgres on `localhost:5433`, server port 8787.
- **Workspace & artifacts** — see `hermes.nodes` / `hermes.artifacts` above;
  artifacts flow through graph state (`Command(update={"artifact": …})` →
  `STATE_DELTA` → live canvas) *and* Postgres, and an artifact can be bound as
  a folder's dashboard (`as_dashboard`) to give a domain its own UI.
