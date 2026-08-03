---
name: component-design
description: How to design bespoke render_component UI for answers — weather cards, inbox digests, schedules, stats. Use whenever presenting data-rich information in chat.
---

# Component Design — answers as living UI

For any data-rich answer (weather, emails, calendar, lists, comparisons,
numbers), do BOTH: one short conversational sentence in text, and a
`render_component` call that presents the data as a designed component.
Fetch real data first (tools), then render it — never invent data.

## The design system
Self-contained HTML+CSS. Use the injected CSS variables so it matches the
app in light AND dark: `var(--bg) --surface --surface-alt --text --subtle
--accent --hairline --danger --success`. System font is inherited.

- Calm and high-end: generous padding (14-18px), 12-14px radii, hairline
  borders (`1px solid var(--hairline)`), no drop shadows, no gradients
  unless they carry meaning (e.g. sky in a weather card).
- Hierarchy: one big number or fact (26-34px, weight 600), quiet labels
  (11-12px, `var(--subtle)`, letter-spacing).
- Color only where it means something: accent for the key figure,
  success/danger for deltas.
- Emoji/unicode glyphs beat icon fonts (☀ ☁ ⛅ ✉ ▲ ▼ ●).
- No external images, fonts, or network calls. No JavaScript needed —
  the host renders and sizes it automatically.

## Patterns
- **Weather**: big temp + condition glyph, row of day chips (day/glyph/
  hi-lo), subtle sky-tinted header.
- **Inbox digest**: sender in 600 weight, subject normal, one-line
  preview in --subtle, unread dot in --accent, hairline separators.
- **Schedule**: time column in --subtle, event blocks with a 2px accent
  left border.
- **Stats/comparison**: grid of stat tiles (label / big value / delta).

Keep components under ~1600 chars of HTML when possible; they should feel
like a native widget, not a webpage.
