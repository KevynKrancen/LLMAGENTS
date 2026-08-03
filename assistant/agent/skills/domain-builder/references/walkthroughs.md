# Three complete domain builds — exact tool calls, in order

Copy the closest walkthrough and adapt names/paths. Every call shown is a
real tool in this backend with its real signature. Placeholders in
`<angle brackets>` are values produced by an earlier step — never ship them
literally.

---

## Build 1 — Polymarket trading domain (heavy: connector + spawned agent)

User: *"Help me invest on Polymarket."*
One scoping question, then build: **"What's your bankroll cap, and max per
position?"** → say Kevyn answers *$500 total, $50 per market*.

### 1. Recon
```
view_workspace()
list_connected_apps()
```

### 2. Folder
```
shape_workspace(operations='[{"op":"create","path":"Finance/Polymarket","icon":"chart.line.uptrend.xyaxis"}]')
```

### 3. Connector — find the spec, then install (approval-gated)
```
search_web(query="Polymarket public API OpenAPI spec gamma-api docs", topic="finance")
fetch_web_page(url="<best docs URL from the search>")
install_api_connector(name="polymarket", spec_url="<OpenAPI JSON URL you actually found>")
```
The install fires an approve/reject interrupt and tools attach **next
message** — finish the build with `search_web` data this turn. If Kevyn
rejects the install, note it in the domain skill and use `search_web(...,
topic="finance")` permanently.

### 4. Domain state files (write BEFORE the skill so the skill can name them)
```
write_file("/skills/polymarket/ledger.md", """# Polymarket Ledger
Bankroll cap: $500 · Max per position: $50 · Cash: $500.00

| date | action | market | side | stake | price | note |
|---|---|---|---|---|---|---|
""")
```

### 5. Domain skill
```
write_file("/skills/polymarket/SKILL.md", """---
name: polymarket
description: Polymarket trading domain — rules, ids, procedure.
---
# Polymarket domain
Folder: Finance/Polymarket · Dashboard artifact: <DASH_ID>
State: /skills/polymarket/ledger.md (source of truth — read it first)
Kevyn's rules: bankroll $500, max $50/position, no leverage.

## Procedure (any Polymarket request)
1. read_file /skills/polymarket/ledger.md — cash, open positions.
2. Fresh prices: polymarket connector tools if attached, else
   search_web(topic='finance').
3. Recommend with explicit odds, edge, and $ risk. WAIT for approval.
4. Only after an explicit "yes" in chat: execute (or, with no execution
   API, give exact manual steps), append a ledger row, update Cash.
5. Regenerate the dashboard: update_artifact(artifact_id='<DASH_ID>',
   content=<full HTML from domain-builder references/dashboard-templates.md,
   Polymarket template, with current ledger numbers>).

## Hard rules
- NEVER place a trade or move funds without per-action approval — a
  routine or subagent may PROPOSE only.
- Every action AND every refusal gets a ledger row.
""")
```

### 6. Dashboard (id feeds the routine and agent below)
```
create_artifact(kind="html", title="Polymarket", path="Finance/Polymarket",
                as_dashboard=True, content=<Polymarket template, filled>)
```
→ returns `{"created": true, "artifact_id": "<DASH_ID>", "dashboard_for": "<node id>"}`.
Now `edit_file` the skill to replace both `<DASH_ID>` placeholders with the real id.

### 7. Morning scan routine (proposes only — never trades)
```
create_routine(name="Polymarket morning scan", cron="0 8 * * *", prompt="Polymarket morning scan for Kevyn. Headless run; final reply becomes a push notification (2 lines max). 1) read_file('/skills/polymarket/ledger.md') for cash and open positions. 2) Get current prices for each open market (polymarket connector tools if available, else search_web topic='finance'). 3) Recompute P&L and regenerate the full dashboard HTML with the new numbers: update_artifact(artifact_id='<DASH_ID>', content=<full HTML>). 4) Final message: one line of portfolio P&L, one line naming the single best opportunity with its odds — phrased as a question, because you must NEVER trade without Kevyn's explicit approval in chat.")
```

