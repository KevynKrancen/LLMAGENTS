# IMPLEMENTATION.md — what was built, file by file

Session record of the Hermes build: every module, what it does, and what
was verified live. Companion to ARCHITECTURE.md (how it fits together)
and ROADMAP.md (what's next).

## Verified working (tested against live services in CI)

| Behavior | How it was verified |
|---|---|
| All 3 trust-tier graphs compile | `build_assistant_graph('chat'/'routine'/'webhook')` against live Postgres 16 |
| AG-UI endpoint streams | `POST /agent` → `RUN_STARTED`, `STEP_STARTED/FINISHED`, `STATE_SNAPSHOT` over SSE |
| REST + bearer auth | health/threads/routines CRUD/integrations status; 401 without token |
| Bounded memory files | add/replace/remove with usage headers; over-limit backpressure |
| Device queue | enqueue → claim (`delivered`) → result recorded |
| Connectors | Weather catalog app attaches 1 tool; local OpenAPI spec → 3 typed tools; hot-swap into chat graph confirmed by streaming run |
| Workspace tree | `Travel/Japan/Food` materialized from a path'd save_note; tree returns counts |
| Folder dashboards | `create_artifact(path=…, as_dashboard=True)` bound as `Finance/Budget`'s face |
| Receipts + undo | create_routine receipt recorded → `execute_undo` → marked undone |
| App typechecks | `tsc --noEmit` clean, strict mode, at every step |

Assumptions still to verify on first real run (see ROADMAP): interrupt
resume payload shape, REASONING event names from ag-ui-langgraph, mem0
pgvector first-write index creation.

## Backend — `assistant/`

- `config.py` — pydantic-settings; every credential/knob env-driven.
- `db.py` — psycopg sync+async pools; owns the `hermes` schema: `routines`,
  `device_commands`, `device_tokens`, `message_log` (+GIN FTS index),
  `threads`, `artifacts` (with `space`), `nodes` (workspace tree, cascade,
  `dashboard`), `integrations`, `receipts`, `push_log`, `memory_files`.
- `google_auth.py` — shared Gmail+Calendar OAuth (CLI flow + token cache).
- `agent/agent.py` — graph assembly: `create_deep_agent` with per-mode
  toolsets, CopilotKit AG-UI bridge, skills (bundled dirs + writable
  `/skills/` StoreBackend route), CompositeBackend (`/workspace/` →
  sandbox or disk), `AsyncPostgresSaver/Store` on lazily-opened pools
  (`setup_persistence()` from lifespan), `interrupt_on` approvals,
  version-keyed graph cache for connector hot-swap.
- `agent/prompt.py` — identity + capabilities + memory rules +
  propose-as-done + answers-are-UI + receipts awareness.
- `agent/middleware.py` — `ModelSelectMiddleware` (Settings-driven
  per-request model via `init_chat_model` cache), `MemorySnapshotMiddleware`
  (frozen bounded-files snapshot per thread), `Mem0Middleware` (semantic
  recall fenced into the user message; async persistence post-answer).
- `agent/session_log.py` — mirrors messages to Postgres (thread titles,
  FTS), triggers the background review every N user turns.
- `agent/review.py` — post-turn cheap-model review with memory-tools-only
  whitelist (Hermes Agent pattern).
- `agent/receipts.py` — consequential-tool registry, reversibility
  classes, undo descriptors (calendar/routine/artifact/connector),
  `execute_undo`, `ReceiptMiddleware` (`awrap_tool_call`).
- `agent/subagents/` — researcher (web) + analyst (cheap model).
- `agent/skills/` — planning, morning-brief, skill-authoring,
  domain-builder (the self-specialization recipe), component-design
  (generated-UI design system + hermes:// actions).
- `memory/store.py` — bounded `BoundedMemoryFile` (§-delimited, char
  budgets, unique-substring edits, loud overflow) + mem0 client (hosted
  or local pgvector).
- `tools/` — web, gmail, calendar (incl. free-slot finder), apple_mail
  (IMAP/SMTP), whatsapp (Cloud API), youtube, memory, session_search
  (discovery/scroll/browse), artifacts (path + as_dashboard, Command
  state updates), workspace (shape/view/save_note with path
  materialization), routines, device (queue-backed), apps (self-install
  connectors).
- `integrations/` — registry (Postgres, version counter, safe config
  masking), mcp.py (langchain-mcp-adapters), openapi.py (spec → typed
  StructuredTools), catalog.py (Weather/Telegram/GitHub/Spotify/Notion).
- `routines/manager.py` — APScheduler + Postgres; fresh thread per fire;
  recursion guard via toolset; receipt + budgeted push per run.
- `server/app.py` — lifespan (schema, persistence, AG-UI mount, scheduler),
  bearer auth middleware, connector hot-swap middleware, REST: threads,
  artifacts(space), workspace, hub, ledger(+seen/undo), routines CRUD,
  device register/next-command/results, shortcuts manifest, apps CRUD,
  WhatsApp webhook (owner-only, scoped tier, out-of-loop reply).
- `server/push.py` — APNs .p8 client; doorbells exempt from the 4/day
  budget; routine pushes budgeted with ledger fallback.
- `server/oauth.py` — Google web OAuth (`/auth/google/start|callback`) +
  `/integrations/status` for the Settings screen.
- `server/device_queue.py` — pending→delivered→done command lifecycle.

## iPhone app — `HermesApp/`

- `src/agui/` — types (event vocabulary incl. THINKING aliases), SSE
  parser (CRLF, multi-line data, [DONE]), streaming UTF-8 decoder with
  TextDecoder fallback, RFC-6902 patch (immutable), client on `expo/fetch`.
- `src/state/chat.ts` — the reducer: streaming text/reasoning, tool
  activity, card extraction, device-tool coordination via queue drain
  (single execution path), frontend-tool auto-continuation run, interrupt
  detection (`__interrupt__` walk) + resume via
  `forwardedProps.command.resume`, shared-state patches, thread load from
  message log.
- `src/state/settings.ts` — persisted server/auth/provider/model prefs.
- `src/api/rest.ts` — typed client for the whole REST surface.
- `src/device/` — frontendTools (render_component + show_* schemas, tool
  label map), toolExecutor (deep links, x-callback shortcuts with result
  wait, EventKit reminders, queue drain), push (APNs registration,
  doorbell handling).
- `src/components/` — Hub (ledger w/ undo, workspace, rhythms,
  conversations, system chips), HtmlComponentCard (auto-sizing sandboxed
  WebView, hermes://open + hermes://say bridge, long-press reshape),
  GenCards, MessageBubble, Composer (＋/model chip/morphing send),
  CapabilitySheet (workspace drill-in), ApprovalSheet, ModelSheet,
  ArtifactCanvas (live html/markdown/table/chart), Symbol (SF Symbols
  with fallback), Sheet, ThemedMarkdown, EmptyGreeting, ToolActivityBar.
- `app/` — index (home: away pill, chat, sheets), space/[id] (dashboard +
  subfolders + items), artifacts + artifact/[id] (live via shared state),
  routines, connectors, settings, _layout (URL + push wiring).

## Design decisions worth knowing

1. **Device commands go through the queue even in live chat** — the app
   drains on TOOL_CALL_END instead of executing directly, so live and
   headless paths share one execution record and never double-fire.
2. **Graphs are cached per (mode, connector-version)** and the AG-UI
   agent's `graph` attribute is swapped by middleware — connector installs
   apply on the next message without restart.
3. **Replies to WhatsApp are sent by the server, not by a tool** — the
   untrusted-inbound tier can never message anyone (Hermes Agent's rule).
4. **Receipts are written by middleware, not by tools** — tools stay pure;
   the consequential-tool registry is one place to audit.
5. **The app declares UI tools; the backend owns device tools** — UI cards
   round-trip through the frontend-tool contract; device actions are
   backend tools so routines can use them headlessly.
