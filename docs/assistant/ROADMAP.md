# ROADMAP.md — what exists, what's next

Companion to ARCHITECTURE.md (how it fits together) and IMPLEMENTATION.md
(what was built, file by file). This document is the forward plan: a
checklist of what is real today, a prioritised backlog with effort
estimates and implementation sketches, and the assumptions that still need
verifying on the first real end-to-end run.

Effort legend: **S** = under a day. **M** = two to four days. **L** = a
week or more, usually because native iOS work or a new external service is
involved.

---

## 1. What exists today

Everything below is implemented and referenced by module, not aspiration.

**Backend (`assistant/`)**

- [x] Deep agent on deepagents 0.7 (`create_deep_agent`) with three
  trust-tier toolsets — chat / routine / webhook — and a version-keyed
  graph cache for connector hot-swap (`agent/agent.py`,
  `tools/__init__.py`: `BACKEND_TOOLS`, `ROUTINE_RUN_TOOLS`,
  `WEBHOOK_TOOLS`).
- [x] AG-UI protocol endpoint over SSE via `LangGraphAGUIAgent` +
  `add_langgraph_fastapi_endpoint` at `POST /agent`, plus the REST surface
  (threads, artifacts, routines, device queue, ledger, hub, connectors,
  shortcuts manifest) (`server/app.py`).
- [x] Three-layer memory: bounded §-delimited MEMORY/USER files with char
  budgets (`memory/store.py`: `BoundedMemoryFile`), mem0 semantic memory on
  pgvector (`memory/store.py`: `SemanticMemory`), and zero-LLM full-text
  session search (`tools/session_search.py`). Injection is cache-safe:
  frozen snapshot per thread + per-turn recall fenced into the user message
  (`agent/middleware.py`), with a cheap-model post-turn review every N
  turns (`agent/review.py`, `agent/session_log.py`).
- [x] Routines: cron + natural-language prompt, APScheduler, fresh thread
  per fire, results pushed within a daily budget of 4 proactive
  notifications (`routines/manager.py`, `server/push.py`).
- [x] Device queue + APNs doorbell: tools enqueue commands
  (`tools/device.py` → `server/device_queue.py`), a doorbell push wakes
  either the app or the iOS 26 notification automation → `AI: Poll`
  shortcut (`server/push.py`, `shortcuts/README.md`).
- [x] Connectors platform: MCP servers, OpenAPI specs, and a curated
  builtin catalog become live tools without a restart
  (`integrations/registry.py`, `mcp.py`, `openapi.py`, `catalog.py`);
  agent-driven installs are gated behind `interrupt_on` approval
  (`tools/apps.py`, `agent/agent.py`: `_OUTBOUND_APPROVAL`).
- [x] Workspace tree + folder dashboards: an agent-shaped hierarchy with
  artifacts as folder "faces" (`tools/workspace.py`, `tools/artifacts.py`,
  `hermes.nodes.dashboard`).
- [x] Action receipts ledger with reversibility classes and executable undo
  descriptors (`agent/receipts.py`; `/ledger` routes in `server/app.py`).
- [x] Subagents (researcher, analyst) and bundled skills (planning,
  morning-brief, skill-authoring, domain-builder, component-design)
  (`agent/subagents/`, `agent/skills/`), plus agent-authored skills in the
  writable `/skills/` StoreBackend route.
- [x] WhatsApp webhook tier: owner-only inbound, scoped read-mostly
  toolset, replies sent outside the agent loop (`server/app.py`:
  `whatsapp_inbound`).

**App (`HermesApp/`, Expo 57 / RN 0.86)**

- [x] Hand-rolled AG-UI SSE client on `expo/fetch` with typed event
  normalisation, including THINKING_* → REASONING_* aliases
  (`src/agui/client.ts`, `sse.ts`, `types.ts`, `jsonPatch.ts`).
- [x] Chat store reducing the event stream: streaming text and reasoning,
  tool activity chips, STATE_DELTA shared state, interrupt detection and
  resume (`src/state/chat.ts`).
