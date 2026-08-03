# Skills and Memory — the intelligence layer

How Hermes stays expert (skills) and stays personal (memory). This document
covers the five bundled skills, the self-authoring loop that lets the agent
write its own skills into a Postgres-backed store, the three-layer memory
system, per-turn injection mechanics and their cache discipline, the post-turn
background review, and the house rules for writing a new skill.

Source files covered:

| Concern | File |
|---|---|
| Bundled skills | `assistant/agent/skills/*/SKILL.md` |
| Skill sources + writable `/skills/` route | `assistant/agent/agent.py` |
| Bounded files + mem0 client | `assistant/memory/store.py` |
| Per-turn injection middleware | `assistant/agent/middleware.py` |
| Post-turn review | `assistant/agent/review.py`, `assistant/agent/session_log.py` |
| Memory tools | `assistant/tools/memory.py` |
| Session search | `assistant/tools/session_search.py` |
| Budgets and cadence | `assistant/config.py` |

For the surrounding system (trust tiers, persistence layout, request
lifecycle) see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. How skills load

Skills are DeepAgents **Agent Skills**: directories containing a `SKILL.md`
with YAML frontmatter, surfaced to the model by `SkillsMiddleware` via
progressive disclosure — the system prompt carries only an index of
`name: description` pairs plus each skill's path; the agent calls `read_file`
on a skill's `SKILL.md` when (and only when) the task matches its description.

`build_assistant_graph()` wires two sources, in order:

```python
# assistant/agent/agent.py
skills=[str(_SKILLS_DIR), "/skills/"],  # bundled (read-only) + agent-authored (writable)
```

- **Bundled** — `assistant/agent/skills/`, shipped with the repo, edited only
  by humans in git.
- **Agent-authored** — the virtual path `/skills/`, which the
  `CompositeBackend` routes to a `StoreBackend` (§3). Writable by the agent
  through the ordinary file tools.

Loading behaviour (DeepAgents 0.7 `SkillsMiddleware`):

