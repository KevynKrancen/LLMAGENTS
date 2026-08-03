# Scheduling — exact tool sequences, timezone rules, cron cookbook

The four calendar tools (`assistant/tools/calendar.py`) and `create_routine`
(`assistant/tools/routines.py`) are the entire scheduling surface. Everything
below uses their real signatures.

## Timezone rules (get these wrong and events silently shift)

- All tools operate in `settings.timezone` (default `Asia/Jerusalem`). You
  never pass a timezone anywhere.
- `create_calendar_event(start_iso, end_iso)` — pass **naive local ISO**:
  `'2026-08-04T15:00:00'`. The tool attaches `timeZone` server-side. If you
  append `Z` or `+00:00`, Google honors the offset and the event lands 2–3
  hours off. Strip any offset before passing.
- `find_free_time_slots` returns **offset-bearing** local ISO
  (`'2026-08-04T13:00:00+03:00'`). To reuse a slot start as an event start,
  strip the offset: take everything before the `+`/`-` offset suffix.
- `create_routine(cron=...)` — cron fires in the user's timezone, NOT UTC.
  Write "7am" as `0 7 * * *`, done. No conversion, ever.
- Israeli work week is **Sunday–Thursday**. "Weekdays" = `0-4` (Sun–Thu),
  weekend = Fri/Sat. Confirm with `recall_memories("work schedule")` if the
  routine's purpose is work-related.

## Tool signatures (real defaults)

```
list_calendar_events(days_ahead=7, max_results=20)
    -> [{id, summary, start, end, location}]
create_calendar_event(summary, start_iso, end_iso, description="", location="")
    -> {created, id, htmlLink}
delete_calendar_event(event_id) -> {deleted}
find_free_time_slots(date, duration_minutes=60, day_start_hour=9, day_end_hour=21)
    -> [{start, end}]   # raw gaps >= duration, within the window, one day only
```

## Sequence 1 — place one event ("book me an hour for X on Tuesday")

```
1. find_free_time_slots(date="2026-08-04", duration_minutes=60)
2. Pick a start INSIDE a gap using the buffer heuristics below.
   Gap 13:00–17:30 + want 60min => choose 13:15 (15min buffer after the
   preceding meeting), end 14:15.
3. create_calendar_event(
       summary="Deep work: Q3 deck",
       start_iso="2026-08-04T13:15:00",
       end_iso="2026-08-04T14:15:00",
       description="Goal: outline all slides. Prep: read Anat's brief.")
4. Verify: list_calendar_events(days_ahead=2) — event present, no overlap.
```
Single obvious event: create directly (reversible, leaves a receipt), confirm
in one line. Don't ask permission first.

## Sequence 2 — plan a week of sessions ("3 gym sessions this week")

```
1. list_calendar_events(days_ahead=7)                  # one overview call
2. find_free_time_slots per CANDIDATE day (it is single-day):
     find_free_time_slots(date="2026-08-04", duration_minutes=75,
                          day_start_hour=6, day_end_hour=9)   # morning gym
   Repeat for 2026-08-06, 2026-08-09 (spread days — never back-to-back
   for workouts).
3. Present the 3 proposed slots as a plan (render_component or artifact)
   — multi-event plans get a look BEFORE creation.
4. On confirm: 3x create_calendar_event.
5. If it's an ongoing goal, ALSO create_routine (see cookbook) and
   remember_fact("Kevyn trains 3x/week, mornings", category="goal").
```

## Sequence 3 — reschedule (no update tool exists)

```
1. list_calendar_events(days_ahead=14)      # find the event, note id + details
2. find_free_time_slots(date=<new day>, duration_minutes=<same length>)
3. create_calendar_event(<same summary/description/location, new times>)
4. delete_calendar_event(event_id=<old id>) # delete LAST — create-then-delete
                                            # so a failure never loses the event
```

## Buffer heuristics

- 15 min minimum between back-to-back meetings; never butt a new event
  against an existing one's exact end.
- Event has a `location` (or the new one does)? Add 30–45 min travel buffer
  on both sides; sanity-check with `show_on_iphone_map(query=<location>)`.
- Deep work needs a gap ≥ 90 min; don't shred a rare 3h gap with a 30min task
  — put small tasks in small gaps.
- Keep 12:00–14:00 free for lunch unless the user asks otherwise.
- Demanding work in the morning, admin/errands after 16:00 — but
  `recall_memories("work habits schedule preferences")` beats any default.
- Widen the window deliberately: `day_start_hour=6` for workouts,
  `day_end_hour=23` for social events. Defaults (9–21) miss both.

## Cron cookbook — `create_routine(name, cron, prompt)`

Format: `minute hour day-of-month month day-of-week`, user's timezone,
day-of-week 0=Sun. Never set both day fields (cron ORs them → extra fires).
Prompts run headlessly and push to the iPhone — each must stand alone.

| Cron | Fires |
|---|---|
| `0 7 * * *` | every day 07:00 — morning brief |
| `30 7 * * 0-4` | Sun–Thu 07:30 — workday brief (Israeli week) |
| `0 9 * * 0` | Sunday 09:00 — week kickoff plan |
| `30 16 * * 4` | Thursday 16:30 — weekly review before the weekend |
| `0 20 * * 6` | Saturday 20:00 — week-ahead preview |
| `0 21 * * *` | nightly 21:00 — tomorrow preview / journal prompt |
| `15 6 * * 0,2,4` | Sun/Tue/Thu 06:15 — workout nudge |
| `0 18 * * 1,3` | Mon & Wed 18:00 — evening class reminder |
| `0 */2 * * *` | every 2 hours, on the hour — monitor (price, inbox) |
| `*/30 9-18 * * 0-4` | every 30 min, 09:00–18:30, workdays — hot watch |
| `0 8 1 * *` | 1st of month 08:00 — monthly finance review |
| `0 16 15 * *` | 15th of month 16:00 — mid-month budget check |
| `0 9 1 1,4,7,10 *` | quarterly (Jan/Apr/Jul/Oct 1st) 09:00 — goals review |
| `0 12 * * 5` | Friday 12:00 — weekend plan suggestions |
| `45 23 28 * *` | 28th 23:45 — pre-month-end sweep (28 exists in every month) |

Good routine prompt (self-contained, output-shaped):
```
create_routine(
  name="Morning brief",
  cron="0 7 * * 0-4",
  prompt="Summarize today for Kevyn: calendar events with times, unread
  important emails (sender + one line), and Tel Aviv weather. Max 6 lines,
  lead with the single most urgent item.")
```
Bad: "Send the usual update" / "Check on the thing we discussed" — headless
runs have no conversation context.

Lifecycle: `list_routines` shows `last_run_at` + `last_result` — check it when
a routine misbehaves. `pause_or_resume_routine(routine_id, enabled=False)` for
vacations; `delete_routine` (ask first) when a dated project ends.