- [x] Generated live components: freeform `render_component` HTML in an
  auto-sizing themed WebView with `hermes://say` / `hermes://open` action
  URLs and long-press reshape (`src/components/HtmlComponentCard.tsx`),
  plus typed cards — plan, media, event, email draft, bar chart
  (`src/components/GenCards.tsx`, `src/device/frontendTools.ts`).
- [x] Hub (receipts + undo, workspace, chats), approval sheet for
  `interrupt_on` actions, artifact canvas (html/markdown/table/chart),
  spaces with dashboards, connectors and routines screens
  (`src/components/Hub.tsx`, `ApprovalSheet.tsx`, `ArtifactCanvas.tsx`,
  `app/space/[id].tsx`, `app/connectors.tsx`, `app/routines.tsx`).
- [x] Device executor: deep links, x-callback shortcut runs, EventKit
  reminders; fed by both the live TOOL_CALL stream and the polled queue
  (`src/device/toolExecutor.ts`); APNs registration + doorbell handling
  (`src/device/push.ts`).

**Shortcuts (`shortcuts/`)**

- [x] Documented pack: `AI: Setup`, `AI: Poll`, senders (iMessage, email),
  focus, timer, HomeKit, navigation, WhatsApp prefill — with the iOS 26
  notification-automation zero-tap path (`shortcuts/README.md`).

---

## 2. What to build next (priority order)

### 2.1 Live Activities / Dynamic Island agent status — **M**

**Why.** The agent already runs long multi-tool turns and headless
routines, but the phone shows nothing between "sent" and "done". A Live
Activity turns the Dynamic Island into an agent status line: *thinking →
Searching the web → Sending email → needs approval*.

**Sketch.**
- Evaluate `voltra` and `react-native-activity-kit` (both wrap
  ActivityKit for Expo via config plugins); whichever is chosen, the
  Activity attributes are small: `{runId, phase, toolLabel, detail}`.
  `toolLabel` reuses `TOOL_LABELS` from `src/device/frontendTools.ts`.
- Foreground path: start/update the activity from the chat reducer in
  `src/state/chat.ts` on `RUN_STARTED` / `TOOL_CALL_START` /
  `RUN_FINISHED` — no server change needed.
- Background path (the interesting one): push-updated activities.
  iOS 17.2+ issues a *push-to-start* token; register it via a new
  `POST /device/activity-token` next to `POST /device/register`
  (`server/app.py`), stored in a new `hermes.activity_tokens` table
  (`db.py`).
- Extend `ApnsClient.send` (`server/push.py`) — it currently hardcodes
  `apns-push-type: alert` — with a `send_activity(event, state)` method
  using `apns-push-type: liveactivity` and topic
  `{bundle_id}.push-type.liveactivity`.
- Drive updates from a tiny middleware next to `ReceiptMiddleware`
  (`agent/receipts.py` shows the `awrap_tool_call` pattern): on tool
  start/end, post a throttled activity update (≥2 s apart; APNs will
  drop-floor spammy activity pushes). Routine fires
  (`routines/manager.py:_fire`) start an activity, end it with the result
  summary.
- Approval states: when `interrupt_on` fires, flip the activity to
  "Waiting for approval" — the island becomes the approval prompt's
  attention hook, the app's `ApprovalSheet` remains the actual control.

### 2.2 Typed component grammar (A2UI v0.9 / json-render) — **M–L**

**Why.** `render_component` today is freeform HTML in a WebView
(`HtmlComponentCard.tsx`). It works, but it is unverifiable (the model can
emit anything), non-native (WebView per card), and unstylable at the
system level. A typed component grammar — an A2UI v0.9-style JSON
component tree — makes generated UI machine-checkable and natively
rendered.

**Sketch.**
- Define the grammar once, enforce it twice: a JSON Schema for a small
  component set — `Column`, `Row`, `Text`, `Stat`, `List`, `ListItem`,
  `Chip`, `Button`, `Image`, `Divider`, `ProgressBar`, `Chart` — each with
  a closed prop set and an optional `action` binding
  (`{say: string} | {open: url}`), mirroring the existing `hermes://say` /
  `hermes://open` semantics.
