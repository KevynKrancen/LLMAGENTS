# Decomposition — turning big requests into write_todos plans

## Rules for a good todo list

1. **Verb-first, checkable.** "Research movers and get 3 quotes" ✓ —
   "Movers" ✗. If you can't tell when it's done, it's not a todo.
2. **One tool-scope per todo.** A todo maps to one delegation or one small
   cluster of related calls (e.g. "find slot + create event" is one todo;
   "research flights AND build itinerary" is two).
3. **Dependency order.** Grounding (memory/calendar/workspace recon) first,
   research second, synthesis third, scheduling/routines/reminders last —
   later steps embed ids and facts produced by earlier ones.
4. **4–9 todos.** Fewer: you didn't need write_todos. More: merge or push
   detail down into the todo's execution.
5. **Statuses honestly.** Exactly one `in_progress` at a time; flip to
   `completed` immediately after finishing, before starting the next —
   the user watches this list live in the app.
6. **Last todo = delivery.** Present artifact + summary; never end with an
   internal step.

## Delegation map — who executes a step

| Work | Executor |
|---|---|
| Broad/multi-source web research ("best neighborhoods", "top movers") | `task(subagent_type="researcher", description=...)` — description must name the deliverable shape: "return a ranked list of N with prices and one-line tradeoffs" |
| Ranking, comparison tables, number-crunching over gathered data | `task(subagent_type="analyst", ...)` |
| Misc multi-step side quest that needs no specialism | `task(subagent_type="general-purpose", ...)` |
| One quick lookup | `search_web` / `fetch_web_page` directly — never spawn a subagent for a single call |
| Availability + events | `find_free_time_slots` → `create_calendar_event` (see scheduling.md) |
| Recurring follow-up | `create_routine` |
| Hard deadline that must ping the phone | `create_iphone_reminder(title, due_iso)` |
| The plan document / tracker | `create_artifact(kind, title, content, path=...)`; checklists → `save_note(title, content, path=...)` |
| Durable facts learned while planning | `remember_fact(fact, category=...)` |
| A domain that will live for months (ongoing job hunt, trading) | escalate to the **domain-builder** skill instead of a one-off plan |

---

## Worked example 1 — trip planning

Request: *"Plan a 5-day Tokyo trip for late October."*

```
write_todos(todos=[
 {"content":"Recall travel prefs + check late-Oct calendar conflicts","status":"in_progress"},
 {"content":"Research flights TLV-Tokyo and best areas to stay","status":"pending"},
 {"content":"Research day-by-day activities and food","status":"pending"},
 {"content":"Build itinerary artifact in Travel/Tokyo","status":"pending"},
 {"content":"Save booking checklist note","status":"pending"},
 {"content":"Calendar-block the trip + booking deadline reminder","status":"pending"},
 {"content":"Remember trip facts; present plan","status":"pending"}])
```

| Todo | Execution |
|---|---|
| 1 | `recall_memories("travel preferences flights budget")`; `list_calendar_events(days_ahead=60)` scanning ~Oct 19–31 for conflicts. If no budget anywhere, ask the ONE question now. |
| 2 | `task(subagent_type="researcher", description="Find 3 TLV→Tokyo round-trip options for ~Oct 20-27 with price and total travel time, and 3 Tokyo neighborhoods to stay in with a nightly hotel price band each. Return a compact ranked list.")` |
| 3 | Second `researcher` task: "Day-by-day: for a 5-day first Tokyo visit build 5 themed days (area, 2-3 sights, lunch + dinner picks with price level). Late October — note seasonal events (autumn foliage, Halloween crowds)." |
| 4 | `create_artifact(kind="markdown", title="Tokyo — 5 days, late Oct", content=<Day 1..5 itinerary + flight/hotel shortlist>, path="Travel/Tokyo")` — `path` materializes the folder. |
| 5 | `save_note(title="Tokyo booking checklist", content="- [ ] Book flight (target < $X)\n- [ ] Book hotel ...\n- [ ] eSIM\n- [ ] Suica/Welcome Suica\n- [ ] Travel insurance", path="Travel/Tokyo")` |
| 6 | Trip block: `create_calendar_event(summary="Tokyo trip", start_iso="2026-10-21T08:00:00", end_iso="2026-10-26T22:00:00", description="Itinerary: see Travel/Tokyo artifact")`. Deadline: `create_iphone_reminder(title="Book Tokyo flights", due_iso="2026-09-15T18:00:00", notes="Prices climb ~6 weeks out")`. |
| 7 | `remember_fact("Kevyn is planning a Tokyo trip Oct 21-26 2026, budget ~$X", category="date")`; reply 2–3 lines pointing at the artifact. |

---

## Worked example 2 — job search

Request: *"Help me find a new job as a senior ML engineer."*

This is an ongoing capability → hybrid: run the plan below, and offer the
domain-builder skill for the permanent infrastructure (folder + dashboard).

