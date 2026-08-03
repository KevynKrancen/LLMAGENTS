# Hermes UX Design — Philosophy and System

How the Hermes iPhone app (`HermesApp/`) is designed, why each mechanic exists,
and the exact tokens and components that implement it. Companion to
`ARCHITECTURE.md` (backend) and `API.md` (surface contracts); the rendered
walkthrough lives in `ui-gallery.html`.

---

## 1. The 2027 thesis

Every mainstream assistant app in 2025 was a chat window bolted onto a
conventional app: hamburger menu, settings tree, a sidebar of stale
conversations. Hermes is built on a different bet — the interface of a personal
agent is not something a designer ships once; it is something **the agent
composes, spends a bounded attention budget on, and lets you audit and
reverse**.

Three consequences follow, and every mechanic in this document traces back to
one of them:

1. **Composition.** The agent builds the surfaces: inline components are
   generated HTML (`render_component`), the workspace tree is grown by
   conversation (`shape_workspace`), folders acquire bespoke dashboard UIs
   (`create_artifact(as_dashboard=True)`). The app ships almost no fixed
   chrome; it ships a renderer.
2. **Attention.** Proactive contact is a scarce resource the system spends
   deliberately. Routine pushes draw from a hard budget of four per day
   (`_DAILY_PUSH_BUDGET = 4` in `assistant/server/push.py`); overflow lands
   silently in the ledger. Nothing nags.
3. **Audit and reverse.** Every consequential action leaves a receipt with a
   declared reversibility (`full` / `partial` / `none`) and, where possible, an
   executable undo descriptor (`assistant/agent/receipts.py`). Trust is not a
   promise in a prompt; it is a table the user can read and a button they can
   press.

## 2. Agentic-first principles

### Conversation does, UI keeps

The chat is where things *happen*; the rest of the app is where things *are
kept*. `app/index.tsx` is the whole app — one serene chat screen — and
everything else (Hub, workspace, artifacts, routines, connectors, settings) is
a view over state the agent produced. No screen in the app creates anything by
itself: there is no "new folder" button, no "new dashboard" wizard. You ask;
Hermes shapes.

### Propose-as-done

From the system prompt (`assistant/agent/prompt.py`):

> **Propose as done**: never ask "would you like me to…?". Stage the work
> first — the reply drafted, the event composed, the plan built — and present
> it for one-tap confirm. Effort is yours; the user only decides.

Mechanically: the agent does all the work up front, and LangGraph
`interrupt_on` gates only the irreversible boundary (outbound sends, connector
installs — see `_OUTBOUND_APPROVAL` in `assistant/agent/agent.py`). The
`ApprovalSheet` renders the fully-formed action ("Hermes wants to…" with the
exact arguments) and offers **Approve** / **Not now** — a decision, not a
form.

### Attention budget

Interruptions are priced. `send_routine_result` checks a rolling 24-hour
window against the budget of 4; doorbell pushes (which merely wake the device
executor after a user-initiated request) are exempt. A routine that fires when
the budget is spent still runs, still writes its receipt — it just doesn't
buzz the phone. The **away pill** (below) is the polite reconciliation
mechanism: everything missed is one tap away, never pushed.

### Receipts + reversibility

`ReceiptMiddleware` wraps every tool execution; tools listed in
`_CONSEQUENTIAL` produce a row in `hermes.receipts` with a one-line summary, a
reversibility class, and — when the tool result yields an id — an undo
descriptor (`delete_calendar_event`, `delete_routine`, `delete_artifact`,
`remove_connector`, `toggle_routine`). Failed calls leave no receipt. The app
exposes the ledger in the Hub with per-row **Undo**; `POST /ledger/{id}/undo`
executes the descriptor server-side. The visual grammar is deliberate: a
green dot for reversible actions, a bronze dot for irreversible ones, struck-
through text once undone.

### Agent-composed surfaces

The app's fixed chrome is intentionally close to nil: a top bar (menu glyph,
wordmark, avatar), a composer, and system chips tucked at the bottom of
sheets. Everything with content in it — Hub sections, workspace grid, folder
faces, inline cards — is data the agent produced. The UI's job is to render
what the agent keeps, faithfully and quietly.

---

## 3. Mechanics

### 3.1 The Hub replaces the sidebar

`src/components/Hub.tsx`; data from `GET /hub` (`assistant/server/app.py`).