- App side: declare a new frontend tool `render_ui` in
  `src/device/frontendTools.ts` whose `parameters` *is* the grammar (the
  model sees the schema as the tool signature — that alone removes most
  malformed output). Validate the parsed args with zod, then render with a
  ~200-line recursive `JsonComponent` renderer next to `GenCards.tsx` —
  native views, theme tokens from `src/theme/tokens.ts`, no WebView.
- Backend side: add the same schema as a pydantic model under
  `assistant/agent/` so headless surfaces (routine results, future
  Mac/watch clients) can validate and re-render the same trees; update the
  `component-design` skill (`agent/skills/component-design`) to teach the
  grammar instead of raw HTML.
- Migration: keep `render_component` as the escape hatch for genuinely
  bespoke layouts; the skill should steer the model to `render_ui` first.
  Version the grammar (`"v": 1`) in the payload from day one so later
  A2UI-proper alignment is a renderer change, not a data migration.

### 2.3 App Intents — let iOS 27 Siri drive Hermes — **M–L**

**Why.** Siri's AI layer composes App Intents. Exposing Hermes as intents
means "Ask Hermes to move my 3pm" works from the lock screen, CarPlay,
and AirPods without opening the app.

**Sketch.**
- App Intents must be compiled Swift inside the app target. Under Expo,
  add a native target via a config plugin (e.g. `@bacons/apple-targets`
  or a bespoke plugin) — this forces a dev-client / EAS build, no more
  Expo Go, so batch it with the Live Activities work (2.1) which has the
  same constraint.
- Define `AskHermesIntent` (`@Parameter var request: String`) returning
  `ProvidesDialog & ShowsSnippetView`. Implementation: POST to the
  backend with the stored server URL + bearer token. The backend already
  has the right primitive — `_run_headless` in `server/app.py` — so add a
  thin `POST /ask {prompt}` route that runs the **chat** graph headlessly
  and returns `{text}`. Keep it under the same bearer auth.
- Snippet view: render the answer text; once 2.2 exists, a `render_ui`
  tree can map to a SwiftUI snippet for rich results.
- Add `AppShortcutsProvider` phrases ("Ask Hermes", "Hermes, …") so the
  intents surface without setup. Scope carefully: intents run without the
  approval sheet, so `/ask` should use a toolset without outbound sends
  (reuse the `WEBHOOK_TOOLS` tier or a new `siri` tier in
  `tools/__init__.py`) until per-domain autonomy (2.4) exists.
- Interim zero-code path (already possible today): a Shortcuts shortcut
  hitting `/ask` gets Siri voice invocation on current iOS.

### 2.4 Earned per-domain autonomy levels — **M**

**Why.** Approval today is static: `_OUTBOUND_APPROVAL` in
`agent/agent.py` always interrupts for sends and installs. Trust should be
earned per domain: *ask-first → act-and-notify → silent*, advancing on
approval history, dropping instantly on an undo.

**Sketch.**
- Schema: `hermes.autonomy (domain text pk, level int, streak int,
  updated_at)` in `db.py`. Domains map from tools: `email.send`,
  `whatsapp.send`, `calendar.delete`, `connector.install` — a
  `_DOMAIN_OF: dict[tool, domain]` next to `_CONSEQUENTIAL` in
  `agent/receipts.py`.
- Signals in, both already flow through code we own:
  - Approvals: when the app resumes an interrupt with `approve` (and no
    edit), bump the domain streak; `edit`/`reject` reset it to 0.
    Cleanest hook: a small `POST /autonomy/feedback` the app calls from
    `resolveInterrupt` in `src/state/chat.ts`, since decision payloads are
    consumed inside LangGraph.
  - Undo: `execute_undo` (`agent/receipts.py`) drops the receipt's domain
    one level and zeroes the streak — undo is the strongest trust signal.