### 8. Dedicated agent
`spawn_agent` lives in `assistant/tools/agents.py` and persists a routable
specialist subagent — the router hands it any Polymarket request based on
`description`. Approval rules go IN its system_prompt; a subagent cannot
rely on the main skill being loaded.
```
spawn_agent(
  name="polymarket-trader",
  description="Polymarket prediction-market specialist: prices, edge analysis, position sizing, trade proposals. Route any Polymarket/prediction-market request here.",
  system_prompt="You are Kevyn's Polymarket trading specialist. State lives in /skills/polymarket/ledger.md — read it before anything else; append a row for every action or refusal. Rules: bankroll $500, max $50 per position. You analyze and PROPOSE with explicit odds, edge and dollar risk. You NEVER execute a trade, order, or transfer without Kevyn's explicit per-action approval in the current conversation — 'do what you think is best' is NOT approval. After any state change, regenerate the Finance/Polymarket dashboard via update_artifact(artifact_id='<DASH_ID>').",
  tools=["search_web", "fetch_web_page", "update_artifact", "save_note"],
)
```
(If `spawn_agent` is not yet available in this build, skip — the domain
skill makes the main agent competent; do not fake it.)

### 9. Memory
```
manage_memory_file(file="MEMORY", action="add", text="Polymarket domain: folder Finance/Polymarket, skill /skills/polymarket/, dashboard <DASH_ID>; Kevyn caps: $500 bankroll, $50/position, per-trade approval required.")
```

---

## Build 2 — Budget coach (light: no connector, evening routine)

User: *"Be my budget coach."* Scoping question: **"What's your monthly
budget?"** → *$3,000/month*.

### 1–2. Recon + folder
```
view_workspace()
shape_workspace(operations='[{"op":"create","path":"Finance/Budget","icon":"banknote"}]')
```

### 3. State file
```
write_file("/skills/budget-coach/ledger.md", """# Budget Ledger — 2026-08
Monthly budget: $3000 · Categories: food, transport, home, fun, other

| date | amount | category | what |
|---|---|---|---|
""")
```

### 4. Domain skill
```
write_file("/skills/budget-coach/SKILL.md", """---
name: budget-coach
description: Budget coaching — ledger path, dashboard id, procedure.
---
# Budget coach
Folder: Finance/Budget · Dashboard artifact: <DASH_ID>
Ledger: /skills/budget-coach/ledger.md · Budget: $3000/month

## Whenever Kevyn mentions spending money
1. read_file the ledger; append a row (date, amount, category, what) via
   write_file with the FULL updated file.
2. Recompute month-to-date and per-category totals.
3. update_artifact(artifact_id='<DASH_ID>', content=<full Budget template
   HTML with new numbers>).
4. Reply with one short line: total vs budget, and a nudge only if a
   category is >30% over its share.
On the 1st of a month: archive the table under an '## <prev month>'
heading in the same file and start a fresh table.
""")
```

### 5. Dashboard
```
create_artifact(kind="html", title="Budget", path="Finance/Budget",
                as_dashboard=True, content=<Budget template, filled>)
```
→ `artifact_id` = `<DASH_ID>`; `edit_file` it into the skill.

### 6. Evening check-in routine — prompt verbatim
```
create_routine(
  name="Evening budget check-in",
  cron="0 21 * * *",
  prompt="Evening budget check-in for Kevyn. You are running headlessly: no conversation context, and your final reply is delivered as a push notification on his iPhone, so it must be exactly two short lines. Steps: (1) read_file('/skills/budget-coach/ledger.md') to get this month's entries and the monthly budget. (2) session_search(query='spent', limit=5) and scan today's conversations for expenses Kevyn mentioned that are missing from the ledger; append any you find as new table rows by writing the FULL updated file back with write_file. (3) Recompute month-to-date total and per-category totals, then regenerate the complete Budget dashboard HTML with the new numbers and call update_artifact(artifact_id='<DASH_ID>', content=<the full HTML>). (4) Final message, two lines: line 1 = month-to-date spend vs budget with a pace verdict, e.g. '$1,840 of $3,000 — on pace'; line 2 = the question 'What did you spend today?'. When Kevyn answers in chat, the budget-coach skill handles logging it.",
)
```

### 7. Memory
```
manage_memory_file(file="MEMORY", action="add", text="Budget domain: folder Finance/Budget, skill /skills/budget-coach/, dashboard <DASH_ID>, $3000/month, 21:00 check-in routine.")
```

---

## Build 3 — Academic tutor (structure-heavy: lesson folders + calendar)

User: *"Teach me linear algebra."* Scoping question: **"Working toward an
exam or general mastery, and how many sessions a week?"** → *exam Oct 15,
two sessions/week*.