- Sources are scanned in `before_agent`, **once per thread** — the resulting
  `skills_metadata` is checkpointed in graph state and the scan is skipped on
  every subsequent turn of that conversation. A skill written mid-session
  therefore becomes loadable in the **next** conversation, which is exactly
  what the domain-builder skill promises ("next session you reload it
  automatically").
- Sources load in order and **later sources win** on a name collision. Since
  `/skills/` is listed second, an agent-authored skill named
  `component-design` would shadow the bundled one — this is the mechanism
  behind skill-authoring's instruction to *update* a deficient skill rather
  than write a near-duplicate under a new name.
- Frontmatter is validated per the Agent Skills specification: `name` must be
  1–64 chars, lowercase alphanumeric plus hyphens, and must match the parent
  directory name; `description` is required. A missing `name` or
  `description` skips the skill with a logged warning.

The auto-added general-purpose subagent inherits the same skill sources; the
explicit `researcher` and `analyst` subagents
(`assistant/agent/subagents/__init__.py`) declare none and see no skills.

---

## 2. The bundled skills

Five skills ship in `assistant/agent/skills/`. Each is a single `SKILL.md`
(no helper scripts). Frontmatter is minimal: `name` + `description`.

### 2.1 `domain-builder` — self-specialisation

**Fires when** the user asks for a new *capability* rather than an answer:
"help me invest on Polymarket", "be my budget coach", "teach me linear
algebra". Also referenced directly from the system prompt's *Specialized
domains* bullet, so the main agent reaches for it without being asked.

**Purpose**: turn a capability request into a persistent **domain** — five
artefacts built in a fixed order:

1. **Folder** — `shape_workspace` a home (e.g. `Finance/Polymarket`); all
   domain output files under it.
2. **Skill** — write `/skills/<domain>/SKILL.md` capturing the user's goals,
   the procedure, APIs and pitfalls. This is the step that makes the
   expertise permanent across sessions.
3. **Connectors** — `install_mcp_connector` / `install_api_connector` for
   live data or actions (both interrupt for user approval); web search as
   fallback.
4. **Routines** — recurring behaviour becomes `create_routine` with a
   self-contained prompt (e.g. a 21:00 daily expenses check-in).
5. **Dashboard** — `create_artifact(kind='html', path=<folder>,
   as_dashboard=true)`; the folder's custom UI, updated whenever domain data
   changes.

**Hard rules baked in**: at most one clarifying question before building;
money/trading domains never place a trade or move funds without a per-action
approval, and every action goes in the domain ledger; durable user goals go
to memory (`manage_memory_file`), operational detail stays in the domain
skill.

### 2.2 `component-design` — answers as living UI

**Fires when** presenting any data-rich answer in chat: weather, inbox
digests, schedules, stats, comparisons. The system prompt's *Answers are UI*
rule points at it by name.

**Purpose**: pair one short conversational sentence with a `render_component`
call producing a self-contained HTML+CSS card. Key constraints:

- Use the injected CSS variables (`--bg --surface --surface-alt --text
  --subtle --accent --hairline --danger --success`) so components match the
  app in light and dark; no external images, fonts, or network calls; no
  JavaScript.
- Calm, high-end look: 14–18px padding, 12–14px radii, hairline borders, one
  big fact (26–34px, weight 600), colour only where it means something.
- Named layout patterns for weather, inbox digest, schedule and stat tiles.
- **Actions**: components are alive, not pictures. Two link schemes —
  `hermes://open?url=…` (open apps/deep links on the phone) and
  `hermes://say?text=…` (send a message back to the agent as the user) —
  turn a digest row into a "summarize" chip or a video card into a real play
  button.
- Keep components under ~1,600 chars of HTML; native widget, not a webpage.

### 2.3 `morning-brief` — the daily digest

**Fires** for routine runs and for "what's my day" style questions.

**Purpose**: a fixed four-section composition, skipping empty sections:
**Today** (`list_calendar_events(days_ahead=1)`, times + titles), **Inbox**
(`list_gmail_messages("in:inbox is:unread newer_than:1d")` plus unread Apple
Mail, people over newsletters), **Weather** (one line via `search_web`), and
**Heads-up** (`recall_memories("upcoming deadlines birthdays goals")`, at
most one timely item). Under 120 words, bold section labels, no preamble —
because on a routine run the text *is* the APNs push notification body, so it
leads with the single most useful fact.

### 2.4 `planning` — multi-step work and goals

**Fires** for "plan my week", "help me organize", goal tracking, or any
multi-step request.

**Purpose**: three procedures — (1) `write_todos` before acting on
multi-step requests, execute step by step, summarise in 2–3 lines; (2)
scheduling discipline: `find_free_time_slots` before proposing times, and
`recall_memories("work habits schedule preferences")` before creating events;
(3) goals → routines: a stated recurring goal ("run 3× a week") earns an
offer to `create_routine` plus a `remember_fact` of the goal, with the
reminder that routine prompts run headlessly and must be self-contained.

### 2.5 `skill-authoring` — the self-improvement recipe

**Fires** after difficult or repeated tasks, or when a loaded skill proved
wrong or incomplete.

**Purpose**: the meta-skill governing the loop in §3. It licenses the agent
to write `/skills/<name>/SKILL.md` with the file tools, tells it to offer to
save a working procedure after an iterative task, and to fix a deficient
skill *before finishing the conversation*. Its rules are quoted in §4.

---

## 3. The self-authoring loop

The writable half of the skills system is one line of backend routing:

```python
# assistant/agent/agent.py
def _backend():
    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": StoreBackend(namespace=lambda rt: (settings.user_id, "skills")),
            "/workspace/": _workspace_backend(),
        },
    )
```

Mechanics:

- The agent's file tools (`ls`, `read_file`, `write_file`, `edit_file`,
  `glob`, `grep` — provided by DeepAgents' `FilesystemMiddleware`) all pass
  through the `CompositeBackend`. Any path under `/skills/` is stripped of
  its prefix and served by the `StoreBackend`.
- `StoreBackend` adapts LangGraph's `BaseStore` — here the
  `AsyncPostgresStore` passed as `store=` to `create_deep_agent`. Each file
  is a store item under the namespace `(settings.user_id, "skills")`, i.e.
  `("kevyn", "skills")` by default. The store is **cross-thread and
  persistent**: skills written in one conversation survive restarts and are
  visible to every future session.
- Paths that match no route fall through to the default `StateBackend`
  (ephemeral, per-thread graph state) — scratch files; `/workspace/` routes
  to a real `FilesystemBackend` over `assistant/data/workspace` (or a
  Daytona/E2B/Modal sandbox when `SANDBOX_PROVIDER` is set).

The loop in practice:

1. A hard or repeated task is completed (or the domain-builder skill runs).
2. The agent writes `/skills/email-triage/SKILL.md` with `write_file`.
3. Next conversation, `SkillsMiddleware` scans `/skills/` alongside the
   bundled directory, and `email-triage` appears in the prompt index.
4. If the skill later proves wrong, skill-authoring directs the agent to
   `edit_file` it in place — and because `/skills/` loads after the bundled
   directory, even a bundled skill can be superseded by writing a same-name
   skill into the store.

There is no approval gate on skill writes — skills change *procedure*, not
the outside world; outward actions remain gated by `interrupt_on` and the
receipts ledger regardless of what a skill says.

---

## 4. Writing a new skill

Format, per the skill-authoring skill and the loader's validation:

```markdown
---
name: email-triage
description: Triage Kevyn's inbox — classify, summarize, draft replies.
---

# Email Triage

## When to Use
User asks to "deal with", "triage", or "catch me up on" email.

## Procedure
1. list_gmail_messages("in:inbox is:unread newer_than:2d") and unread Apple Mail.
2. Bucket: needs-reply / FYI / newsletter. People outrank machines.
3. render_component an inbox digest (component-design patterns) with
   hermes://say chips: "summarize", "draft reply".
4. Draft replies for needs-reply items; present for approval — never send
   unbidden.

## Pitfalls
- Do not mark anything read; triage is read-only until approved.
- Newsletters are never "important" regardless of subject urgency.

## Verification
Digest rendered; every needs-reply item has a drafted response staged.
```

Rules:

- **Frontmatter**: `name` (1–64 chars, lowercase alphanumeric and hyphens,
  must equal the directory name) and `description`. The house rule from
  skill-authoring: keep the description **≤ 60 characters** — the index
  entry is what triggers the skill, and short, keyword-dense descriptions
  keep the always-in-context index tight. (The loader itself tolerates up to
  the Agent Skills spec limit of 1,024 chars before truncating with a
  warning; the bundled skills' own descriptions run longer — the 60-char
  rule is the discipline imposed on *self-authored* skills.)
- **Body shape**: `When to Use → Procedure (numbered) → Pitfalls →
  Verification`.
- **Patch, don't fork**: prefer updating an existing skill over creating
  near-duplicates; a same-name skill in `/skills/` overrides a bundled one.
- **Class-level only**: "email triage", never "fix Tuesday's bug".
- **Never capture environment-dependent failures** or "tool X doesn't work"
  claims — they harden into refusals the agent will later cite against
  itself.
- **Procedures belong in skills; facts about the user belong in memory** —
  the dividing line repeated in the system prompt, the skill, and the memory
  tool docstrings.

---

## 5. The memory system

Three complementary layers, governed by one cache discipline inherited from
the Hermes Agent design (stated at the top of
`assistant/agent/middleware.py`): **anything dynamic is injected into the
user message, never the cached system prefix; the curated snapshot is frozen
per thread.**

| Layer | Store | Written by | Injected |
|---|---|---|---|
| Bounded files (`MEMORY`, `USER`) | Postgres `hermes.memory_files` | `manage_memory_file` (agent + reviewer) | Frozen `SystemMessage`, once per thread |
| mem0 semantic memory | pgvector (`hermes_memories`) or mem0 platform | Auto after answers + `remember_fact` | `<memory-context>` block appended to each user message |
| Session log | Postgres `hermes.message_log` / `hermes.threads` | `SessionLogMiddleware`, every turn | On demand via `session_search` |

### 5.1 Bounded files (`assistant/memory/store.py`)

Two char-budgeted, curated files — the part of memory that is *always* in
context, so it is kept small and dense:

| File | Content | Budget | Env var |
|---|---|---|---|
| `MEMORY` | The agent's own notes | 2,200 chars | `MEMORY_CHAR_LIMIT` |
| `USER` | The user's profile | 1,375 chars | `USER_PROFILE_CHAR_LIMIT` |

Implementation (`BoundedMemoryFile`):

- Entries are delimited by `§` (`ENTRY_DELIMITER = "\n§\n"`) in a single
  Postgres row per file.
- `add` / `replace` / `remove`, where replace/remove locate the target entry
  by **unique substring**: no match and ambiguous match are both errors, the
  latter asking for a longer substring.
- Every error — including an over-budget write — raises `MemoryFileError`,
  whose string form **lists the current entries**. The tool returns that
  text verbatim, so the model can consolidate stale entries and retry in the
  same turn. Budget pressure is a feature: the file cannot silently bloat.
- `render()` prepends a usage header so the model always sees how full the
  file is:

  ```
  MEMORY (your personal notes) [64% — 1,408/2,200 chars]
  - User prefers concise replies
  - Weekly review runs Fridays 16:00
  ```

- `memory_snapshot()` concatenates both rendered files — this is the string
  the snapshot middleware freezes (§5.3).

**Hermes-style content rules** (enforced by prompt, tool docstrings, and the
reviewer's instructions alike):

- Write **declarative facts, not instructions to yourself**: "User prefers
  concise replies" ✓ — "Always reply concisely" ✗.
- If a fact will be stale in a week, it does not belong in the bounded files
  — use `remember_fact`.
- Prioritise what reduces future steering: the best memory prevents the user
  from ever repeating a correction.
- Procedures belong in skills, not memory.

### 5.2 mem0 semantic layer

`SemanticMemory` (same file) is a lazily-built, lock-guarded singleton:

- With `MEM0_API_KEY` set → the hosted mem0 platform (`MemoryClient`).
- Otherwise → local mem0 (`Memory.from_config`) with a **pgvector** vector
  store, connection parsed from `DATABASE_URL`, collection
  `hermes_memories`. No extra infrastructure beyond the Postgres container.

All operations are scoped to `settings.user_id`. `search()` normalises the
two client shapes (local returns `{"results": [...]}`, platform returns a
list). Writes go through `add` (single fact + metadata) or
`add_conversation` (user/assistant pair) — in the latter case mem0's own
LLM-based extraction decides which facts to keep, so the agent does not have
to curate the long tail by hand.

### 5.3 Per-turn injection and cache discipline (`assistant/agent/middleware.py`)

Two middlewares wrap every model call:

**`MemorySnapshotMiddleware`** — the bounded files.

- On each model call it inserts the snapshot as a `SystemMessage` at
  position 0, headed `## Your curated memory (frozen snapshot for this
  session)`, unless a message with that header is already present.
- The snapshot string is computed **once per `thread_id`** and cached in an
  in-process dict (bounded to 500 threads, FIFO-evicted). Frozen-per-thread
  is deliberate: the system prefix stays byte-stable for the whole
  conversation, so provider prompt caching keeps working. Mid-session
  `manage_memory_file` edits become visible in the *next* conversation.
- A snapshot failure degrades to an empty string — memory must never break
  the run.

**`Mem0Middleware`** — the semantic layer, strictly on the user-message side
of the cache boundary.

- *Before the call*: takes the latest `HumanMessage`, searches mem0 with its
  text (top 5), and — only if the message does not already contain a
  `<memory-context>` fence — appends:

  ```
  <memory-context>
  Background from long-term memory (may be irrelevant — use judgement):
  - Kevyn's sister Dana lives in Paris
  - User prefers window seats on flights
  </memory-context>
  ```

  The replacement `HumanMessage` keeps the original message `id`. A failed
  search logs a warning and injects nothing.
- *After the call*: if the final `AIMessage` has **no tool calls** (i.e. it
  is the turn's actual answer, not an intermediate step), the clean user
  text (fence stripped) and the answer — each truncated to 2,000 chars — are
  submitted to `semantic_memory.add_conversation` on a **single-worker
  `ThreadPoolExecutor`**, keeping mem0's extraction latency entirely off the
  response path and serialised.

`recall_memories` exists for *deliberate* digging beyond the automatic top-5
("call this only when you need to dig deeper on a specific topic").

### 5.4 Post-turn background review (`assistant/agent/review.py`)

Automatic injection covers recall; the review covers **curation** — deciding
what deserves to be written down at all, without spending the main model's
tokens or the user's time.

Cadence (`SessionLogMiddleware.aafter_agent` in
`assistant/agent/session_log.py`):

- Every turn, all new messages are mirrored to `hermes.message_log` (text
  capped at 8,000 chars) and the thread is upserted into `hermes.threads`
  (title = first human message, 80 chars).
- For **chat-tier** sessions only, human turns are counted per thread; every
  `review_every_n_turns` (default **6**, env `REVIEW_EVERY_N_TURNS`) the
  counter resets and `spawn_review(messages)` fires. Routine and webhook
  tiers never trigger review.

Execution (`spawn_review` → `_run_review`):

- Runs on a **daemon thread** — fire-and-forget, never blocks a response,
  never raises (failures log a warning).
- Builds a digest of the conversation: tool messages dropped as machine
  noise, each remaining message truncated to 600 chars, keeping the last
  6,000 chars overall.
- A headless `create_agent` on `settings.review_model` (default
  `anthropic:claude-haiku-4-5-20251001` — deliberately a cheap model) with
  **only** `manage_memory_file` and `remember_fact` bound, recursion limit
  12, system-prompted as "a silent memory curator … you never reply to the
  user".
- Its instructions restate the routing rules: persona/preferences/
  relationships/goals/dates and expectations about assistant behaviour;
  declarative facts only; stale-in-a-week → `remember_fact`; core durable →
  bounded files; otherwise reply exactly `Nothing to save.` and stop.

The division of labour is intentional: `Mem0Middleware` persists raw
exchanges cheaply every turn (mem0 extracts), while the reviewer makes the
judgement calls about the *bounded* files on a slow cadence, using the same
tools the main agent would.

### 5.5 Session search (`assistant/tools/session_search.py`)

Zero-LLM Postgres full-text search over the mirrored message log — the third
memory layer, for "as we discussed last week" moments. One tool,
`session_search(query, thread_id, limit)`, with three **argument-inferred
modes**:

| Mode | Trigger | Behaviour |
|---|---|---|
| **Scroll** | `thread_id` given | That conversation's messages in order, up to 100, content capped at 600 chars each |
| **Discovery** | `query` given | Full-text search (`to_tsvector('simple')` / `plainto_tsquery`) over `hermes.message_log`, grouped by thread, ranked by `ts_rank`; returns `ts_headline` snippet plus **bookends** — the first 3 and last 3 human/AI messages (200 chars each) so the agent sees how a conversation opened and concluded without scrolling it; limit clamped to 1–10 |
| **Browse** | no args | Most recent chat threads (`thread_id`, `title`, `when`), limit clamped to 1–20 |

Routine-run sessions are **demoted, not excluded** in discovery (rank
× 0.3): a morning brief that mentioned a flight should still be findable,
but six briefs should not bury the one real conversation about it. Browse
mode filters to `source='chat'` outright.

The tool's docstring instructs the recall-first posture: *"recall before
asking the user to repeat themselves."*

### 5.6 Memory tools reference (`assistant/tools/memory.py`)

| Tool | Layer | Notes |
|---|---|---|
| `manage_memory_file(file, action, text, old_text)` | Bounded | `file` ∈ `MEMORY`/`USER`; `action` ∈ `add`/`replace`/`remove`; returns the updated rendered file, or an actionable error listing current entries |
| `remember_fact(fact, category)` | mem0 | Standalone-sentence facts; `category` ∈ `preference`/`person`/`goal`/`date`/`general`, stored as metadata |
| `recall_memories(query, limit)` | mem0 | Returns `[{id, memory, score}]`; for digging beyond the automatic per-turn top-5 |
| `forget_memory(memory_id)` | mem0 | Deletes by id from `recall_memories` — the user's right to be forgotten |
| `session_search(query, thread_id, limit)` | Session log | See §5.5 |

---

## 6. Where a fact goes — the routing table

The same routing rules appear in the system prompt, the memory tool
docstrings, the review prompt, and the skill-authoring skill, so every writer
(main agent, reviewer, self-authored skills) applies them consistently:

| It is… | It goes to… |
|---|---|
| A procedure ("how to triage email") | A skill in `/skills/` |
| A durable core fact or preference | `manage_memory_file` → `MEMORY`/`USER` |
| A long-tail detail, person, date, past decision | `remember_fact` → mem0 |
| Stale within a week | mem0, never the bounded files |
| Something that happened in a conversation | Already in the session log — `session_search` finds it |
| A domain's operational detail (APIs, pitfalls, user goals for it) | The domain's skill; only the durable goal itself in memory |