- Promotion rule: streak ≥ 5 → ask-first becomes act-and-notify; a
  further 10 clean act-and-notify actions (no undo) → silent. Store the
  thresholds in `config.py`.
- Enforcement: `interrupt_on` is fixed at graph construction, so compute
  the interrupt map from the autonomy table at build time and key the
  graph cache on an `autonomy_version` counter exactly as connector
  changes already do (`_graph_cache` keyed on
  `integration_registry.version` in `agent/agent.py`) — a level change
  rebuilds on the next message.
- Notification tier: act-and-notify = execute, then a receipt-referencing
  push through the existing budget (`send_routine_result` pattern in
  `server/push.py`); silent = ledger only. The ledger already surfaces
  everything with undo, which is what makes this safe.

### 2.5 Voice: show-while-telling — **L**

**Why.** The generated-UI investment pays double in voice: Hermes speaks a
summary while streaming the full card to the screen — the phone in your
hand shows the inbox digest as the voice says "three things need replies".

**Sketch.**
- Input: `expo-speech-recognition` (on-device SFSpeechRecognizer) behind a
  mic button in `Composer.tsx`; transcript lands in the existing `send()`.
- Output: buffer `TEXT_MESSAGE_CONTENT` deltas in the chat reducer into
  sentence-sized chunks; speak each completed sentence with `expo-speech`
  while the same deltas render as text. Cards (`render_component` /
  `render_ui`) keep streaming visually — voice mode changes nothing about
  the event flow, only adds a TTS sink.
- Barge-in: mic re-activation stops TTS and calls the existing
  `stop()` (`abortController` in `src/state/chat.ts`).
- Prompting: a `voice_mode` context item (the `contextItems()` mechanism
  already forwards `model` and `memory_enabled`) telling the agent to keep
  spoken prose short and push detail into components.
- Upgrade path: a realtime speech-to-speech provider later replaces the
  STT/TTS ends without touching the AG-UI middle.

### 2.6 Affordance-rich intent input: parameter chips under the composer — **S–M**

**Why.** The composer is a bare text field. As the user types "remind me
to…", Hermes can show what it *understood* — chips like
`⏰ tomorrow 9:00` `📝 call the bank` — editable before send. Affordances
build trust before the run starts.

**Sketch.**
- Backend: `POST /intent/preview {text}` → `{intent, params:
  [{key, value, confidence}], missing: [key]}` using the cheap
  `review_model` (already configured in `config.py`) with a strict JSON
  schema; no tools, ~300 ms.
- App: debounce composer input 400 ms (`Composer.tsx` already receives
  prefills via `prefill`/`onPrefillConsumed`, so the chip row slots in
  above it); render chips from the preview; tapping a chip opens inline
  edit; a chip for a `missing` param renders hollow as a prompt.
- On send, pass the confirmed structure as a context item
  (`contextItems()` in `src/state/chat.ts`) so the agent starts from
  resolved parameters instead of re-parsing.
- Cache previews by text prefix; drop the request on every keystroke that
  extends a still-in-flight one.

### 2.7 Pushcut Automation Server tier: guaranteed zero-tap — **S**

**Why.** The current zero-tap path (APNs doorbell → notification
automation → `AI: Poll`) is best-effort: it needs the notification
delivered and, for some actions, an unlocked phone. Pushcut Automation
Server (a dedicated always-on iOS device) executes shortcuts
server-triggered, guaranteed.

**Sketch.**
- Config: `pushcut_api_key`, `pushcut_fallback_seconds` (default 60) in
  `config.py`.
- Escalation, not replacement: `device_queue.enqueue` keeps the doorbell;
  a background task (the APScheduler instance in `routines/manager.py` is
  already running — add a repeating sweep job) finds commands still
  `pending` after the fallback window and fires
  `POST https://api.pushcut.io/v1/execute` (API-Key header) naming the
  matching `AI: *` shortcut with the payload as input.
- The shortcut's existing report block (`POST /device/results`,
  `shortcuts/README.md`) already closes the loop, so `record_result`
  needs no change; add a `via` column on `hermes.device_commands` for
  `queue | pushcut` observability in the ledger.