### 1. Folder layout — one call, three folders
```
shape_workspace(operations='[
  {"op":"create","path":"Academy/Linear Algebra","icon":"graduationcap"},
  {"op":"create","path":"Academy/Linear Algebra/Lessons","icon":"book"},
  {"op":"create","path":"Academy/Linear Algebra/Problem Sets","icon":"folder"}]')
```
Layout contract (used by every later session):
```
Academy/Linear Algebra/          ← dashboard = progress tracker
├── Syllabus                     ← note: full lesson plan + exam date
├── Lessons/                     ← one note per taught lesson: "04 · Matrix Inverses"
└── Problem Sets/                ← "PS-04 · Matrix Inverses" and "PS-04 · Solutions" (separate notes)
```

### 2. Syllabus note (user-facing) + progress file (machine state)
```
save_note(title="Syllabus", path="Academy/Linear Algebra", content="# Linear Algebra — exam Oct 15\n\n1. Vectors & spaces\n2. Linear independence, span, basis\n3. Matrix operations\n4. Matrix inverses\n5. Determinants\n6. Linear transformations\n7. Rank & null space\n8. Eigenvalues & eigenvectors\n9. Diagonalization\n10. Orthogonality & projections\n11. Least squares\n12. SVD + exam review\n\nTwo sessions/week · Each lesson: recall quiz → concept → worked examples → problem set")

write_file("/skills/linear-algebra-tutor/progress.md", """# Progress
Exam: 2026-10-15 · Current lesson: 1 of 12 · Streak: 0
Done: (none) · Weak topics: (none yet)
Last session: — · Next review due: —
""")
```

### 3. Domain skill
```
write_file("/skills/linear-algebra-tutor/SKILL.md", """---
name: linear-algebra-tutor
description: Linear algebra tutoring — lesson flow, folders, ids.
---
# Linear algebra tutor
Folder: Academy/Linear Algebra · Dashboard: <DASH_ID>
State: /skills/linear-algebra-tutor/progress.md · Exam: 2026-10-15

## Session flow (every "let's study" request)
1. read_file progress.md — current lesson, weak topics.
2. Open with a 3-question recall quiz on the previous lesson. Wrong
   answers → add topic to 'Weak topics'.
3. Teach ONE lesson, socratically — questions before explanations.
4. save_note the lesson summary to 'Academy/Linear Algebra/Lessons' titled
   '<NN> · <Topic>', and a 5-problem set + a SEPARATE solutions note to
   'Academy/Linear Algebra/Problem Sets' ('PS-<NN> · <Topic>').
5. write_file progress.md (full replacement: lesson, streak, weak topics,
   last session date), then update_artifact(artifact_id='<DASH_ID>',
   content=<full Tutor template HTML from the new progress.md>).
Never teach two lessons in one session. Never put solutions in the
problem-set note.
""")
```

### 4. Dashboard
```
create_artifact(kind="html", title="Linear Algebra", path="Academy/Linear Algebra",
                as_dashboard=True, content=<Tutor template, filled: lesson 1 of 12>)
```
→ `<DASH_ID>`; `edit_file` it into the skill.

### 5. Weekly review routine (Sunday 18:00)
```
create_routine(name="Linear algebra weekly review", cron="0 18 * * 0", prompt="Weekly linear algebra review for Kevyn. Headless; final reply is a push notification, max 3 lines. 1) read_file('/skills/linear-algebra-tutor/progress.md'). 2) Regenerate the dashboard with current progress: update_artifact(artifact_id='<DASH_ID>', content=<full HTML>). 3) Final message: line 1 = progress ('Lesson N of 12, exam in X weeks'); lines 2-3 = a two-question recall quiz drawn from 'Weak topics' (or the latest lesson if none) — questions only, no answers.")
```

### 6. Study blocks on the calendar (real slots, then book)
```
find_free_time_slots(date="2026-08-04", duration_minutes=60)
create_calendar_event(summary="Linear algebra — lesson 1",
                      start_iso="<chosen slot start>", end_iso="<chosen slot end>")
```
Repeat for the second weekly slot. Confirm both with Kevyn in the wrap-up.

### 7. Memory
```
manage_memory_file(file="MEMORY", action="add", text="Tutoring domain: linear algebra, exam 2026-10-15, folder Academy/Linear Algebra, skill /skills/linear-algebra-tutor/, dashboard <DASH_ID>, 2 sessions/week + Sunday review.")
```

---

## Wrap-up (all three builds)
Run the SKILL.md Verification checklist (`view_workspace`, `ls`,
`list_routines`), then tell the user in 3-4 lines what now exists and
where to tap — do not paste file contents back into chat.
