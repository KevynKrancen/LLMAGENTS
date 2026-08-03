# Brief recipes — the full composition algorithm

Exact tool calls, triage heuristics, and three complete example briefs.
All tool signatures verified against `assistant/tools/{calendar,gmail,
apple_mail,web,memory}.py` and `assistant/integrations/catalog.py`.

## 0. The parallel fetch (one batch, five calls)

```
list_calendar_events(days_ahead=1, max_results=20)
list_gmail_messages(query="in:inbox is:unread newer_than:1d", max_results=15)
list_apple_mail_messages(max_results=10, unread_only=True)
get_weather_forecast(place="Tel Aviv", days=1)        # only if installed — see §3
recall_memories(query="deadlines birthdays travel commitments this week", limit=5)
```

Returns, in order: `[{id, summary, start, end, location}]`,
`[{id, from, subject, date, snippet}]`, `[{uid, from, subject, date,
preview}]`, `{place, current, daily}`, `[{id, memory, score}]`.
Any source that errors (Apple Mail unconfigured, weather tool absent) is
dropped silently — a brief never contains an error message.

## 1. Calendar

The window is **now → now+24h** in Asia/Jerusalem. At 07:00 that includes
tomorrow until 07:00, so filter:

- Keep events where `start` date-part == today.
- All-day events: `start` is `"2026-08-03"` (no `T`). Render as one line
  under the date ("All day: Company offsite"), not as a timed row.
- Timed events: `"2026-08-03T09:00:00+03:00"` → render `9:00` (24h clock).
- Overlap check: sort by start; if `start[i+1] < end[i]`, mark the later
  row `· overlaps HH:MM` in `var(--danger)`.
- Lead time: minutes from now to the first timed event; if <90, it belongs
  in the hero line ("First meeting in 40 min").

### Day-shape classification (decides hero + chips)

| Shape  | Rule (first match wins)                                          | Hero line                          | Chips to offer                       |
|--------|------------------------------------------------------------------|------------------------------------|--------------------------------------|
| travel | An event whose summary/location matches flight signals: "Flight", "✈", an IATA pair (TLV, CDG…), airline names, train/airport locations — or a trip surfaced by `recall_memories` dated today | Route + departure time             | Directions, check-in                 |
| busy   | ≥4 timed events, or total timed duration ≥5h, or any overlap      | Meeting count + first start        | Focus block, reply to top email      |
| quiet  | ≤1 timed event                                                    | The open time ("Clear until 16:00")| A goal nudge from memory             |
| normal | everything else                                                   | First event + count                | Reply / prep chips as data suggests  |

Busy day extra: `find_free_time_slots(date="2026-08-03",
duration_minutes=90)` → `[{start, end}]`; offer the first gap as a focus
block via a `hermes://say` chip. (Defaults scan 9:00–21:00; pass
`day_start_hour`/`day_end_hour` to narrow.)

## 2. Email triage

### Gmail query cookbook

| Situation                          | `query`                                                        |
|------------------------------------|----------------------------------------------------------------|
| Baseline morning sweep             | `in:inbox is:unread newer_than:1d`                             |
| First workday after weekend (Sunday in Israel) | `in:inbox is:unread newer_than:3d`                 |
| Cut marketing noise at the source  | `in:inbox is:unread newer_than:1d category:primary`            |
| VIP check (addresses from USER profile) | `from:(sarah@client.com OR omer@acme.com) newer_than:2d`  |
| Anything with documents            | `in:inbox is:unread has:attachment newer_than:1d`              |

`max_results` caps at 25 in the tool; 15 is plenty for a brief.

### Sender classes

| Class | Who                        | Signals in `from`                                                                 |
|-------|----------------------------|-----------------------------------------------------------------------------------|
| A     | A real human               | `First Last <name@domain>`, personal Gmail/Outlook, a company address that is a person's name, anyone in the USER profile or past threads |
| B     | Transactional / operational| Bookings, invoices, security alerts, calendar invites, delivery + billing notices (`billing@`, `security@`, `receipts@`) |
| C     | Bulk                       | `no-reply@`, `noreply@`, `notifications@`, `newsletter@`, `marketing@`, `hello@`, social-network notifiers |