### 2.8 Ephemeral micro-app lifecycle: pin or dissolve — **S–M**

**Why.** The agent generates dashboards and mini-apps freely
(`create_artifact(as_dashboard=True)`), which means accretion. Micro-apps
should behave like foam: useful instantly, gone unless pinned.

**Sketch.**
- Schema: `pinned boolean default false`, `expires_at timestamptz` on
  `hermes.artifacts` (`db.py`). `create_artifact` (`tools/artifacts.py`)
  sets `expires_at = now() + 14 days` for `html` artifacts and dashboards;
  `markdown` notes keep no expiry.
- Touch-to-live: `update_artifact` and every render fetch push
  `expires_at` forward — things in use never dissolve.
- Pin: a pin action on `ArtifactCanvas.tsx` / the artifacts list →
  `PATCH /artifacts/{id} {pinned}` (new route in `server/app.py`);
  pinned ⇒ `expires_at` null.
- Dissolve: a nightly sweep job on the shared APScheduler soft-deletes
  expired artifacts and writes a `dissolve_artifact` receipt with an undo
  descriptor (restore = clear deleted flag) — dissolution becomes visible
  and reversible in the ledger like every other consequential action
  (`agent/receipts.py`).
- Hub: an "Expiring soon" strip in `Hub.tsx` is the pin affordance.

### 2.9 Multi-device: Mac, iPad, second iPhone — **M–L**

**Why.** The backend is already device-plural in places
(`hermes.device_tokens` holds any number of tokens; pushes fan out), but
commands are anonymous: "play on the iPad" is not expressible.

**Sketch.**
- Device identity: extend registration to
  `POST /device/register {token, device_id, name, platform,
  capabilities}` and the table accordingly; the app sends a stable
  installation id (`src/device/push.ts`).
- Targeted queue: `target_device` column on `hermes.device_commands`;
  `next_pending` (`server/device_queue.py`) takes a `device_id` query
  param and claims only matching-or-untargeted commands; device tools
  (`tools/device.py`) gain an optional `device` argument, resolved by
  name.
- iPad: mostly free — enable `supportsTablet` and audit the two-pane
  chances (chat + artifact canvas side by side) in `app/_layout.tsx`.
- Mac: fastest credible path is a thin menu-bar client speaking the same
  AG-UI protocol (`/agent` is transport-agnostic SSE) rather than
  Catalyst; it registers as a device with
  `capabilities: ["shell", "applescript"]`, which makes the device queue
  genuinely interesting — the agent gains a Mac executor with the same
  receipts/approval discipline.

### 2.10 Hosted deployment + backups — **M**

**Why.** Everything currently assumes a machine on the home network
(`SETUP.md`). One outage during a routine window and trust in proactivity
drains.

**Sketch.**
- Observability first (near-zero effort): set `LANGSMITH_API_KEY` +
  `LANGSMITH_TRACING` env vars — the LangGraph stack traces every run,
  including routine and webhook tiers, with no code change.
- Hosting: two viable shapes.
  1. **VM/container as-is** — the FastAPI app is self-contained
     (`uvicorn assistant.server.app:app`); deploy with the existing
     `assistant/docker-compose.yml` Postgres or a managed
     pgvector-capable Postgres (Neon/Supabase/RDS). Simplest; keeps the
     device queue, webhooks, and APScheduler in one process.
  2. **LangGraph Platform (LangSmith deployment)** for the graph itself —
     note the caveats before choosing it: the platform owns
     checkpointing (the `AsyncPostgresSaver` wiring in `agent/agent.py`
     changes), and the non-graph surface (device queue, `/webhooks/*`,
     APNs, APScheduler routines) must either move into platform custom
     routes or stay behind as a sidecar service. Estimate assumes shape
     1 first, revisiting 2 when scale demands it.
