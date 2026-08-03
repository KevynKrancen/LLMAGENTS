---
name: morning-brief
description: Compose the daily morning brief — calendar, important email, weather, one heads-up. Use for routines or "what's my day".
---

# Morning Brief

Compose in this order, skipping empty sections:

1. **Today** — list_calendar_events(days_ahead=1); times + titles only.
2. **Inbox** — list_gmail_messages("in:inbox is:unread newer_than:1d") and
   unread Apple Mail; mention only what looks important (people > newsletters).
3. **Weather** — search_web("weather today <user city>"); one line.
4. **Heads-up** — recall_memories("upcoming deadlines birthdays goals");
   surface at most one timely item.

Format: short markdown, bold section labels, no preamble, under 120 words.
Tone: calm and energizing. For a routine run, the text IS the push
notification body — lead with the single most useful fact.
