---
name: component-design
description: Design system for render_component — bespoke HTML cards (weather, inbox, schedule, stats) with live hermes:// actions, theme-matched. Use whenever presenting data-rich answers in chat.
---

# Component Design — answers as living UI

## When to Use
- Any data-rich answer: weather, email digests, schedules, stats, comparisons,
  trackers, lists, media results. Do BOTH: one short conversational sentence
  in text AND one `render_component` call. A real assistant shows, not tells.
- Prefer a bespoke `render_component` over the generic `show_*` cards
  (`show_plan_card`, `show_chart`, `show_event_card`, `show_email_draft`,
  `show_media_card`) whenever layout, hierarchy, or actions matter; the
  generic cards are only for quick confirmations.
- Never render invented data. Fetch with tools first, then render.

## The contract (host: HermesApp/src/components/HtmlComponentCard.tsx)
- Tool: `render_component(html, title?)`. `html` = body markup only (no
  `<html>`/`<head>`; a `<style>` block inside is fine — each component is its
  own document, class names cannot collide). `title` = short accessibility title.
- Injected CSS vars, auto light/dark: `--bg --surface --surface-alt --text
  --subtle --accent --hairline --danger --success`. Nothing else is injected.
- Injected base: system font 14px/1.5, `color:var(--text)`, transparent body
  with 2px padding, universal margin/padding reset, `box-sizing:border-box`.
- The host already wraps your HTML in a card with surface background, hairline
  border, and 14px radius. Do NOT re-frame — add inner padding (14–16px) and
  use `var(--surface-alt)` for inner tiles.
- The WebView auto-sizes; height caps at 560px then inner-scrolls. Stay under
  ~550px tall (roughly 6–7 list rows plus a chip row).
- Long-press shows built-in reshape chips (Simpler / More detail / As a chart)
  — never build your own reshape controls.

## Procedure
1. Fetch real data with tools.
2. Copy the closest template — read `references/patterns.md` when building any
   card (weather, inbox digest, schedule, stat tiles, comparison,
   progress/tracker, list-with-actions, media, hero answer) and adapt it.
3. Make it alive: every component carries at least one real affordance. Read
   `references/actions.md` when wiring `hermes://open` deep links or
   `hermes://say` chips — it has the exact encoding rules, the iOS deep-link
   catalog, and 10 worked examples.
4. Send one `render_component` call plus one line of chat text.

## Design rules
- Calm and high-end: 14–16px padding, 10–12px inner radii, hairline borders
  (`1px solid var(--hairline)`), no shadows; gradients only when they carry
  meaning (a weather card's sky).
- Hierarchy: one hero fact at 26–34px weight 600. Labels at 11px, uppercase,
  `letter-spacing:.06em`, `var(--subtle)`.
- Color only where it means something: `--accent` for the key figure and
  affordances, `--success`/`--danger` for deltas and states. Tint with
  `var(--surface-alt)` or `color-mix(in srgb, var(--accent) 12%, transparent)`.
- Glyphs over icon fonts: ☀ ⛅ ☂ ✉ ▲ ▼ ● ○ ✓ ▶ ↗. No external images, fonts,
  or network calls. No JavaScript — actions are pure `hermes://` links.
- `font-variant-numeric:tabular-nums` on any column of numbers.
- Target ≤1600 chars of HTML. It should feel like a native widget, not a webpage.

## Pitfalls
- Plain `<a href="https://…">` is BLOCKED by the host (only `hermes://` URLs
  are handled; everything else is swallowed). Every link must be
  `hermes://open?url=<encoded>` or `hermes://say?text=<encoded>`.
- Anchors render blue and underlined by default — every `<a>` needs explicit
  `color` and `text-decoration:none`.
- The host parses actions with `new URL(url).searchParams`, so an unencoded
  `&` or `#` in the payload truncates it. Always `encodeURIComponent` the
  whole target; pre-encoded targets need double encoding (`%20` → `%2520`) —
  see references/actions.md.
- `hermes://open` fires exactly one URL with no fallback chain and fails
  silently. Prefer universal https links (`https://www.youtube.com/watch?v=…`)
  over bare schemes unless the app is certainly installed.
- Never nest an `<a>` inside an `<a>` (tappable row containing chips) — put
  chips in a sibling row instead.
- Adding an outer border/background/radius duplicates the host frame.
- Hex colors hard-code one theme and break the other — use the vars.

## Verification
Before sending, check:
- Every `var(--…)` is one of the nine injected names, spelled exactly.
- Every href starts with `hermes://open?url=` or `hermes://say?text=` and the
  value is fully URL-encoded; no raw `&`, `#`, or spaces inside it.
- Mentally render at 300px wide: nothing overflows horizontally, total height
  ≲550px, text truncates with ellipsis rather than wrapping into noise.
- Exactly one component + one short sentence; every number in it traces back
  to a tool result from this turn.
