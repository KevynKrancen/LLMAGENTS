---
name: domain-builder
description: Build a specialized domain when the user wants a new capability — finance/trading agent, budget coach, academic tutor, anything. Creates the folder, skill, connectors, routines, and a custom dashboard UI.
---

# Domain Builder — self-specialization recipe

When the user asks for a new *capability* ("help me invest on Polymarket",
"be my budget coach", "teach me linear algebra"), don't just answer — BUILD
THE DOMAIN. A domain is five things, created in this order:

## 1. Folder — where it lives
`shape_workspace` a home, e.g. `Finance/Polymarket` or `Academy/Linear
Algebra`. Everything the domain produces files under it (save_note,
create_artifact with path=).

## 2. Skill — how you stay expert (CRITICAL)
Write `/skills/<domain>/SKILL.md` with the file tools: what the domain is
for, the user's goals/constraints, your procedure, APIs involved, pitfalls.
This makes the expertise PERMANENT — next session you reload it
automatically. Update it as you learn the user's preferences.

## 3. Connectors — the domain's hands
If the domain needs live data or actions, connect the right API:
`install_mcp_connector` / `install_api_connector` (e.g. a markets API,
a flashcards API). Both require user approval. Check
`list_connected_apps` first. If no API fits, web search is your fallback.

## 4. Routines — the domain's heartbeat
Recurring behavior becomes a routine: "ask me my expenses every evening" →
`create_routine(cron='0 21 * * *', prompt='Ask Kevyn what he spent today;
append answers to the Budget ledger note and refresh the Budget
dashboard.')`. Routine prompts must be self-contained.

## 5. Dashboard — the domain's face
`create_artifact(kind='html', path=<folder>, as_dashboard=true)` builds the
folder's custom UI — it renders whenever the user opens the folder. Design
it for the domain: a budget ledger with running totals, a positions table
with P&L, a lesson tracker with progress. Self-contained HTML/CSS/JS, calm
styling matching the app (off-whites/near-blacks, one accent). UPDATE it
(update_artifact) whenever the domain's data changes — it is living UI,
not a report.

## Rules
- Confirm scope with one short question at most, then build the whole
  domain in one go and show it.
- Money/trading domains: NEVER place a trade or move funds without an
  explicit per-action approval; record every action in the domain ledger.
- Store durable user goals in memory (manage_memory_file), operational
  detail in the domain skill.
- On later requests inside a domain, load its skill, use its folder, and
  keep its dashboard current.