- Backups: nightly `pg_dump` of the `hermes` schema *and* the LangGraph
  checkpoint tables to object storage; the mem0 pgvector collection
  (`hermes_memories`) lives in the same database, so one dump covers
  chat history, memory, receipts, and workspace. Test the restore, not
  the dump.
- Production APNs: flip `apns_use_sandbox=false` (`config.py`) and verify
  token-based auth against the production gateway; sandbox and production
  device tokens differ.

---

## 3. Known gaps and assumptions to verify on the first real run

These were built against documented behaviour but not yet exercised
end-to-end against live services. Check them in this order — each one can
silently degrade rather than crash.

1. **Interrupt resume format.** The app resumes approvals with
   `forwardedProps: {command: {resume: [{type: "approve" | "edit" |
   "reject", args?}]}}` (`resolveInterrupt`, `src/state/chat.ts`),
   matching the HumanInTheLoopMiddleware decision format. Verify: (a) the
   installed `ag-ui-langgraph` actually maps `forwardedProps.command`
   onto a LangGraph `Command(resume=…)`; (b) decision list order matches
   the interrupt's request order; (c) the `edit` decision shape
   (`{type: "edit", args}`) is what the middleware expects.
2. **Interrupt surfacing.** `extractInterrupt` walks RAW/CUSTOM events for
   `__interrupt__` / `action_request` markers — deliberately loose.
   Confirm which event type the interrupt actually arrives on and tighten
   the detector once observed.
3. **AG-UI event details.** `normalizeEvent` (`src/agui/types.ts`) aliases
   THINKING_* → REASONING_*; verify the reasoning event names the
   installed `ag-ui-langgraph` emits, that `TOOL_CALL_RESULT` events are
   delivered (the wire history depends on them), and that `STATE_DELTA`
   JSON Patch paths match the `sharedState` shape the app maintains.
4. **mem0 first-run pgvector index.** Local mode
   (`Memory.from_config` with the `pgvector` provider,
   `memory/store.py`) must create the `hermes_memories` collection and
   requires the `vector` extension — the Docker image
   (`assistant/docker-compose.yml`) ships it, but the *first* `add()`
   pays index-creation latency and needs DDL privileges. Also note
   mem0's default embedder is OpenAI: `OPENAI_API_KEY` must be set even
   when `assistant_model` is Anthropic, or an explicit `embedder` block
   must be added to the config dict.
5. **Session-log offset arithmetic.** `SessionLogMiddleware._log`
   (`agent/session_log.py`) slices `fresh = messages[already:]` where
   `already` counts *logged rows* — but only messages with non-empty text
   are inserted, so tool-call-only messages skew the offset and can
   duplicate log rows on later turns. Harmless for search, wrong for
   counts; fix by tracking the last-logged message id instead.
6. **APNs HTTP/2 dependency.** `httpx.Client(http2=True)`
   (`server/push.py`) requires the `h2` extra (`httpx[http2]`); without
   it the first doorbell raises at runtime, not import time.
7. **Thread rehydration is lossy.** `loadThread` (`src/state/chat.ts`)
   rebuilds only human/ai text from `hermes.message_log` — generated
   cards, tool results, and shared state are not restored, so a resumed
   thread continues correctly but *renders* thinner than it was. Decide
   whether to persist card payloads (cheap: log `render_*` args) before
   users notice.
8. **Shortcut x-callback while locked.** `runShortcut`
   (`src/device/toolExecutor.ts`) resolves via the app's return URL and
   times out after 30 s — with the phone locked, results arrive as
   `no result (timed out)` even when the shortcut ran. The Pushcut tier
   (2.7) and the `AI: Poll` report block are the honest paths for
   unattended execution; treat in-app x-callback results as
   foreground-only.
9. **Doorbell pushes are visible.** The doorbell is an alert push
   (`apns-push-type: alert`, `server/push.py`) because the iOS 26
   notification automation only fires on delivered, visible
   notifications. Verify the automation triggers reliably with
   `interruption-level: time-sensitive`, and accept that zero-tap is not
   zero-noise until the Live Activities work (2.1) gives status a home.