A conventional sidebar answers "where are my chats?". The Hub answers the
question that actually matters for an agent: **"what has Hermes done, and what
does Hermes keep?"** It is a full-screen reveal over the chat (hamburger glyph,
title *"Hermes keeps"*), composed of:

| Section | Content | Source |
|---|---|---|
| WHILE YOU WERE AWAY | Last 8 receipts, with Undo where possible | `GET /ledger` |
| YOUR SPACE | The workspace tree the agent grew | `hub.workspace` (`_tree()`) |
| RHYTHMS | Up to 3 enabled routines with cron | `hub.routines` |
| CONVERSATIONS | Full-text search ("Search everything said", 250 ms debounce) + 4 recent threads + new-chat glyph | `GET /threads?query=` |
| System chips | Connectors · Artifacts · Settings | fixed routes |

Opening the Hub calls `POST /ledger/seen`, which is what retires the away
pill. Chats come *fourth* — deliberately. In an agentic app, conversation
history is an input log, not the product.

### 3.2 The away pill

`app/index.tsx`. When `hub.unseen_actions > 0` (unseen receipts), a hairline
pill floats under the top bar: *"3 things done while you were away"*, with a
small accent dot. Tapping it opens the Hub, whose ledger section answers it in
full and marks everything seen.

Rationale: this is the attention budget's other half. Autonomy without
visibility breeds distrust; visibility via push breeds fatigue. The pill is
pull-based disclosure — glanceable, dismissed by the act of looking, never a
badge count on an icon.

### 3.3 Alive components — `hermes://open` and `hermes://say`

`src/components/HtmlComponentCard.tsx`; declared to the agent as the
`render_component` frontend tool (`src/device/frontendTools.ts`); design rules
in the `component-design` skill
(`assistant/agent/skills/component-design/SKILL.md`).

For any data-rich answer the agent fetches real data, then renders a bespoke
self-contained HTML+CSS component inline in the chat — a weather card, an
inbox digest, a schedule — plus at most one line of text. The card renders in
a WebView that:

- injects the app's design tokens as CSS variables (`--bg --surface
  --surface-alt --text --subtle --accent --hairline --danger --success`) plus
  `color-scheme`, so generated UI matches the native theme in light and dark;
- auto-sizes to content via a `scrollHeight` postMessage + `ResizeObserver`
  (capped at 560 pt, scrolling internally beyond that);
- intercepts navigation (`onShouldStartLoadWithRequest`) and blocks everything
  except two schemes.

Those two schemes make components **alive, not pictures**:

- `hermes://open?url=<encoded>` — opens the phone: deep links
  (`youtube://watch?v=…`, `spotify:track:…`, `maps:?q=…`, https). A video
  result carries its own working ▶ button.
- `hermes://say?text=<encoded>` — speaks back to the agent as the user via
  `useChat.getState().send(text)`. An inbox digest row carries "summarize" /
  "reply" chips; a stat tile offers "details".

The skill keeps components under ~1600 characters of HTML, hairline-bordered,
shadow-free, using unicode glyphs (☀ ✉ ▲) rather than icon fonts — a native
widget's manners, not a webpage's.

### 3.4 Reshape long-press

Also `HtmlComponentCard.tsx`. Long-pressing any generated component reveals a
row of quiet chips — **Simpler · More detail · As a chart** — each of which
sends `"Reshape the last component: <option>."` back through the chat.

Rationale: if the agent composes the UI, the user must be able to send the UI
back to the workshop. Reshape is the smallest possible edit loop: no settings
panel, no layout editor — a spoken instruction bound to a gesture, keeping the
agent as the single renderer of record.

### 3.5 The workspace tree, grown by speech

Backend: `assistant/tools/workspace.py` (`shape_workspace`, `view_workspace`,
`save_note`). Frontend: `src/components/CapabilitySheet.tsx` (the ＋ sheet)
and `app/space/[id].tsx` (folder screens).

The workspace is a tree of folders at any depth, holding notes and artifacts.
It **starts empty** and is only ever shaped by conversation. Paths are the
interaction primitive: `save_note(path='Travel/Japan/Food')` materialises
every missing folder along the way (`_ensure_path`, case-insensitive `ILIKE`
matching). The agent is explicitly instructed never to invent structure the
user didn't ask for.

The ＋ sheet renders whatever tree exists — a 3-per-row grid of cells, drilled
in place via a trail stack; tap enters a folder, long-press opens its screen.
The empty state is an invitation, not a template:

