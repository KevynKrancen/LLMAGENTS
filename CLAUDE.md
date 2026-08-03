# CLAUDE.md — guidance for AI agents working on this repository

This repo contains two things:
1. **Hermes** — a personal AI assistant (the active project): `assistant/`
   (Python backend), `HermesApp/` (Expo iPhone app), `shortcuts/` (Apple
   Shortcuts pack), `docs/assistant/` (documentation).
2. A legacy MCP multi-agent demo at the repo root (`agent.py`, `web_ui.py`,
   `mail_agent/`, `video_gen/`, …). **Do not modify the legacy code** when
   working on Hermes.

## Golden rules

- **Stack versions matter.** deepagents 0.7.x / langchain 1.3+ / langgraph
  1.2+ have breaking API differences from older docs. Verified working
  patterns are IN THIS CODEBASE — copy them, don't trust memory:
  - Middleware base class: `langchain.agents.middleware.AgentMiddleware`;
    async hooks are `awrap_model_call`, `awrap_tool_call`, `aafter_agent`.
    Mutate requests via `request.override(...)`, never in place.
  - `ToolCallRequest` fields: `tool_call` (dict with name/args), `tool`,
    `state`, `runtime`. Thread id: `runtime.execution_info.thread_id`.
  - deepagents backends are INSTANCES (`CompositeBackend(default=StateBackend(),
    routes={...})`) — factories were removed in 0.7.
  - `AsyncPostgresSaver`/`AsyncPostgresStore` must be constructed inside a
    running event loop → graphs are built in the FastAPI lifespan, never at
    import time (see `assistant/server/app.py`).
  - `@tool(parse_docstring=True)` only — `handle_tool_error` does not exist
    in langchain-core 1.5.
- **Prompt-cache discipline** (Hermes-Agent principle, enforced here):
  dynamic context (mem0 recall, per-turn data) is injected into USER
  messages; the bounded memory snapshot is frozen per thread. Never inject
  per-turn content into the system prompt.
- **Trust tiers**: three graph modes — `chat` (everything), `routine`
  (no routine management: recursion guard), `webhook` (minimal read-only
  set; replies sent OUTSIDE the agent loop). Never give the webhook tier
  outbound or device tools.
- **Receipts**: consequential tools must stay registered in
  `assistant/agent/receipts.py::_CONSEQUENTIAL` (with undo descriptors
  where reversible). If you add an outward-acting tool, add it there AND
  consider `interrupt_on` in `assistant/agent/agent.py`.
- **UI philosophy**: conversation *does*, UI *keeps*. No tool buttons in
  the app; no preset structure; SF Symbols only (never emoji); answers are
  generated components (`render_component`), depth lives in artifacts and
  folder dashboards. Read `docs/assistant/UX-DESIGN.md` before UI work.

## Verifying changes

```bash
# Backend: local Postgres 16 (no docker in CI containers):
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /tmp/pg -U hermes --auth=trust"
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pg -o '-p 5433 -k /tmp' start"
createdb -h localhost -p 5433 -U hermes hermes
pip install -r assistant/requirements.txt
python -c "from assistant.agent.agent import build_assistant_graph; build_assistant_graph('chat')"
ANTHROPIC_API_KEY=test API_AUTH_TOKEN=t uvicorn assistant.server.app:app --port 8789
curl -s localhost:8789/health
# AG-UI smoke: POST /agent with FULL RunAgentInput (state/tools/context/
# forwardedProps are all REQUIRED fields — 422 otherwise).

# App:
cd HermesApp && npx tsc --noEmit   # must stay clean; strict mode
```

`assistant/data/`, `.env`, `credentials.json`, `apns_key.p8` are
gitignored — never commit secrets or local state.

## Conventions

- Tools: `@tool(parse_docstring=True)`, action-verb names
  (`verb_domain_specifics`), docstring Args/Returns sections, JSON string
  returns, errors as readable strings (the ToolNode converts exceptions).
- Python: type hints everywhere, module docstrings explaining *why*,
  helpers prefixed `_`, no dead code. TypeScript: strict, no `any`,
  zustand for state, design tokens from `src/theme/tokens.ts` only —
  no hard-coded colors.
- Commits: imperative subject + wrapped body; push to the feature branch
  (never main without being asked).

## Key documentation

`docs/assistant/`: ARCHITECTURE, IMPLEMENTATION, API, SETUP,
SKILLS-AND-MEMORY, UX-DESIGN, ROADMAP. The ROADMAP lists what to build
next and known assumptions to verify on first live run.