### Thread signals (each promotes one level)

- Subject starts `Re:` / `Fwd:` — a live conversation waiting on someone.
- Snippet addresses the user by name ("Kevyn, …") or asks a direct question.
- Deadline vocabulary in subject/snippet: today, tomorrow, EOD, by Friday,
  urgent, reminder, expiring, final, action required.
- Calendar invite markers: "Invitation:", "invite.ics", "Accepted:".

### Decision rule

- **A + any signal → always highlight** (these lead the inbox section).
- **A alone → highlight** if space remains.
- **B → highlight only if actionable today** (flight check-in, payment due
  today, security alert). Otherwise fold into the count.
- **C → never highlight.** Count only.
- Hard cap: 3 highlights. Everything else: "+N others, nothing urgent."
- Merge Apple Mail using the same classes; dedupe on (from, subject).
- `read_gmail_message(message_id)` ONLY for a highlight whose snippet is
  not enough to state the ask ("needs your signature today").

## 3. Weather

**Connector path** (preferred): the `weather` builtin (Open-Meteo, keyless)
exists only when installed via the app platform — if `get_weather_forecast`
is not in your toolset, do NOT call it, use the fallback.

```
get_weather_forecast(place="Tel Aviv", days=1)
→ {"place": "Tel Aviv",
   "current": {"temperature_2m": 26.1, "weather_code": 2, "wind_speed_10m": 14.2},
   "daily": {"temperature_2m_max": [28.4], "temperature_2m_min": [21.0],
             "precipitation_probability_max": [10]}}
```

WMO `weather_code` → glyph/word:

| Code   | Render      | Code   | Render        |
|--------|-------------|--------|---------------|
| 0      | ☀ Clear     | 61–67  | ☂ Rain        |
| 1–2    | ⛅ Partly    | 71–77  | ❄ Snow        |
| 3      | ☁ Overcast  | 80–82  | ☂ Showers     |
| 45,48  | Fog         | 95–99  | ⛈ Thunder     |
| 51–57  | ☂ Drizzle   |        |               |

