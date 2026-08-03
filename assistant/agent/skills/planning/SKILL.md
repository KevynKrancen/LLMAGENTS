---
name: planning
description: Multi-step planning and scheduling — decompose big requests into write_todos plans, schedule work via the calendar tools, and turn recurring goals into cron routines. Use for any 3+ step request.
---

# Planning

## When to Use
- Any request needing 3+ dependent steps or touching 2+ tool domains
  (research + calendar, workspace + routines, …).
- "Plan my week / trip / move", "help me organize X", "I want to start
  doing Y regularly", scheduling anything into the calendar.
- NOT for single-tool asks ("what's on my calendar tomorrow") — just do those.

## Procedure
1. **Ground before planning.** `recall_memories("<topic> preferences habits")`,
   and `list_calendar_events(days_ahead=7)` if time is involved. Ask at most
   ONE clarifying question — only for a fact that changes the whole plan
   (budget, hard deadline). Everything else: pick a sensible default and say so.
2. **Decompose into `write_todos`** before acting: 4–9 verb-first todos, one
   tool-scope each, dependency order, all `pending` except the first
   `in_progress`. Read `references/decomposition.md` when the request is big
   or fuzzy — it has the decomposition rules and three fully worked plans
   (trip, job search, apartment move) with the exact tool per step.
3. **Execute one todo at a time**, updating statuses as you go. Delegate:
   broad multi-source web research → `task(subagent_type="researcher", ...)`;
   ranking/comparison/number-crunching → `subagent_type="analyst"`; everything
   else → direct tools. Don't delegate a single `search_web` call.
4. **Schedule with real availability, never guesses.** For every proposed
   time: `find_free_time_slots(date="YYYY-MM-DD", duration_minutes=...)`,
   pick a start inside a returned gap, then `create_calendar_event`. Read
   `references/scheduling.md` before any non-trivial scheduling (multi-day
   placement, rescheduling, buffers) and for the cron cookbook when writing
   any `create_routine` schedule.
5. **Plans are deliverables, not chat.** The plan itself goes in
   `create_artifact` (markdown/html, `path=` a workspace folder) or
   `save_note`; the chat reply is 2–3 lines plus the artifact. Present
   multi-event schedule proposals BEFORE mass-creating events ("propose as
   done" — stage it, one-tap confirm); a single obvious event you create
   directly (it's reversible and leaves a receipt).
6. **Recurring goal → routine.** "I want to run 3x a week" ⇒ offer
   `create_routine(name, cron, prompt)` with a self-contained prompt (it runs
   headlessly — no "as discussed") + `remember_fact(..., category="goal")`.
7. **Close the loop.** Mark every todo `completed` (or say why one was
   dropped), then summarize what now exists — events, artifact, routine — in
   2–3 lines.

## Pitfalls
- **There is no update_calendar_event.** Rescheduling =
  `list_calendar_events` (get id) → `delete_calendar_event(event_id)` →
  `create_calendar_event` with the new times.
- `create_calendar_event` takes NAIVE local ISO (`'2026-08-04T15:00:00'`).
  Never append `Z` or an offset — the tool applies the user's timezone
  server-side; a `Z` would silently shift the event.
- `find_free_time_slots` covers ONE date (default window 09–21). For a week,
  loop over dates. It returns raw gaps `{start, end}` — a 4h gap is one
  slot, not four 1h slots; you choose the start time inside it.
- Cron is 5-field, evaluated in the user's timezone (`Asia/Jerusalem` —
  work week Sun–Thu), day-of-week `0` = Sunday. Never set both day-of-month
  and day-of-week (standard cron ORs them).
- Todos are plumbing, not the product — never present the todo list as the
  deliverable, and never `write_todos` for a trivially linear task.
- Routines never auto-expire. A routine for a dated project (a move, a trip)
  needs a final todo: `delete_routine` after the date passes.

## Verification
- After creating events: `list_calendar_events` for the affected range —
  every new event present, no overlaps with existing ones.
- After `create_routine`: `list_routines` shows it enabled with the intended
  cron; re-read the prompt as if you knew nothing — would it run standalone?
- Every todo is `completed`, and each produced something checkable (an event
  id, an artifact, a note path, a routine id) — not just prose.
- The plan artifact/note actually exists at the workspace path you claimed.
