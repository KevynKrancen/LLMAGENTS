# Component patterns — complete copy-paste HTML

Every template below is a full `html` argument for `render_component`. Adapt
the data, keep the structure. Each component is its own WebView document, so
the `<style>` block and short class names never collide with anything.

## What the host injects (do not repeat it)

Your markup lands inside this document (HermesApp/src/components/HtmlComponentCard.tsx):

```css
:root{ color-scheme:light|dark;
  --bg --surface --surface-alt --text --subtle --accent
  --hairline --danger --success }          /* exact palette per theme */
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui;background:transparent;
     color:var(--text);font-size:14px;line-height:1.5;padding:2px}
```

Palette for intuition (HermesApp/src/theme/tokens.ts): warm off-white bg,
near-black text, bronze accent (#B08D57 light / #C9A265 dark), muted green
success, muted red danger. Never hard-code these — the vars flip per theme.

## Shared recipes (used throughout)

```css
/* Quiet action chip — the ONLY button style */
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);
      border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
/* Micro label */
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle)}
/* One-line truncation */
.trunc{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* Two-line clamp (titles) */
.clamp2{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
/* Accent tint (WKWebView supports color-mix; var(--surface-alt) is the plain fallback) */
background:color-mix(in srgb,var(--accent) 12%,transparent);
```

Row lists: `border-bottom:1px solid var(--hairline)` on rows +
`:last-of-type{border-bottom:0}`. Tappable rows: put the `hermes://` href on a
block-level `<a>` with `text-decoration:none;color:var(--text)` — and never
nest another `<a>` inside it.

---

## 1. Weather

Hero temp + tinted sky header (a gradient that carries meaning), day chips.
Hero taps into the Weather app.

```html
<style>
.wx{padding:14px}
.now{display:flex;align-items:center;gap:14px;padding:14px;border-radius:12px;
     text-decoration:none;color:var(--text);
     background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 16%,transparent),transparent 70%)}
.gl{font-size:32px;line-height:1}
.t{font-size:34px;font-weight:600;line-height:1;font-variant-numeric:tabular-nums}
.c{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle);margin-top:5px}
.days{display:flex;gap:6px;margin-top:12px}
.d{flex:1;text-align:center;background:var(--surface-alt);border-radius:10px;padding:8px 2px}
.d .n{font-size:11px;color:var(--subtle)}
.d .g{font-size:15px;margin:3px 0}
.d .hi{font-size:12px;font-variant-numeric:tabular-nums}
.d .lo{color:var(--subtle)}
</style>
<div class="wx">
  <a class="now" href="hermes://open?url=weather%3A%2F%2F">
    <span class="gl">⛅</span>
    <span><span class="t">23°</span><div class="c">Tel Aviv · Partly cloudy · H 26° L 19°</div></span>
  </a>
  <div class="days">
    <div class="d"><div class="n">Mon</div><div class="g">☀</div><div class="hi">27° <span class="lo">19°</span></div></div>
    <div class="d"><div class="n">Tue</div><div class="g">☀</div><div class="hi">28° <span class="lo">20°</span></div></div>
    <div class="d"><div class="n">Wed</div><div class="g">⛅</div><div class="hi">26° <span class="lo">19°</span></div></div>
    <div class="d"><div class="n">Thu</div><div class="g">☂</div><div class="hi">22° <span class="lo">17°</span></div></div>
    <div class="d"><div class="n">Fri</div><div class="g">☀</div><div class="hi">25° <span class="lo">18°</span></div></div>
  </div>
</div>
```

Rain variant: swap gradient tint toward a cool subtle tone by mixing
`var(--subtle)` instead of `var(--accent)`. Hourly variant: replace `.days`
with hour chips (`14:00 / ☂ / 21°`).

## 2. Inbox digest

Unread dot in accent, sender 600, quiet preview, per-row `say` chips.
Data from `list_gmail_messages` / `list_apple_mail_messages`.

```html
<style>
.in{padding:4px 14px 12px}
.hd{display:flex;justify-content:space-between;align-items:baseline;padding:10px 0 4px}
.hd b{font-size:13px}
.hd a{font-size:11px;color:var(--subtle);text-decoration:none}
.m{padding:10px 0;border-bottom:1px solid var(--hairline)}
.m:last-of-type{border-bottom:0}
.r{display:flex;align-items:center;gap:7px}
.dot{width:6px;height:6px;border-radius:3px;background:var(--accent);flex:none}
.fr{font-weight:600;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wh{font-size:11px;color:var(--subtle);flex:none}
.sj{font-size:13px;margin-top:2px}
.pv{font-size:12px;color:var(--subtle);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chips{display:flex;gap:6px;margin-top:7px}
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
</style>
<div class="in">
  <div class="hd"><b>Inbox · 3 unread</b><a href="hermes://open?url=message%3A%2F%2F">Open Mail ↗</a></div>
  <div class="m">
    <div class="r"><span class="dot"></span><span class="fr">Sarah Chen</span><span class="wh">9:12</span></div>
    <div class="sj">Q3 budget — final numbers</div>
    <div class="pv">Attached the final sheet, need your sign-off before Thursday's…</div>
    <div class="chips">
      <a class="chip" href="hermes://say?text=Summarize%20Sarah%20Chen's%20email%20about%20the%20Q3%20budget">Summarize</a>
      <a class="chip" href="hermes://say?text=Draft%20a%20reply%20to%20Sarah%20Chen's%20Q3%20budget%20email">Reply</a>
    </div>
  </div>
  <div class="m">
    <div class="r"><span class="dot"></span><span class="fr">Stripe</span><span class="wh">8:47</span></div>
    <div class="sj">Invoice #1284 payment failed</div>
    <div class="pv">The payment for invoice #1284 ($240.00) could not be processed…</div>
    <div class="chips">
      <a class="chip" href="hermes://say?text=What%20happened%20with%20the%20Stripe%20invoice%20%231284%3F">Details</a>
    </div>
  </div>
  <div class="m">
    <div class="r"><span class="dot"></span><span class="fr">GitHub</span><span class="wh">7:30</span></div>
    <div class="sj">[LLMAGENTS] 2 PRs awaiting your review</div>
    <div class="pv">deepagents-upgrade and fix/session-log are ready for review…</div>
  </div>
  <a class="chip" style="display:inline-block;margin-top:10px"
     href="hermes://say?text=Show%20me%20the%20next%205%20emails">Show 5 more</a>
</div>
```

Show at most 3–5 rows; the "Show 5 more" chip is the pagination.

## 3. Schedule / agenda

Right-aligned time gutter, 2px accent left border on events, free time as a
quiet ghost row. Data from `list_calendar_events` / `find_free_time_slots`.

```html
<style>
.sc{padding:10px 14px 12px}
.h{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle);padding:4px 0 8px}
.ev{display:flex;gap:10px;padding:5px 0}
.t{width:48px;flex:none;font-size:12px;color:var(--subtle);text-align:right;
   font-variant-numeric:tabular-nums;padding-top:2px}
.b{flex:1;border-left:2px solid var(--accent);padding:1px 0 1px 10px;min-width:0}
.ti{font-size:14px;font-weight:600}
.lo{font-size:12px;color:var(--subtle);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.free .b{border-left-color:var(--hairline)}
.free .ti{font-weight:400;font-size:12px;color:var(--subtle)}
.chips{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
</style>
<div class="sc">
  <div class="h">Today · Mon Aug 3</div>
  <div class="ev"><div class="t">09:00</div><div class="b"><div class="ti">Team standup</div><div class="lo">Meet · 25 min</div></div></div>
  <div class="ev free"><div class="t"></div><div class="b"><div class="ti">2h free — deep work?</div></div></div>
  <div class="ev"><div class="t">12:30</div><div class="b"><div class="ti">Lunch with Dana</div><div class="lo">Café Noir, Ahad Ha'Am 43</div></div></div>
  <div class="ev"><div class="t">15:00</div><div class="b"><div class="ti">Q3 budget review</div><div class="lo">Zoom · 1h</div></div></div>
  <div class="chips">
    <a class="chip" href="hermes://open?url=calshow%3A%2F%2F">Open Calendar ↗</a>
    <a class="chip" href="hermes://open?url=maps%3A%3Fq%3DCaf%C3%A9%20Noir%20Ahad%20Ha'Am%2043">Route to lunch ↗</a>
    <a class="chip" href="hermes://say?text=Block%20the%20free%202%20hours%20this%20morning%20for%20deep%20work">Block free time</a>
  </div>
</div>
```

## 4. Stat tiles

2-column grid, one full-width hero tile, ▲▼ deltas in success/danger.
Tiles can be tappable drill-downs.

```html
<style>
.st{padding:14px;display:grid;grid-template-columns:1fr 1fr;gap:8px}
.tile{background:var(--surface-alt);border-radius:12px;padding:12px;text-decoration:none;color:var(--text)}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--subtle)}
.val{font-size:26px;font-weight:600;line-height:1.15;margin-top:4px;font-variant-numeric:tabular-nums}
.d{font-size:12px;margin-top:2px;font-variant-numeric:tabular-nums}
.up{color:var(--success)}.dn{color:var(--danger)}
.wide{grid-column:1/-1}
</style>
<div class="st">
  <div class="tile wide"><div class="lbl">Portfolio</div><div class="val">$48,210</div><div class="d up">▲ 1.8% today</div></div>
  <a class="tile" href="hermes://say?text=Details%20on%20my%20AAPL%20position">
    <div class="lbl">AAPL</div><div class="val">$229.14</div><div class="d up">▲ 2.4%</div></a>
  <a class="tile" href="hermes://say?text=Details%20on%20my%20NVDA%20position">
    <div class="lbl">NVDA</div><div class="val">$182.06</div><div class="d dn">▼ 0.9%</div></a>
</div>
```

Works for any KPI set: sleep/steps, site analytics, spend by category. Hero
value 26px in tiles, up to 34px if there is only one number that matters.

## 5. Comparison (two options)

Side-by-side columns, winner marked by accent border + tinted badge, decision
chips underneath.

```html
<style>
.cp{padding:14px}
.cols{display:flex;gap:8px}
.opt{flex:1;border:1px solid var(--hairline);border-radius:12px;padding:12px;min-width:0}
.best{border-color:var(--accent)}
.bdg{display:inline-block;font-size:10px;text-transform:uppercase;letter-spacing:.06em;
     color:var(--accent);background:color-mix(in srgb,var(--accent) 12%,transparent);
     border-radius:999px;padding:2px 8px;margin-bottom:6px}
.nm{font-size:14px;font-weight:600}
.pr{font-size:22px;font-weight:600;margin:6px 0 8px;font-variant-numeric:tabular-nums}
.kv{font-size:12px;display:flex;justify-content:space-between;gap:6px;padding:3px 0;border-top:1px solid var(--hairline)}
.kv span{color:var(--subtle)}
.chips{display:flex;gap:6px;margin-top:10px}
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
</style>
<div class="cp">
  <div class="cols">
    <div class="opt best">
      <div class="bdg">Best overall</div>
      <div class="nm">El Al LY315</div><div class="pr">$412</div>
      <div class="kv"><span>Depart</span><b>09:40</b></div>
      <div class="kv"><span>Duration</span><b>4h 55m</b></div>
      <div class="kv"><span>Stops</span><b>Nonstop</b></div>
    </div>
    <div class="opt">
      <div style="height:22px"></div>
      <div class="nm">Lufthansa LH687</div><div class="pr">$356</div>
      <div class="kv"><span>Depart</span><b>06:10</b></div>
      <div class="kv"><span>Duration</span><b>7h 30m</b></div>
      <div class="kv"><span>Stops</span><b>1 (FRA)</b></div>
    </div>
  </div>
  <div class="chips">
    <a class="chip" href="hermes://say?text=Book%20the%20El%20Al%2009%3A40%20flight">Take the 09:40</a>
    <a class="chip" href="hermes://say?text=Show%20more%20flight%20options%20for%20that%20day">More options</a>
  </div>
</div>
```

Three or more options: switch to stacked full-width rows (name left, price
right, one-line specs in subtle) — side-by-side columns fail below ~140px each.

## 6. Progress / tracker

Accent progress bar on a surface-alt track, checked milestones, one log action.

```html
<style>
.tk{padding:14px}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.gl{font-size:14px;font-weight:600}
.pc{font-size:13px;font-weight:600;color:var(--accent);font-variant-numeric:tabular-nums}
.bar{height:6px;border-radius:3px;background:var(--surface-alt);margin:10px 0 12px;overflow:hidden}
.fill{height:100%;border-radius:3px;background:var(--accent);width:64%}
.stp{display:flex;gap:8px;align-items:center;font-size:13px;padding:4px 0}
.ok{color:var(--success)}.td{color:var(--subtle)}
.pend .tx{color:var(--subtle)}
.chip{display:inline-block;font-size:11px;color:var(--subtle);border:1px solid var(--hairline);
      border-radius:999px;padding:3px 10px;text-decoration:none;margin-top:10px}
</style>
<div class="tk">
  <div class="top"><span class="gl">Half-marathon plan · Week 6 of 10</span><span class="pc">64%</span></div>
  <div class="bar"><div class="fill"></div></div>
  <div class="stp"><span class="ok">✓</span><span class="tx">Long run 14 km — Sunday</span></div>
  <div class="stp"><span class="ok">✓</span><span class="tx">Intervals 6×800 m — Tuesday</span></div>
  <div class="stp pend"><span class="td">○</span><span class="tx">Tempo 8 km — Thursday</span></div>
  <a class="chip" href="hermes://say?text=I%20finished%20Thursday's%20tempo%20run%2C%20log%20it">Mark tempo done</a>
</div>
```

Set the fill width inline (`style="width:64%"`) when generating from data.

## 7. List with actions

Each row carries the one action that resolves it — `say` for agent work,
`open` for phone work (a call, a route).

```html
<style>
.ls{padding:6px 14px 12px}
.hd{display:flex;justify-content:space-between;align-items:baseline;padding:8px 0}
.hd b{font-size:13px}
.cnt{font-size:11px;color:var(--subtle)}
.it{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--hairline);font-size:13px}
.it:last-of-type{border-bottom:0}
.tx{flex:1;min-width:0}
.sub{color:var(--subtle);font-size:11px}
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
.foot{margin-top:10px}
</style>
<div class="ls">
  <div class="hd"><b>Errands for today</b><span class="cnt">3 open</span></div>
  <div class="it"><div class="tx">Pick up dry cleaning<div class="sub">closes 19:00</div></div>
    <a class="chip" href="hermes://say?text=Mark%20%22pick%20up%20dry%20cleaning%22%20as%20done">Done</a></div>
  <div class="it"><div class="tx">Renew passport appointment</div>
    <a class="chip" href="hermes://say?text=Help%20me%20book%20the%20passport%20renewal%20appointment">Do it</a></div>
  <div class="it"><div class="tx">Call the plumber<div class="sub">+972 54 123 4567</div></div>
    <a class="chip" href="hermes://open?url=tel%3A%2B972541234567">Call ↗</a></div>
  <div class="foot">
    <a class="chip" href="hermes://say?text=Add%20all%20open%20errands%20to%20my%20iPhone%20Reminders">Add all to Reminders</a>
  </div>
</div>
```

## 8. Media card (video / track result)

No external images allowed, so the affordance IS the design: tinted play
block, clamped title, whole hit area opens playback directly (no agent
round-trip). Pair with `search_youtube_videos` for a real video_id.

```html
<style>
.md{padding:14px}
.hit{display:flex;gap:12px;align-items:center;text-decoration:none;color:var(--text)}
.play{width:44px;height:44px;flex:none;border-radius:12px;display:flex;align-items:center;
      justify-content:center;font-size:17px;color:var(--accent);
      background:color-mix(in srgb,var(--accent) 14%,transparent)}
.ti{font-size:14px;font-weight:600;line-height:1.35;
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.by{font-size:12px;color:var(--subtle);margin-top:2px}
.alts{display:flex;gap:6px;margin-top:12px}
.chip{font-size:11px;color:var(--subtle);border:1px solid var(--hairline);border-radius:999px;padding:3px 10px;text-decoration:none;flex:none}
</style>
<div class="md">
  <a class="hit" href="hermes://open?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DdQw4w9WgXcQ">
    <span class="play">▶</span>
    <span style="min-width:0"><span class="ti">Rick Astley — Never Gonna Give You Up (Official Video)</span>
      <div class="by">Rick Astley · 3:33 · 1.6B views</div></span>
  </a>
  <div class="alts">
    <a class="chip" href="hermes://say?text=Play%20the%20next%20search%20result%20instead">Not this one</a>
    <a class="chip" href="hermes://open?url=spotify%3Asearch%3Anever%20gonna%20give%20you%20up">Spotify ↗</a>
  </div>
</div>
```

Multiple results: stack 2–3 `.hit` rows with hairline separators, each with
its own encoded watch URL.

## 9. Hero answer (single fact)

Conversions, quick sums, "when is sunset" — one number, its context, one
follow-up.

```html
<style>
.he{padding:18px 16px 14px}
.big{font-size:30px;font-weight:600;font-variant-numeric:tabular-nums}
.big em{font-style:normal;color:var(--accent)}
.sub{font-size:12px;color:var(--subtle);margin-top:4px}
.chip{display:inline-block;font-size:11px;color:var(--subtle);border:1px solid var(--hairline);
      border-radius:999px;padding:3px 10px;text-decoration:none;margin-top:12px}
</style>
<div class="he">
  <div class="big">$1,000 = <em>₪3,712</em></div>
  <div class="sub">1 USD = 3.712 ILS · updated 10:04</div>
  <a class="chip" href="hermes://say?text=Convert%20%245%2C000%20to%20shekels%20at%20today's%20rate">Convert $5,000</a>
</div>
```

## Trimming to budget

When a component drifts past ~1600 chars: cut rows before cutting style (3
great rows beat 7 cramped ones); merge selectors; drop per-row actions and
keep one footer chip row; never cut the encoding of hrefs or the hairline
separators — they are what makes it read as native.
