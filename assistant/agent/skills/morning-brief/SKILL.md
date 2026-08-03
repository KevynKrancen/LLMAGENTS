---
name: morning-brief
description: Compose the daily brief — today's schedule, triaged email, weather, one heads-up. Use for "what's my day", morning routine runs, or setting up a scheduled daily brief.
---

# Morning Brief

## When to Use
- User asks "what's my day", "morning brief", "catch me up".
- A routine fires with a brief-like prompt (headless run).
- User wants a scheduled daily brief created, changed, or debugged —
  read references/routine-delivery.md before touching create_routine.

Two delivery modes; decide FIRST, it changes the output format:
- **Chat**: one `render_component` card + one short sentence. Copy the
  closest example brief (busy / quiet / travel) from
  references/brief-recipes.md and swap in real data.
- **Routine (headless)**: `render_component` and all `show_*` tools do not
  exist there. The final text IS the deliverable — its first ~180 chars
  become the push notification body, the rest lands in the routine's
  `last_result` and the ledger.

## Procedure
1. **Anchor**: today's date and time in Asia/Jerusalem. City comes from the
   USER profile already in context; if absent, `recall_memories("home city",
   limit=3)`. Never guess a city.
2. **Fetch everything in ONE parallel tool batch**:
   - `list_calendar_events(days_ahead=1, max_results=20)`
   - `list_gmail_messages(query="in:inbox is:unread newer_than:1d",
     max_results=15)` — first workday after a weekend: `newer_than:3d`
   - `list_apple_mail_messages(max_results=10, unread_only=True)`
   - Weather: `get_weather_forecast(place=<city>, days=1)` if that tool is
     in your toolset (weather app installed); otherwise
     `search_web(query="weather today <city>", max_results=3)`
   - `recall_memories("deadlines birthdays travel commitments this week",
     limit=5)`
3. **Filter + classify the day**: keep only events whose start date is
   today (the 24h window leaks tomorrow-morning events); all-day events
   have a date-only `start` (no `T`). Classify the day shape — busy /
   quiet / travel — per the table in references/brief-recipes.md §1; it
   decides the card's hero and which chips to offer. On a busy day,
   optionally `find_free_time_slots(date=<today>, duration_minutes=90)`
   to propose a focus block.
4. **Triage email**: bucket every message by sender class (human >
   transactional > bulk) and thread signals (Re:, direct address,
   deadline words). Highlight at most 3, count the rest. Full heuristics
   and Gmail query cookbook: references/brief-recipes.md §2. Call
   `read_gmail_message` only for a message you will summarize beyond its
   snippet.
5. **Compose** in fixed order, silently skipping empty sections:
   Schedule → Inbox (≤3 + "+N others") → Weather (one line, umbrella /
   heat warning only when the data says so) → ONE heads-up (soonest hard
   deadline > birthday ≤2 days > prep for tomorrow's early start).
6. **Deliver**:
   - Chat: `render_component(title="Morning brief", html=…)` + one calm
     sentence ("Busy one — 5 meetings, first at 9:00.").
   - Routine: plain text; the FIRST sentence must carry the single most
     useful fact of the day and stand alone under 180 chars.

## Pitfalls
- `days_ahead=1` means now→+24h, not "today" — always re-filter by date.
- Apple Mail raises when ICLOUD_* env is unconfigured — skip that source
  silently; never surface a config error inside a brief.
- Calling `get_weather_forecast` when the weather app isn't installed
  fails — check your toolset first, fall back to `search_web`.
- Never invent data: an empty calendar or inbox is good news, say so
  ("Nothing scheduled. Inbox is clear."), don't pad with filler.
- Exactly one heads-up. A memory dump is not a brief.
- Never send anything outward (email/WhatsApp) from a brief — routines
  run without approval sheets, so a send there is unguarded.
- In chat, every card action must be a `hermes://say` or `hermes://open`
  link, fully URL-encoded (component-design skill rules apply).

## Verification
- Every event, sender, temperature, and count traces to a tool result
  from THIS run — nothing remembered, nothing assumed.
- ≤3 emails highlighted; unhighlighted ones are counted, not listed.
- Chat card: fits 300px wide, ≲550px tall, only injected CSS vars.
- Routine text: read the first 180 chars alone — if they don't tell the
  user the one thing they need this morning, rewrite the lead.