> *Your space is unshaped. Tell Hermes what to keep and how to organize it —
> folders form themselves as you speak.*

A footer hint prefills the composer ("Make me a folder for …", or "Add a
folder inside *Travel* for …" when drilled in), reinforcing that speech is the
only shaping tool.

### 3.6 Folder dashboards — a folder's face

`create_artifact(kind='html', path='Finance/Polymarket', as_dashboard=True)`
sets `hermes.nodes.dashboard` to the artifact id
(`assistant/tools/artifacts.py`). When the user opens that folder
(`app/space/[id].tsx`), the dashboard artifact renders first — a 300 pt live
canvas — as the folder's opening view, excluded from the item list beneath
("the dashboard is the folder's face — don't repeat it in the list").

This is how a domain gets a specialised interface without an app update: the
`domain-builder` skill has the agent create the folder, a domain skill,
connectors, routines, and a custom HTML dashboard it keeps current with
`update_artifact`. A budget ledger with running totals, a positions table with
P&L, a lesson tracker — living UI, not a report. The app specialises itself
around what the agent builds.

### 3.7 SF Symbols only

`src/components/Symbol.tsx` (expo-symbols `SymbolView`, weight `light`).
Native chrome and workspace icons are SF Symbol names — `airplane`,
`banknote`, `graduationcap`, `folder` — validated by
`/^[a-z0-9]+(\.[a-z0-9]+)*$/`; anything that doesn't parse as a symbol name
(e.g. an emoji from older data) degrades to text, with `◇` as the last-resort
fallback. The `shape_workspace` docstring instructs the agent to emit SF
Symbol names, **never emoji**, when choosing folder icons.

Rationale: agent-chosen iconography must land inside Apple's visual system,
not beside it. One caveat by design: *inside* generated HTML components (a
WebView, where SF Symbols don't exist) the component-design skill prescribes
unicode glyphs instead — same restraint, different substrate.

### 3.8 Supporting mechanics

- **Approval sheet** (`ApprovalSheet.tsx`): bottom sheet titled "Hermes wants
  to…", listing each interrupted action with its literal arguments on a
  `surfaceAlt` slab. Approve (accent, success haptic) / Not now (warning
  haptic). Dismissing the sheet rejects — refusal is the default.
- **Tool activity chips** (`ToolActivityBar.tsx`): while the agent runs, up to
  three quiet hairline chips above the composer show friendly labels
  ("Searching the web…", "Checking your calendar…") from `TOOL_LABELS`; when
  none are active, the last completed chip lingers with a ✓.
- **Reasoning disclosure** (`MessageBubble.tsx`): assistant thinking streams
  behind a collapsed "▸ thinking" toggle — a 2 px left-bordered quote block in
  `subtle`, opt-in, never forced on the reader.
- **Morphing send** (`Composer.tsx`): the send button doesn't exist until
  there is text; it becomes an accent ↑, and while the agent runs it morphs
  into a stop ■. A centred micro model chip above the bar opens the provider/
  model sheet; changes apply on the next message, no restart.
- **Empty greeting** (`EmptyGreeting.tsx`): time-of-day greeting in New York
  serif ("Good morning, Kevyn" — "Up late" past midnight) over four suggestion
  chips. The first-run screen is a conversation opener, not a feature tour.

---

## 4. Design tokens

`HermesApp/src/theme/tokens.ts`. The stated intent, from the file itself:

> The look is deliberately quiet: warm off-whites, near-blacks, a refined
> bronze accent, hairline separators and generous whitespace. Every screen
> should feel airy — few borders, soft radii, restrained color.

### 4.1 Palette

| Token | Light | Dark | Role |
|---|---|---|---|
| `bg` | `#FAFAF8` | `#0C0C0E` | Screen background |
| `surface` | `#FFFFFF` | `#16161A` | Cards, sheets, composer |
| `surfaceAlt` | `#F4F3F0` | `#1D1D22` | Raised slabs, chips, inputs |
| `text` | `#111214` | `#F4F4F2` | Primary text |
| `subtle` | `#6B6E76` | `#9A9DA6` | Secondary text, labels, idle icons |
| `accent` | `#B08D57` | `#C9A265` | Bronze — actions, key figures, folder icons |
| `onAccent` | `#FFFFFF` | `#141414` | Text on accent |
| `hairline` | `#E7E5E0` | `#26262B` | Separators, borders |
| `danger` | `#C0392B` | `#E06C5B` | Errors, destructive |
| `success` | `#2E7D5B` | `#5BB08C` | Done, reversible receipts |
| `bubbleUser` | `#F1EADF` | `#242028` | User chat bubble tint |

Theme selection is automatic (`useTheme` → `useColorScheme`); there is no
manual toggle. The same palette is injected into every WebView (generated
components and dashboards) as CSS variables, so agent-composed HTML inherits
the theme for free.

Colour discipline: bronze accent for the *one* thing that matters on a
surface; `success`/`danger` only where they carry meaning; everything else is
text, subtle, and hairline. Borders are `StyleSheet.hairlineWidth` nearly
everywhere; the sole shadow in the system is `shadow.soft` (6% black, 12
radius, y-offset 4) on inline cards.

### 4.2 Spacing, radius, type

- **Spacing** — a 4 pt grid: `space(n) = n × 4`. Screen gutters sit at
  `space(4–5)` (16–20 pt); sections breathe at `space(6)`.
- **Radius** — `sm: 10`, `md: 14`, `lg: 20`. Cards and inputs use `md`;
  chips, sheets and bubbles use `lg`; the composer bar is `lg + 6`. The user
  bubble drops its bottom-right corner to `sm` for the tail.
- **Type scale** — `title: 28`, `heading: 20`, `body: 16`, `small: 13`,
  `micro: 11`. Titles, the wordmark and the greeting aspire to **New York**
  (Apple's serif, `titleFamily: 'NewYork'`), silently falling back to the
  system font where unregistered; everything else is the system sans. Section
  labels are `micro`, upper-case, letter-spaced 1.4 — quiet wayfinding.

---

## 5. Component inventory

`HermesApp/src/components/` — fifteen files, the entire component system.

| Component | Role |
|---|---|
| `Hub.tsx` | The agent-composed home surface: receipts + undo, workspace, routines, thread search, system chips |
| `Composer.tsx` | Input bar: ＋ capability button, model chip, morphing send/stop |
| `MessageBubble.tsx` | User bubble / full-width assistant turn, reasoning disclosure, card host |
| `ThemedMarkdown.tsx` | Token-styled markdown renderer for assistant prose |
| `GenCards.tsx` | Dispatch for `show_*` generative cards: plan, media, event, email draft, bar chart |
| `HtmlComponentCard.tsx` | `render_component` host: auto-sizing themed WebView, `hermes://` actions, reshape long-press |
| `ArtifactCanvas.tsx` | Live artifact renderer — html in a WebView; markdown, table, chart natively |
| `ApprovalSheet.tsx` | Native approve/reject for `interrupt_on` actions, with haptics |
| `CapabilitySheet.tsx` | The ＋ sheet: drill-in workspace grid, empty-state invitation, shaping hint |
| `MenuSheet.tsx` | Avatar menu: Artifacts, Routines, Connectors, Settings |
| `ModelSheet.tsx` | Provider + model picker, applied on next message |
| `Sheet.tsx` | Minimal bottom-sheet primitive (grabber, backdrop, slide) — no external dependency |
| `Symbol.tsx` | SF Symbol renderer with text fallback |
| `ToolActivityBar.tsx` | Quiet tool-progress chips above the composer |
| `EmptyGreeting.tsx` | Serene first-run state: serif greeting + suggestion chips |

Navigation (`app/_layout.tsx`, expo-router Stack, headers hidden): `index` is
the chat; `artifacts`, `routines`, `connectors`, `settings` present as modals;
`space/[id]` and `artifact/[id]` push. Expo SDK 57 / React Native 0.86;
`react-native-webview` for agent-composed HTML; `expo-symbols` for SF Symbols.

---

## 6. Microcopy

The writing is part of the design system: warm, spare, never system-ese.

- Hub title: **"Hermes keeps"** — the app named for what it does.
- Empty workspace: *"Unshaped — tell Hermes what to keep and it takes form
  here."*
- Away pill: *"3 things done while you were away"* — plain past tense, no
  exclamation.
- Approval heading: *"Hermes wants to…"* — the agent asks; the reject button
  is *"Not now"*, not "Cancel".
- Empty folder: *"Nothing here yet — tell Hermes to keep something in
  Travel."*
- Sections are nouns with character: **RHYTHMS**, not "Scheduled tasks".

The register is a good assistant's: states what happened, proposes what's
next, never pleads for attention.
