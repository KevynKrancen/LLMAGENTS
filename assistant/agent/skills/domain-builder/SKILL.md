---
name: domain-builder
description: Build a full domain when the user asks for a new capability — trading, budgeting, tutoring, anything. Folder + skill + connectors + routines + dashboard, optionally a dedicated agent.
---

# Domain Builder — self-specialization recipe

A domain turns "help me with X" into permanent infrastructure: a workspace
folder, a domain skill, connectors, routines, a live dashboard, and (for
heavy domains) a dedicated agent. Build the whole thing in one go, then show it.

## When to Use
The user asks for a new ongoing *capability*, not a one-off answer:
"help me invest on Polymarket", "be my budget coach", "teach me linear
algebra". One-off questions never trigger this. Before building, read
`references/walkthroughs.md` — it has three complete builds with the exact
tool calls in order; copy the closest one.

## Procedure
Confirm scope with at most ONE short question (budget cap, goal, deadline),
then build in this order — later steps embed ids produced by earlier ones.

1. **Recon** — `view_workspace()` and `list_connected_apps()`. Reuse an
   existing folder/connector rather than duplicating.
2. **Folder** — `shape_workspace(operations='[{"op":"create","path":"Finance/Polymarket","icon":"chart.line.uptrend.xyaxis"}]')`.
   Icons are SF Symbol names (`banknote`, `graduationcap`, `book`,
   `chart.line.uptrend.xyaxis`, …), never emoji. Everything the domain
   produces files under this path via `save_note(..., path=)` /
   `create_artifact(..., path=)`.
3. **Domain skill** — `write_file("/skills/<domain>/SKILL.md", ...)`
   (frontmatter description ≤60 chars or the index truncates it). This is
   what makes the expertise permanent — it reloads every session. Also put
   the domain's machine-readable state next to it: `/skills/<domain>/` is
   the ONLY place you can both write and read back later (`read_file`), so
   canonical data (ledger, progress, position list) lives there as extra
   .md files; workspace notes/artifacts are the user-facing copies.
4. **Connectors** — if the domain needs live data/actions:
   `install_mcp_connector(name, url)` or
   `install_api_connector(name, spec_url, auth_header="")`. Both are
   approval-gated interrupts; tools attach on the next message, so don't
   call them in the same turn you need them. `search_web(query, topic=
   'general'|'news'|'finance')` is always the fallback.
5. **Dashboard (before routines)** —
   `create_artifact(kind='html', title=..., content=..., path=<folder>, as_dashboard=True)`.
   Returns `artifact_id` — record it in the domain skill; routines need it
   for `update_artifact`. Build the HTML from
   `references/dashboard-templates.md` (self-contained, own CSS variables,
   light+dark). The folder screen shows only the top ~300px as a preview —
   headline numbers go first.
6. **Routines** — `create_routine(name, cron, prompt)`. Cron is 5-field in
   the user's local timezone. Routine runs are HEADLESS: no conversation
   context, no routine-management tools, and the final reply becomes an
   iPhone push notification. So every prompt must be self-contained —
   name exact file paths and the real dashboard `artifact_id`, and end
   with a push-sized summary line.
7. **Dedicated agent (heavy domains only)** —
   `spawn_agent(name, description, system_prompt, tools)` persists a
   routable specialist subagent (see walkthroughs for a full example with
   trading approval rules baked into its system_prompt). Skip for light
   domains — the domain skill alone is enough.
8. **Memory** — one dense line via
   `manage_memory_file(file='MEMORY', action='add', text=...)`: domain
   name, folder path, dashboard id, the user's goal. Operational detail
   stays in the domain skill, not memory.

## Pitfalls
- **There is no artifact-read tool.** You cannot fetch a note's or
  dashboard's current content later. Keep the source-of-truth data in
  `/skills/<domain>/*.md` (readable via `read_file`) and regenerate the
  full dashboard HTML from it on every `update_artifact` — updates are
  full replacement, never a diff.
- **Dashboards are display-only.** `hermes://open` / `hermes://say` action
  links work in chat `render_component` cards, NOT in folder dashboards.
- **Money/trading**: NEVER place a trade, order, or transfer without an
  explicit per-action user approval in chat; append every action (incl.
  refusals) to the domain ledger file. Bake the same rule into any
  spawned trading agent's system_prompt.
- Routine prompts that say "the dashboard" or "the ledger" without ids/
  paths will fail headless. Embed literals.
- Don't create near-duplicate domains; extend the existing skill/folder.
- Connector installs may be rejected — the domain must still work
  (degrade to `search_web` + `fetch_web_page`).

## Verification
After building, check all of it:
1. `view_workspace()` — folder (and subfolders) exist at the right path.
2. `ls("/skills/<domain>/")` — SKILL.md + state files present; re-read
   SKILL.md once to confirm it names real ids and paths.
3. `list_routines()` — routine enabled, cron correct.
4. Dashboard: tell the user to open the folder; the artifact renders as
   its face (the `create_artifact` result showed `dashboard_for` set).
5. Say what was built in 3-4 lines and ask nothing further.

On later requests inside a domain: its skill loads automatically — follow
it, file everything under its folder, and keep its dashboard current.