Mention rain only when `precipitation_probability_max[0] ≥ 40` ("☂ 60% —
take a jacket"); heat only when max ≥ 33°.

**Fallback path**: `search_web(query="weather today Tel Aviv",
max_results=3)` → use the `answer` field, compress to one line. Never
fetch result pages for weather.

**Travel day**: fetch the DESTINATION city too and show it instead of (or
beside) home weather — that is the forecast that matters.

## 4. Heads-up

`recall_memories("deadlines birthdays travel commitments this week",
limit=5)` → pick EXACTLY ONE by priority:

1. Hard deadline today/tomorrow (from memory or a triaged email).
2. Birthday/anniversary within 2 days.
3. Prep for tomorrow's early or unusual event ("8:00 flight tomorrow —
   pack tonight").
4. Quiet day only: a standing-goal nudge ("Mornings were for the thesis —
   today is wide open").

Skip the section entirely if nothing is timely or scores are weak
(≲0.4). A stretch heads-up reads as noise and erodes trust in the brief.

## 5. Three complete example briefs (chat mode)

Full `render_component` calls. Design rules come from the component-design
skill: injected vars only, hairline borders, one hero, every action a
fully-encoded `hermes://` link, ≲550px tall. Swap the data, keep the bones.

### 5a. Busy day

`render_component(title="Morning brief — busy day", html=...)`:

```html
<style>
.mb{padding:14px}
.top{display:flex;justify-content:space-between;align-items:center}
.dt{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle)}
.wx{font-size:13px;color:var(--subtle);text-decoration:none}
.hero{font-size:21px;font-weight:600;margin:4px 0 8px}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle);margin:12px 0 2px}
.row{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--hairline);text-decoration:none;color:var(--text)}
.row:last-of-type{border-bottom:0}
.tm{width:44px;flex:none;font-size:12px;color:var(--subtle);font-variant-numeric:tabular-nums}
.ti{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.sub{font-size:12px;color:var(--subtle)}
.warn{color:var(--danger)}
.chips{display:flex;gap:6px;margin-top:12px;flex-wrap:wrap}
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
.chip.a{color:var(--accent);border-color:var(--accent)}
</style>
<div class="mb">
  <div class="top"><span class="dt">Mon · Aug 3</span>
    <a class="wx" href="hermes://open?url=weather%3A%2F%2F">⛅ 26°</a></div>
  <div class="hero">5 meetings — first at 9:00</div>
  <div class="lbl">Schedule</div>
  <div class="row"><span class="tm">9:00</span><span class="ti">Team standup</span></div>
  <div class="row"><span class="tm">10:30</span><span class="ti">Design review <span class="sub warn">· overlaps 11:00</span></span></div>
  <div class="row"><span class="tm">11:00</span><span class="ti">1:1 with Omer</span></div>
  <div class="row"><span class="tm">15:00</span><span class="ti">Investor call <span class="sub">· Zoom</span></span></div>
  <div class="row"><span class="tm">18:30</span><span class="ti">Gym</span></div>
  <div class="lbl">Inbox — 2 of 14 need you</div>
  <a class="row" href="hermes://say?text=Summarize%20Sarah%20Cohen%27s%20Q3%20contract%20email">
    <span class="ti"><b>Sarah Cohen</b> — Re: Q3 contract <span class="sub">· signature due today</span></span></a>
  <a class="row" href="hermes://say?text=Summarize%20the%20AWS%20billing%20alert">
    <span class="ti"><b>AWS</b> — Billing alert <span class="sub">· budget at 92%</span></span></a>
  <div class="lbl">Heads-up</div>
  <div class="sub">Dana's birthday tomorrow — no gift yet.</div>
  <div class="chips">
    <a class="chip a" href="hermes://say?text=Draft%20a%20reply%20to%20Sarah%20confirming%20I%27ll%20sign%20the%20Q3%20contract%20today">Reply to Sarah</a>
    <a class="chip" href="hermes://say?text=Block%2090%20minutes%20of%20focus%20time%20in%20my%20first%20free%20slot%20today">Block focus time</a>
    <a class="chip" href="hermes://say?text=Find%20a%20birthday%20gift%20for%20Dana">Gift ideas</a>
  </div>
</div>
```

Chat line: "Busy one — 5 meetings from 9:00, and Sarah's contract needs
your signature today."

### 5b. Quiet day

Weather becomes the hero; the open time is the story.

```html
<style>
.mb{padding:14px}
.dt{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle)}
.now{display:flex;align-items:center;gap:14px;margin:8px 0 4px;padding:14px;border-radius:12px;text-decoration:none;color:var(--text);background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 14%,transparent),transparent 70%)}
.gl{font-size:30px;line-height:1}
.t{font-size:32px;font-weight:600;line-height:1;font-variant-numeric:tabular-nums}
.c{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle);margin-top:5px}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle);margin:12px 0 2px}
.row{display:flex;gap:10px;align-items:baseline;padding:6px 0}
.tm{width:44px;flex:none;font-size:12px;color:var(--subtle);font-variant-numeric:tabular-nums}
.ti{font-size:14px}
.ok{color:var(--success);font-size:13px;padding:6px 0}
.sub{font-size:12px;color:var(--subtle)}
.chips{display:flex;gap:6px;margin-top:12px}
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
.chip.a{color:var(--accent);border-color:var(--accent)}
</style>
<div class="mb">
  <span class="dt">Sat · Aug 8</span>
  <a class="now" href="hermes://open?url=weather%3A%2F%2F">
    <span class="gl">☀</span>
    <span><span class="t">27°</span><div class="c">Tel Aviv · Clear · H 29° L 21°</div></span>
  </a>
  <div class="lbl">Schedule — clear until 16:00</div>
  <div class="row"><span class="tm">16:00</span><span class="ti">Coffee with Tomer <span class="sub">· Dizengoff</span></span></div>
  <div class="lbl">Inbox</div>
  <div class="ok">✓ Clear — nothing new needs you.</div>
  <div class="lbl">Heads-up</div>
  <div class="sub">You wanted mornings for the thesis — today is wide open.</div>
  <div class="chips">
    <a class="chip a" href="hermes://say?text=Start%20a%2090-minute%20focus%20block%20for%20thesis%20writing">Focus block</a>
    <a class="chip" href="hermes://say?text=What%27s%20the%20beach%20forecast%20for%20this%20afternoon%3F">Beach later?</a>
  </div>
</div>
```

Chat line: "Wide open until 16:00 — a good thesis morning."

### 5c. Travel day

Flight is the hero; weather shown for the DESTINATION; logistics chips.

```html
<style>
.mb{padding:14px}
.dt{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle)}
.fl{display:block;margin:8px 0 4px;padding:14px;border-radius:12px;text-decoration:none;color:var(--text);background:color-mix(in srgb,var(--accent) 12%,transparent)}
.rt{font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}
.fs{font-size:12px;color:var(--subtle);margin-top:4px}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle);margin:12px 0 2px}
.row{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--hairline);text-decoration:none;color:var(--text)}
.row:last-of-type{border-bottom:0}
.tm{width:52px;flex:none;font-size:12px;color:var(--subtle);font-variant-numeric:tabular-nums}
.ti{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.sub{font-size:12px;color:var(--subtle)}
.chips{display:flex;gap:6px;margin-top:12px}
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
.chip.a{color:var(--accent);border-color:var(--accent)}
</style>
<div class="mb">
  <span class="dt">Thu · Aug 13 · Travel day</span>
  <a class="fl" href="hermes://say?text=Show%20my%20flight%20details%20for%20today">
    <div class="rt">TLV → CDG</div>
    <div class="fs">LY 325 · departs 14:40 · Terminal 3 · lands 18:35</div>
  </a>
  <div class="row"><span class="tm">12:10</span><span class="ti">Leave for the airport <span class="sub">· 35 min drive</span></span></div>
  <div class="row"><span class="tm">Paris</span><span class="ti">☂ 18° · 60% rain <span class="sub">· pack a jacket</span></span></div>
  <div class="lbl">Inbox — 1 of 6 matters</div>
  <a class="row" href="hermes://say?text=Summarize%20the%20Hotel%20Malte%20booking%20confirmation">
    <span class="ti"><b>Hotel Malte</b> — Booking confirmed <span class="sub">· check-in from 15:00</span></span></a>
  <div class="lbl">Heads-up</div>
  <div class="sub">Passport + charger — you flagged both last trip.</div>
  <div class="chips">
    <a class="chip a" href="hermes://open?url=https%3A%2F%2Fmaps.apple.com%2F%3Fdaddr%3DBen%2BGurion%2BAirport">Directions to TLV</a>
    <a class="chip" href="hermes://open?url=https%3A%2F%2Fwww.elal.com%2Fen%2Fcheck-in">Check in</a>
  </div>
</div>
```

Chat line: "Travel day — LY 325 to Paris at 14:40; leave by 12:10. Rain
in Paris, pack a jacket."

### Adapting the examples

- Keep the section ORDER fixed (schedule → inbox → heads-up); shape
  varies only in the hero and chips.
- Row budget for ≲550px: hero + ~7 rows + chips. Busy days cut events,
  not inbox highlights ("+1 later" beats an inner scroll).
- Every chip must be something Hermes (or a deep link) can actually do —
  a dead chip is worse than none.
- Routine mode reuses the same COMPOSITION, rendered as plain text — see
  references/routine-delivery.md for the exact text shape.