```
write_todos(todos=[
 {"content":"Recall profile/constraints; confirm target comp+location","status":"in_progress"},
 {"content":"Market scan: companies hiring senior ML in Israel/remote","status":"pending"},
 {"content":"Rank companies into a fit table","status":"pending"},
 {"content":"Set up Career/Job Search folder + application tracker","status":"pending"},
 {"content":"Draft CV tailoring notes for top 3 targets","status":"pending"},
 {"content":"Weekly scan routine + application time blocks","status":"pending"},
 {"content":"Store the goal; present tracker","status":"pending"}])
```

| Todo | Execution |
|---|---|
| 1 | `recall_memories("career skills salary work history")`; ONE question only if target comp/remote-vs-office is unknown. |
| 2 | `task(subagent_type="researcher", description="Find 10-12 companies currently hiring senior ML engineers (Israel or remote-friendly), each with: open role link, stack, size, comp signal if public.")` |
| 3 | `task(subagent_type="analyst", description="Rank these companies by fit for: <profile summary>. Score 1-5 on comp, stack match, seniority, remote policy. Return JSON {columns, rows}.")` → feed straight into `create_artifact(kind="table", title="Target companies", content=<that JSON>, path="Career/Job Search")`. |
| 4 | `shape_workspace(operations='[{"op":"create","path":"Career/Job Search","icon":"briefcase"}]')`; `create_artifact(kind="html", title="Application tracker", content=<tracker UI: company/stage/next action>, path="Career/Job Search", as_dashboard=True)` — the folder now opens as the tracker. |
| 5 | `save_note(title="CV angles — top 3", content=<per-company: which projects to lead with, keywords from their posting>, path="Career/Job Search")` |
| 6 | `create_routine(name="Job scan", cron="0 9 * * 0", prompt="Search for new senior ML engineer openings in Israel/remote posted this week. Compare against the companies already in Kevyn's Career/Job Search tracker; push only genuinely new leads, max 5, with links.")`; then `find_free_time_slots(date=<next Tue>, duration_minutes=90)` → `create_calendar_event(summary="Applications: 2 tailored", ...)` — twice weekly. |
| 7 | `remember_fact("Kevyn is job hunting: senior ML engineer, target <comp>, prefers <remote/hybrid>", category="goal")`; short reply + tracker. |

---

## Worked example 3 — apartment move

Request: *"I'm moving apartments on Sept 1, help me get organized."* (today: Aug 3)

```
write_todos(todos=[
 {"content":"Capture move facts (addresses, movers booked?)","status":"in_progress"},
 {"content":"Build backwards timeline from Sept 1","status":"pending"},
 {"content":"Research movers, get to 3 quote candidates","status":"pending"},
 {"content":"Utilities/address-change checklist note","status":"pending"},
 {"content":"Calendar milestones + hard-deadline reminders","status":"pending"},
 {"content":"Weekly check-in routine until the move","status":"pending"},
 {"content":"Present move plan artifact","status":"pending"}])
```

| Todo | Execution |
|---|---|
| 1 | `recall_memories("apartment address lease")`; ONE question bundling the unknowns ("New address, and are movers already booked?"). `remember_fact("Kevyn moves to <addr> on Sept 1 2026", category="date")`. |
| 2 | No tools — reason backwards: Aug 10 book movers · Aug 17 start packing non-essentials · Aug 24 utilities transfer + address changes · Aug 30 pack essentials · Sep 1 move · Sep 3 old-apartment handover/cleaning. This skeleton drives todos 5–7. |
| 3 | `task(subagent_type="researcher", description="Find 4-5 well-reviewed moving companies serving <city>, with price range for a <N>-room move and phone/site. Rank by reviews.")` Draft (don't send) a quote-request message; outward send waits for confirmation. |
| 4 | `save_note(title="Move checklist", content="Utilities: electric, water, internet, gas\nAddress: bank, bituach leumi, employer, deliveries\nBoth apartments: photos before/after, meter readings", path="Home/Move")` |
| 5 | One `create_calendar_event` per milestone from todo 2 (e.g. `summary="Book movers deadline", start_iso="2026-08-10T18:00:00", end_iso="2026-08-10T18:30:00"`), plus a full-day-style block for Sep 1 08:00–20:00 "MOVING DAY". Hard deadlines also get `create_iphone_reminder(title="Book movers", due_iso="2026-08-09T10:00:00")` — calendar events don't nag, reminders do. |
| 6 | `create_routine(name="Move check-in", cron="0 18 * * 6", prompt="Kevyn moves apartments Sept 1. Review the Home/Move checklist note and this week's move milestones on the calendar; push a 4-line status: done, at risk, next 3 actions.")` — and a FINAL todo item to `delete_routine` after Sept 3 (routines never auto-expire). |
| 7 | `create_artifact(kind="markdown", title="Move plan — Sept 1", content=<timeline + movers shortlist + checklist link>, path="Home/Move")`; 2-line reply. |

## Anti-patterns

- A todo per tool call ("call find_free_time_slots") — todos are outcomes,
  calls are how.
- Researching before grounding — memory or the calendar often already
  answers what you were about to search.
- Ending with created infrastructure but no presentation step — the user
  should always receive the plan, not discover it.
- Spawning a persistent agent (`spawn_agent`) for a finite plan — that's for
  standing domains; plans use the builtin `task()` roster.
