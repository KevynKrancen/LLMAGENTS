# Routine delivery — the scheduled brief

How the headless morning-brief routine works in THIS codebase
(`assistant/routines/manager.py`, `assistant/server/app.py`,
`assistant/server/push.py`), and the exact calls to set it up.

## What a routine run is

- Fires on cron (APScheduler, timezone Asia/Jerusalem) → runs its `prompt`
  in a **fresh thread with no chat history**. Your bounded MEMORY/USER
  files and mem0 context ARE still injected, and skills still load — the
  prompt can (and should) say "follow the morning-brief skill".
- Toolset = CORE_TOOLS + installed connector tools. **Absent**: routine
  management tools (recursion guard) and ALL frontend tools —
  `render_component` and `show_*` do not exist; a call to them fails.
- **No approval interrupts in routine mode** (`interrupt_on=None`): a
  `send_gmail`/`send_whatsapp_message` there fires unguarded. A brief
  reads and summarizes; it never sends.
- Delivery chain for the run's final AI text:
  1. Stored on the routine as `last_result` (truncated to 2000 chars).
  2. A receipt in the ledger: `"<name> — <first 90 chars>"`.
  3. APNs push: title = routine name, **body = first 180 chars**.
  4. If the daily push budget is spent, the push is skipped silently and
     only the ledger receipt remains — the text must stand on its own.

## Setting it up

Check for an existing brief first — `list_routines()` — and never create a
duplicate. Then:

```
create_routine(
  name="Morning brief",
  cron="0 7 * * sun-thu",
  prompt="Compose my morning brief for today. Follow the morning-brief \
skill in routine mode: fetch today's calendar, triage unread email \
(highlight at most 3), one line of weather, and at most one heads-up \
from memory. Output plain text only. The FIRST sentence must carry the \
single most useful fact of my day and stand alone under 180 characters. \
Do not send any emails or messages."
)
```

The prompt must be fully standalone — the run has no conversation to
lean on. Restate the output contract inside it; do not assume the skill
alone will be read before the model starts acting.

### Cron cookbook — WEEKDAY NUMBERS ARE A TRAP

Cron is validated and scheduled with APScheduler's
`CronTrigger.from_crontab(cron, timezone="Asia/Jerusalem")`. Times are
**local** — never convert to UTC. But APScheduler numbers weekdays
**Monday=0**, while standard crontab uses Sunday=0, and `from_crontab`
does NOT translate: numeric day-of-week values shift by one day.
**Always write weekday names**, never numbers:

| Schedule                          | cron                |
|-----------------------------------|---------------------|
| Every day 7:00                    | `0 7 * * *`         |
| Israeli work week (Sun–Thu) 7:00  | `0 7 * * sun-thu`   |
| Mon–Fri 7:00                      | `0 7 * * mon-fri`   |
| Weekend late brief (Fri–Sat 9:30) | `30 9 * * fri,sat`  |
| Weekly review, Friday 18:30       | `30 18 * * fri`     |

5 fields exactly (`minute hour day month day_of_week`); anything else is
rejected at create time. Misfire grace is 300s — a briefly-down server
still delivers, a long outage skips that morning silently.

## Shaping the text for push

```
Busy one: 5 meetings from 9:00, and Sarah's Q3 contract needs your signature today.

Schedule — Standup 9:00 · Design review 10:30 (overlaps your 11:00) ·
1:1 Omer 11:00 · Investor call 15:00 · Gym 18:30.
Inbox — Sarah Cohen: contract signature due today; AWS: budget at 92%.
12 others, nothing urgent.
Weather — ⛅ 26°, dry all day.
Heads-up — Dana's birthday tomorrow, no gift yet.
```

- Line 1 = the push body. One sentence, ≤180 chars, no markdown, no
  section label — it competes with every other lock-screen notification.
- The rest renders in the routine's `last_result` and the ledger; keep it
  scannable (the `·` separator survives everywhere, tables don't).
- Quiet day lead: "Clear until 16:00 — inbox is clean too." Never pad a
  quiet day to look productive.

## Managing and debugging

- `list_routines()` → `{id, name, cron, prompt, enabled, last_run_at,
  last_result}`. `last_result` is the full text of the last run — read it
  before touching anything; most "broken brief" reports are a bad lead
  sentence, not a failed run. `"Routine failed: <exc>"` there means the
  run itself crashed.
- Pause/resume: `pause_or_resume_routine(routine_id, enabled=False|True)`.
- There is NO update tool: to change cron or prompt, `delete_routine(id)`
  (ask the user first) then `create_routine(...)` with the new values.
- To preview output, run the routine's prompt inline in chat but compose
  text-only (no card) — that is what the headless run will produce.
- No push arriving while `last_run_at` advances: either the push budget
  was spent that day or APNs isn't configured — the brief still ran;
  check `last_result` before declaring it broken.
