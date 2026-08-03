# Dashboard HTML templates — Polymarket, Budget, Tutor

Facts that shape these templates (from `ArtifactCanvas.tsx` / `space/[id].tsx`):
- Your `content` becomes the **body innerHTML** of a WebView page. The app
  injects only `:root{color-scheme:…}` and `body{font-family:-apple-system;
  margin:16px}` — no theme variables reach artifacts, so every dashboard
  carries its own `<style>` (a `<style>` tag inside body works and, coming
  later in the document, overrides the injected body margin).
- The folder screen shows a **300px-tall preview** (tap → full screen):
  hero numbers in the first block, tables/lists below the fold.
- No JS is needed; no network calls, images, or fonts will load. Action
  links (`hermes://…`) do NOT work here — display only.
- Updates are full replacement: regenerate the whole document from the
  domain's `/skills/<domain>/*.md` state and call
  `update_artifact(artifact_id, content)`.

## Base block — paste at the top of every dashboard, then append one template

The exact Hermes palette (HermesApp/src/theme/tokens.ts), light + dark:

```html
<style>
:root{
  --bg:#FAFAF8; --surface:#FFFFFF; --surface-alt:#F4F3F0; --text:#111214;
  --subtle:#6B6E76; --accent:#B08D57; --on-accent:#FFFFFF;
  --hairline:#E7E5E0; --danger:#C0392B; --success:#2E7D5B;
}
@media (prefers-color-scheme: dark){:root{
  --bg:#0C0C0E; --surface:#16161A; --surface-alt:#1D1D22; --text:#F4F4F2;
  --subtle:#9A9DA6; --accent:#C9A265; --on-accent:#141414;
  --hairline:#26262B; --danger:#E06C5B; --success:#5BB08C;
}}
body{margin:0;padding:14px;background:var(--bg);color:var(--text);
  font-family:-apple-system,system-ui;-webkit-text-size-adjust:100%}
.card{background:var(--surface);border:1px solid var(--hairline);
  border-radius:14px;padding:14px 16px;margin-bottom:10px}
.label{font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--subtle);margin-bottom:4px}
.hero{font-size:30px;font-weight:600;line-height:1.1}
.row{display:flex;justify-content:space-between;align-items:baseline;
  padding:8px 0;border-bottom:1px solid var(--hairline);font-size:13px}
.row:last-child{border-bottom:0}
.sub{color:var(--subtle);font-size:12px}
.up{color:var(--success)} .down{color:var(--danger)}
.pill{font-size:12px;font-weight:600;border-radius:999px;padding:2px 10px;
  background:var(--surface-alt)}
.track{height:8px;border-radius:4px;background:var(--surface-alt);
  overflow:hidden;margin:10px 0 6px}
.fill{height:8px;border-radius:4px;background:var(--accent)}
</style>
```

No shadows, no gradients, color only where it means something (success/
danger for deltas, accent for the key figure or progress).

---

## 1 · Polymarket (`Finance/Polymarket`, title "Polymarket")

Data source: `/skills/polymarket/ledger.md`. Hero = bankroll value; the
P&L pill flips class `up`/`down` (and its ▲/▼) with the sign.

```html
<div class="card">
  <div class="label">Bankroll</div>
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div class="hero">$512.40</div>
    <span class="pill up">▲ $12.40 · 2.5%</span>
  </div>
  <div class="sub" style="margin-top:4px">Cash $362.40 · At risk $150.00 · Cap $500 · Max $50/position</div>
</div>

<div class="card">
  <div class="label">Open positions</div>
  <div class="row"><span><b>Fed cuts rates in Sept</b> · YES</span>
    <span>$50 @ .62 → .68 <span class="up">+$4.80</span></span></div>
  <div class="row"><span><b>BTC &gt; $100k Dec 31</b> · NO</span>
    <span>$50 @ .55 → .58 <span class="up">+$2.70</span></span></div>
  <div class="row"><span><b>US recession in 2026</b> · NO</span>
    <span>$50 @ .71 → .74 <span class="up">+$2.10</span></span></div>
</div>

<div class="card">
  <div class="label">Ledger — last actions</div>
  <div class="row"><span>Aug 2 · Bought NO · US recession 2026</span><span class="sub">$50 @ .71</span></div>
  <div class="row"><span>Aug 1 · Proposed YES · ECB hold <span class="sub">(declined)</span></span><span class="sub">—</span></div>
  <div class="row"><span>Jul 30 · Bought YES · Fed cuts Sept</span><span class="sub">$50 @ .62</span></div>
</div>

<div class="sub" style="text-align:center;padding:2px 0 8px">
  Every trade requires your explicit approval · updated Aug 3, 08:00</div>
```

