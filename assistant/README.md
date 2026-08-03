# Hermes — Personal AI Assistant Backend

A Hermes-Agent-inspired personal assistant built on the Aug-2026 stack:
**DeepAgents 0.7** (deep agent runtime) · **AG-UI protocol** (app streaming)
· **mem0 + bounded memory files** (three-layer memory) · **Postgres +
pgvector** (checkpoints, store, search, vectors) · **FastAPI**. The iPhone
app lives in [`../HermesApp`](../HermesApp); the Shortcuts pack in
[`../shortcuts`](../shortcuts).

## Architecture

```
iPhone app (Expo / AG-UI SSE)          Apple Shortcuts (AI: Poll, …)
        │  POST /agent                        │ GET /device/next-command
        ▼                                     ▼
FastAPI server ── REST: threads · artifacts · routines · device · webhook
        │
Deep agent (deepagents 0.7, per-mode trust tiers: chat / routine / webhook)
  ├─ middleware: CopilotKit AG-UI bridge → model select (Settings-driven)
  │              → frozen memory snapshot → mem0 recall (user-msg injection,
  │              cache-safe) → session log + background review
  ├─ tools: web search/fetch · gmail · google calendar · apple mail ·
  │         whatsapp cloud · youtube · memory (bounded files + mem0) ·
  │         session_search · artifacts (live, STATE_DELTA) · routines ·
  │         device control (queue + APNs doorbell) 
  ├─ subagents: researcher · analyst      ├─ skills: bundled + self-authored
  └─ persistence: Postgres checkpointer + store; sandbox backend optional
```

Memory (Hermes pattern): bounded `MEMORY`/`USER` files frozen into context
each session + mem0 semantic recall injected into user messages + zero-LLM
full-text search over all past sessions. A post-turn background review
(cheap model, memory tools only) decides what to persist every few turns.

## Setup

```bash
# 1. Database
docker compose -f assistant/docker-compose.yml up -d

# 2. Python env (from repo root)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r assistant/requirements.txt

# 3. Configure
cp assistant/.env.example assistant/.env   # fill in keys
# Google (Gmail+Calendar): put OAuth Desktop client JSON at
# assistant/credentials.json, then:
python -m assistant.google_auth

# 4. Run
uvicorn assistant.server.app:app --host 0.0.0.0 --port 8787
```

Expose the port to your phone (same Wi-Fi, or Tailscale — recommended — or
an https tunnel). Set the server URL + `API_AUTH_TOKEN` in the app Settings.

## Integrations checklist

| Integration | What to configure |
|---|---|
| Anthropic/OpenAI/Google/OpenRouter | API key in `.env`; pick model in the app Settings |
| Web search | `TAVILY_API_KEY` |
| Gmail + Google Calendar | `credentials.json` + `python -m assistant.google_auth` |
| Apple Mail | `ICLOUD_EMAIL` + app-specific password |
| WhatsApp | Meta app (Cloud API): token, phone number id, webhook → `/webhooks/whatsapp` with your verify token; `WHATSAPP_OWNER_PHONE` locks inbound to you |
| YouTube search | `YOUTUBE_API_KEY` (Data API v3) |
| Push (routines, zero-tap device control) | APNs `.p8` key at `assistant/apns_key.p8` + key/team ids |
| Code sandbox | `SANDBOX_PROVIDER=daytona|e2b|modal` + key (+ its pip package) |
| iPhone Shortcuts | Build the pack: [`../shortcuts/README.md`](../shortcuts/README.md) |

## Connectors — the app platform

Install apps from the phone (menu → Connectors) and their tools attach to
the agent automatically, effective on the next message — no restart:

- **MCP servers** — paste any MCP URL (e.g. `https://mcp.notion.com/mcp`);
  tools are discovered live via `langchain-mcp-adapters`.
- **Any REST API** — paste an OpenAPI spec URL (+ optional auth header);
  every documented endpoint becomes a typed tool.
- **Catalog** — one-tap apps: Weather (keyless), Telegram, GitHub, Spotify,
  Notion.
- **In chat** — the agent can install connectors itself
  (`install_mcp_connector` / `install_api_connector`), always gated behind
  an approval sheet.

Endpoints: `GET/POST /apps`, `PATCH/DELETE /apps/{id}`.

## Security model

- Single-user; every request needs the bearer `API_AUTH_TOKEN`.
- Outbound actions (email, WhatsApp, deletes) require in-app approval
  (`interrupt_on`) — approve / edit / reject sheets.
- Trust tiers (Hermes pattern): routine runs can't manage routines
  (recursion guard); WhatsApp-webhook runs get a minimal read-mostly
  toolset and replies are sent outside the agent loop.
- Memory and prompt-cache discipline: dynamic recall is injected into user
  messages, never the cached system prefix.