---

## 2 · Budget (`Finance/Budget`, title "Budget")

Data source: `/skills/budget-coach/ledger.md`. `.fill` width =
spent/budget·100 (cap 100); give the fill `background:var(--danger)` when
over budget, and set the pace line (`on pace` / `running hot`) by comparing
spend% to day-of-month%. Category bar widths = category/its-share·100.

```html
<div class="card">
  <div class="label">August · spent so far</div>
  <div style="display:flex;justify-content:space-between;align-items:baseline">
    <div class="hero">$1,840</div>
    <div class="sub">of $3,000</div>
  </div>
  <div class="track"><div class="fill" style="width:61%"></div></div>
  <div class="sub">61% used · day 3 of 31 · <span class="down">running hot</span></div>
</div>

<div class="card">
  <div class="label">By category</div>
  <div class="row"><span>Food</span><span>$720</span></div>
  <div class="track" style="margin:2px 0 8px"><div class="fill" style="width:80%"></div></div>
  <div class="row"><span>Transport</span><span>$310</span></div>
  <div class="track" style="margin:2px 0 8px"><div class="fill" style="width:52%"></div></div>
  <div class="row"><span>Home</span><span>$540</span></div>
  <div class="track" style="margin:2px 0 8px"><div class="fill" style="width:60%"></div></div>
  <div class="row"><span>Fun</span><span>$270</span></div>
  <div class="track" style="margin:2px 0 0"><div class="fill" style="width:90%;background:var(--danger)"></div></div>
</div>

<div class="card">
  <div class="label">Recent</div>
  <div class="row"><span>Aug 3 · Groceries <span class="sub">food</span></span><span>$86</span></div>
  <div class="row"><span>Aug 2 · Fuel <span class="sub">transport</span></span><span>$64</span></div>
  <div class="row"><span>Aug 2 · Dinner out <span class="sub">fun</span></span><span>$92</span></div>
  <div class="row"><span>Aug 1 · Electricity <span class="sub">home</span></span><span>$140</span></div>
</div>
```

---

## 3 · Tutor (`Academy/Linear Algebra`, title "Linear Algebra")

Data source: `/skills/linear-algebra-tutor/progress.md`. The 12-segment
strip is one flex row: done segments get `background:var(--accent)`, the
current one `outline:2px solid var(--accent)` on `--surface-alt`, the rest
plain `--surface-alt`. Weeks-to-exam = (exam date − today) in whole weeks.

```html
<div class="card">
  <div class="label">Linear algebra · exam Oct 15</div>
  <div style="display:flex;justify-content:space-between;align-items:baseline">
    <div class="hero">Lesson 4 <span style="font-size:16px;color:var(--subtle);font-weight:400">of 12</span></div>
    <span class="pill">10 weeks left</span>
  </div>
  <div style="display:flex;gap:4px;margin-top:12px">
    <div style="flex:1;height:8px;border-radius:4px;background:var(--accent)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--accent)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--accent)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt);outline:2px solid var(--accent)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt)"></div>
    <div style="flex:1;height:8px;border-radius:4px;background:var(--surface-alt)"></div>
  </div>
  <div class="sub" style="margin-top:8px">Now: <b style="color:var(--text)">Matrix inverses</b> · next session opens with a recall quiz on matrix operations</div>
</div>

<div class="card">
  <div class="label">Study health</div>
  <div class="row"><span>Streak</span><span><b>3</b> sessions</span></div>
  <div class="row"><span>Next review due</span><span>Sun · Aug 9</span></div>
  <div class="row"><span>Weak topics</span><span class="down">span vs basis · det sign</span></div>
</div>

<div class="card">
  <div class="label">Recent lessons</div>
  <div class="row"><span>03 · Matrix operations</span><span class="up">quiz 3/3</span></div>
  <div class="row"><span>02 · Independence, span, basis</span><span class="down">quiz 1/3</span></div>
  <div class="row"><span>01 · Vectors &amp; spaces</span><span class="up">quiz 3/3</span></div>
</div>
```

---

## Adapting to a new domain
Keep the shape: one hero card (label → big number → one context line),
then 1-2 list/table cards, then a one-line footer with the update
timestamp. Swap only what the domain measures — a reading tracker's hero
is pages/week, a health domain's is the streak. Resist adding cards: three
is the ceiling; the dashboard is a face, not a report.
