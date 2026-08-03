# Hermes — Setup Guide

End-to-end installation: Postgres, the Python backend, every external
integration, network exposure to the phone, the iPhone app build, and the
Apple Shortcuts pack. Follow the sections in order; only sections 1–5 and 12
are required for a working chat — everything else unlocks a specific
integration and can be added later without restarting from scratch.

Companion documents: [ARCHITECTURE.md](ARCHITECTURE.md) (system design),
[`assistant/README.md`](../../assistant/README.md) (backend overview),
[`HermesApp/README.md`](../../HermesApp/README.md) (app overview),
[`shortcuts/README.md`](../../shortcuts/README.md) (shortcut recipes).

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Postgres (docker-compose)](#2-postgres-docker-compose)
3. [Python environment](#3-python-environment)
4. [Configuration — `.env` reference](#4-configuration--env-reference)
5. [Server auth token](#5-server-auth-token)
6. [Google Cloud: OAuth + YouTube Data API](#6-google-cloud-oauth--youtube-data-api)
7. [Tavily (web search)](#7-tavily-web-search)
8. [Apple Mail (iCloud)](#8-apple-mail-icloud)
9. [Meta WhatsApp Cloud API](#9-meta-whatsapp-cloud-api)
10. [APNs push (.p8 key)](#10-apns-push-p8-key)
11. [Code sandbox providers](#11-code-sandbox-providers)
12. [Running the server](#12-running-the-server)
13. [Exposing the server to the phone](#13-exposing-the-server-to-the-phone)
14. [Building the iPhone app](#14-building-the-iphone-app)
15. [First-launch app configuration](#15-first-launch-app-configuration)
16. [Shortcut pack](#16-shortcut-pack)
17. [Troubleshooting](#17-troubleshooting)

---

## 1. Prerequisites

| Requirement | Needed for | Notes |
|---|---|---|
| Docker (with Compose) | Postgres + pgvector | Any recent Docker Desktop / engine |
| Python 3.12+ | Backend | `assistant/requirements.txt` targets 3.12+ |
| At least one LLM API key | The agent | Anthropic, OpenAI, Google, or OpenRouter |
| macOS with a recent Xcode | Building the iPhone app | Expo SDK 57 / React Native 0.86 |
| Node.js 20+ and npm | The iPhone app | `HermesApp/` |
| An iPhone | Device control, push, shortcuts | Simulator works for the UI, not for push/shortcuts |
| Apple Developer account (free) | Sideloading the app via Xcode | 7-day provisioning renewal on free accounts |
| Apple Developer Program (paid) | APNs push only | Everything except push works without it |
| Google Cloud account | Gmail, Calendar, YouTube | Free tier is sufficient |
| Meta developer account | WhatsApp | Optional |
| Tailscale (recommended) | Reaching the server away from home | Free personal plan is sufficient |

All backend commands below run from the repository root.

## 2. Postgres (docker-compose)

The backend's only stateful dependency is one Postgres 17 instance with the
pgvector extension. It stores LangGraph checkpoints and store, the `hermes`
application schema (threads, routines, artifacts, receipts, device queue,
memory files, connectors), the full-text session-search index, and — in
local memory mode — the mem0 vector collection.

```bash
docker compose -f assistant/docker-compose.yml up -d
```

This starts the image `pgvector/pgvector:pg17` as container `hermes-db`,
listening on **host port 5433** (container 5432), with user / password /
database all `hermes`, and a named volume `hermes_pgdata` for persistence.
A healthcheck (`pg_isready`) is defined; wait for it before first run:

```bash
docker compose -f assistant/docker-compose.yml ps      # State should be "healthy"
docker exec -it hermes-db psql -U hermes -c "select version();"
```

Port 5433 was chosen to avoid colliding with any local Postgres on 5432.
If 5433 is also taken, change the mapping in
`assistant/docker-compose.yml` **and** `DATABASE_URL` in `assistant/.env`.

You may instead point `DATABASE_URL` at an existing Postgres — it must be
version-compatible and have the **pgvector extension installed** (see
[Troubleshooting](#17-troubleshooting)). All application tables are created
automatically at server startup (`assistant/db.py: init_schema()`), and
LangGraph creates its own tables via `setup_persistence()`. No manual
migrations exist or are needed.

## 3. Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r assistant/requirements.txt
```

What this installs (see `assistant/requirements.txt` for pins):

- **Agent runtime** — `deepagents>=0.7.1`, `langchain>=1.2.13`,
  `langgraph>=1.1`, plus the four provider packages
  (`langchain-anthropic`, `langchain-openai`, `langchain-google-genai`,
  `langchain-ollama`).
- **AG-UI bridge** — `ag-ui-protocol`, `ag-ui-langgraph`, `copilotkit`.
- **Connectors** — `langchain-mcp-adapters` (live MCP tool discovery).
- **Memory** — `mem0ai`.
- **Persistence** — `langgraph-checkpoint-postgres`,
  `psycopg[binary,pool]`, `pgvector`.
- **Server** — `fastapi`, `uvicorn[standard]`, `pydantic-settings`,
  `httpx[http2]` (HTTP/2 is required for APNs), `sse-starlette`.
- **Scheduling & push** — `apscheduler`, `PyJWT[crypto]`.
- **Integrations** — `google-api-python-client`, `google-auth-oauthlib`,
  `beautifulsoup4`.

Sandbox provider packages (`langchain-daytona`, `langchain-e2b`,
`langchain-modal`) are deliberately **not** installed by default — they are
commented out at the bottom of `requirements.txt`; install the one matching
your `SANDBOX_PROVIDER` (section 11).

## 4. Configuration — `.env` reference

```bash
cp assistant/.env.example assistant/.env
```

All settings are loaded by `assistant/config.py` (pydantic-settings) from
the environment or `assistant/.env`. Names are case-insensitive; the
uppercase forms below are conventional. **Minimum to chat:** one LLM key +
`DATABASE_URL` (which already defaults to the docker-compose instance).
Every other variable simply unlocks its integration when set.

### LLM providers

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Anthropic key. Needed for the default model. |
| `OPENAI_API_KEY` | — | OpenAI key. Also required by **local mem0 memory** (default embedder/LLM are OpenAI — see Memory below). |
| `GOOGLE_API_KEY` | — | Google Gemini key (`langchain-google-genai`). |
| `OPENROUTER_API_KEY` | — | OpenRouter key. |
| `ASSISTANT_MODEL` | `anthropic:claude-sonnet-5` | Default main model, `provider:model` form. The app's model chip overrides this per message at runtime. |
| `REVIEW_MODEL` | `anthropic:claude-haiku-4-5-20251001` | Cheap model for the post-turn background memory/skill review. |

Set every provider you want selectable in the app's model sheet — the
Settings-driven `ModelSelectMiddleware` switches among configured providers
at runtime; unconfigured ones will fail when chosen.

### Identity

| Variable | Default | Purpose |
|---|---|---|
| `USER_ID` | `kevyn` | Namespaces mem0 memories and the agent-authored skills store. Changing it later orphans existing memories. |
| `USER_NAME` | `Kevyn` | How the agent addresses you (system prompt). |
| `TIMEZONE` | `Asia/Jerusalem` | IANA zone. Routine cron schedules fire in this zone. |

### Database

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://hermes:hermes@localhost:5433/hermes` | Postgres DSN. The default matches `assistant/docker-compose.yml` exactly. Also parsed to configure mem0's local pgvector store. |

### Memory

| Variable | Default | Purpose |
|---|---|---|
| `MEM0_API_KEY` | — | If set, semantic memory uses the hosted mem0 platform. **If empty, mem0 runs locally against pgvector in your Postgres** — but note mem0's local engine defaults to OpenAI for its embedder and internal LLM, so `OPENAI_API_KEY` must be set in local mode. |
| `MEMORY_CHAR_LIMIT` | `2200` | Character budget of the bounded `MEMORY` file. |
| `USER_PROFILE_CHAR_LIMIT` | `1375` | Character budget of the bounded `USER` profile file. |
| `REVIEW_EVERY_N_TURNS` | `6` | Cadence of the post-turn background review run. |

### Web search

| Variable | Purpose |
|---|---|
| `TAVILY_API_KEY` | Enables the web search tool (section 7). |

### Google

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_CREDENTIALS_PATH` | `assistant/credentials.json` | OAuth client JSON (Desktop **or** Web application — section 6). Path setting, rarely changed. |
| `GOOGLE_TOKEN_PATH` | `assistant/data/google_token.json` | Where the refresh token is cached after OAuth. |
| `YOUTUBE_API_KEY` | — | YouTube Data API v3 key for `search_youtube_videos`. Without it the agent falls back to the on-phone `play_youtube_search` device tool. |

### Apple Mail

| Variable | Purpose |
|---|---|
| `ICLOUD_EMAIL` | Your iCloud address (IMAP/SMTP). |
| `ICLOUD_APP_PASSWORD` | App-specific password (section 8). Apple offers no OAuth for IMAP. |

### WhatsApp (Meta Cloud API)

| Variable | Purpose |
|---|---|
| `WHATSAPP_TOKEN` | Cloud API access token (permanent System User token recommended). |
| `WHATSAPP_PHONE_NUMBER_ID` | The *phone number ID* (numeric), not the phone number itself. |
| `WHATSAPP_VERIFY_TOKEN` | Any secret string you invent; must match the webhook configuration in the Meta dashboard (GET handshake on `/webhooks/whatsapp`). |
| `WHATSAPP_OWNER_PHONE` | Your own number in international format **without `+`** (e.g. `972501234567`). Only this sender is answered by the webhook — all other inbound messages are ignored. |

### Sandbox

| Variable | Default | Purpose |
|---|---|---|
| `SANDBOX_PROVIDER` | `none` | `none` \| `daytona` \| `modal` \| `e2b` (section 11). `none` routes `/workspace/` to plain disk under `WORKSPACE_DIR`. |
| `DAYTONA_API_KEY` | — | For `daytona`. |
| `E2B_API_KEY` | — | For `e2b`. |

### Server

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8787` | Port (informational — the actual bind is the `uvicorn` command line). |
| `API_AUTH_TOKEN` | — | Bearer token required on every request except `/health`, `/webhooks/whatsapp`, and the two Google OAuth paths. **If left empty, auth is disabled** — never expose an unauthenticated server. Section 5. |
| `WORKSPACE_DIR` | `assistant/data/workspace` | Agent scratch files when no sandbox is configured. |

### APNs push

| Variable | Default | Purpose |
|---|---|---|
| `APNS_KEY_PATH` | `assistant/apns_key.p8` | The `.p8` auth key file (section 10). |
| `APNS_KEY_ID` | — | 10-character Key ID of the `.p8`. |
| `APNS_TEAM_ID` | — | Your Apple Developer Team ID. |
| `APNS_BUNDLE_ID` | `com.kevyn.hermes` | Must equal the app's bundle identifier (`HermesApp/app.json`). |
| `APNS_USE_SANDBOX` | `true` | `true` for Xcode/development builds (sandbox APNs environment), `false` for TestFlight/App Store builds. |

## 5. Server auth token

```bash
openssl rand -hex 32
```

Paste the result into `API_AUTH_TOKEN` in `assistant/.env`. You will enter
the **same value** twice more: in the iPhone app's Settings (section 15) and
in Data Jar for the shortcut pack (section 16). The server compares it
constant-time on every non-public request (`bearer_auth` middleware in
`assistant/server/app.py`).

## 6. Google Cloud: OAuth + YouTube Data API

One Google Cloud project covers Gmail, Google Calendar, and YouTube search.

### 6.1 Project and APIs

1. [console.cloud.google.com](https://console.cloud.google.com) → create a
   project (e.g. "Hermes").
2. **APIs & Services → Library** — enable:
   - **Gmail API**
   - **Google Calendar API**
   - **YouTube Data API v3** (for the search key, 6.4)

### 6.2 OAuth consent screen

**APIs & Services → OAuth consent screen** (Google Auth Platform):

1. User type **External**, fill in the app name and your email.
2. Scopes: add `https://www.googleapis.com/auth/gmail.modify` and
   `https://www.googleapis.com/auth/calendar` (these are the exact scopes in
   `assistant/google_auth.py`; both are "sensitive", which is fine in
   testing mode).
3. **Test users: add your own Google account.** The app stays unverified —
   in "Testing" publishing status only listed test users can complete the
   flow; refresh tokens for test users expire after 7 days unless you set
   the publishing status to "In production" (you can do this without
   verification for personal use; you will just see an "unverified app"
   warning screen).

### 6.3 OAuth client — two flows, pick either (or both)

Both flows end the same way: a refresh token cached at
`assistant/data/google_token.json`. `assistant/credentials.json` may hold
either client type.

**Flow A — Desktop client, CLI (simplest; requires a browser on the server
machine).**

1. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   → application type **Desktop app**.
2. Download the JSON and save it as `assistant/credentials.json`.
3. Run the one-off flow:

   ```bash
   python -m assistant.google_auth
   ```

   A browser opens (`InstalledAppFlow.run_local_server` on a random local
   port), you approve, and the token is written:
   `Google credentials saved to assistant/data/google_token.json`.

**Flow B — Web application client, sign in from the phone.**

Used by the app's Settings → "Google (Gmail · Calendar) → Sign in ›"
button, which opens `{server}/auth/google/start` in Safari
(`assistant/server/oauth.py`).

1. Decide the exact base URL your phone uses to reach the server first
   (section 13) — the redirect URI must match it exactly.
2. **Create credentials → OAuth client ID** → application type
   **Web application**.
3. Authorised redirect URI: `{server}/auth/google/callback`, e.g.
   `https://mac.tailnet-name.ts.net:8787/auth/google/callback`. Note Google
   only accepts plain `http://` redirect URIs for `localhost` — a Tailscale
   Serve/Funnel HTTPS URL or tunnel is the practical choice here.
4. Download the JSON and save it as `assistant/credentials.json`
   (replacing the desktop JSON if present — whichever client the file
   contains is used for the web flow).
5. In the app: Settings → Google → **Sign in ›** → approve in Safari →
   "✓ Google connected" page → return to Hermes. The callback stores the
   token server-side at the same `google_token.json` path.

`/auth/google/start` and `/auth/google/callback` are in the server's public
paths (no bearer header can be attached to a Safari tab); everything else
stays behind `API_AUTH_TOKEN`.

### 6.4 YouTube Data API key

1. **Credentials → Create credentials → API key.**
2. Restrict it (recommended): API restrictions → YouTube Data API v3.
3. Set `YOUTUBE_API_KEY` in `assistant/.env`.

This powers `search_youtube_videos` (`assistant/tools/youtube.py`);
playback itself happens on the phone via the `play_youtube_video` device
tool, so the key is search-only (100 units per search against the free
10,000/day quota).

## 7. Tavily (web search)

1. Create an account at [tavily.com](https://tavily.com) — the free tier
   (1,000 credits/month at the time of writing) is ample for personal use.
2. Copy the API key from the dashboard into `TAVILY_API_KEY`.

Without it, the `web_search` tool reports itself unconfigured; `fetch_page`
style retrieval still works.

## 8. Apple Mail (iCloud)

Apple offers no OAuth for IMAP/SMTP — an app-specific password is the only
supported route (surfaced verbatim in `/integrations/status`).

1. [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security →
   **App-Specific Passwords** → generate one (requires two-factor
   authentication on the Apple ID).
2. Set `ICLOUD_EMAIL` and `ICLOUD_APP_PASSWORD`.

Outbound `send_apple_mail` is one of the approval-gated tools — the app
shows an approve / edit / reject sheet before anything is sent.

## 9. Meta WhatsApp Cloud API

Gives the agent `send_whatsapp_message` / `send_whatsapp_template`
(`assistant/tools/whatsapp.py`, Graph API v23.0) and the inbound webhook
that lets you text Hermes from WhatsApp.

### 9.1 App creation

1. [developers.facebook.com](https://developers.facebook.com) → **My Apps →
   Create App** → type **Business**.
2. Add the **WhatsApp** product to the app. This provisions a test
   business phone number and a temporary (24 h) access token in
   **WhatsApp → API Setup**.
3. Note the **Phone number ID** (a long numeric ID displayed under the
   phone number — this, not the number itself, is
   `WHATSAPP_PHONE_NUMBER_ID`).
4. While on the test number, add your personal WhatsApp number to the
   allowed recipient list and verify it with the code Meta sends.

### 9.2 Permanent token

The API Setup token expires daily. For a permanent one:

1. [business.facebook.com](https://business.facebook.com) → Business
   settings → Users → **System users** → create one (Admin role is
   simplest).
2. Assign the app to the system user with full control.
3. **Generate token** for the app with permissions
   `whatsapp_business_messaging` and `whatsapp_business_management`,
   expiry "never".
4. Set it as `WHATSAPP_TOKEN`.

### 9.3 Inbound webhook

The server implements both webhook legs in `assistant/server/app.py`:
`GET /webhooks/whatsapp` answers Meta's verification handshake (echoes
`hub.challenge` when `hub.verify_token` matches `WHATSAPP_VERIFY_TOKEN`),
`POST /webhooks/whatsapp` receives messages.

1. Invent a secret string, set it as `WHATSAPP_VERIFY_TOKEN`.
2. Expose the server over **public HTTPS** (Meta will not call a private
   address) — Tailscale Funnel or a tunnel, section 13.
3. Meta app dashboard → WhatsApp → **Configuration → Webhook**: callback
   URL `https://<public-host>/webhooks/whatsapp`, verify token = the same
   string → Verify and save.
4. Subscribe to the **messages** webhook field.
5. Set `WHATSAPP_OWNER_PHONE` to your own number, international format,
   no `+` (it must equal the `from` field Meta sends, e.g.
   `972501234567`).

Security posture (Hermes trust tiers): inbound messages from any number
other than `WHATSAPP_OWNER_PHONE` are silently dropped; webhook runs use
the minimal read-mostly `webhook` toolset; the reply is sent outside the
agent loop. Note the Cloud API rule: free-form messages can only be sent
within 24 h of the recipient last messaging your business number —
otherwise an approved template (`send_whatsapp_template`) is required.

## 10. APNs push (.p8 key)

Needed for routine-result notifications and the zero-tap device-control
"doorbell" pushes. Requires the **paid** Apple Developer Program; skip this
section otherwise — everything else works, pushes are simply logged and
skipped (`ApnsClient.configured` in `assistant/server/push.py`).

1. [developer.apple.com/account](https://developer.apple.com/account) →
   **Certificates, Identifiers & Profiles → Keys → +**.
2. Name it (e.g. "Hermes APNs"), tick **Apple Push Notifications service
   (APNs)**, register.
3. **Download the `.p8` file — this is your only chance**; Apple never
   offers it again. Save it as `assistant/apns_key.p8`.
4. Record the **Key ID** shown on the key page → `APNS_KEY_ID`.
5. Your **Team ID** is on the Membership details page → `APNS_TEAM_ID`.
6. `APNS_BUNDLE_ID` must exactly match the app's bundle identifier —
   `com.kevyn.hermes` as shipped in `HermesApp/app.json`; change both
   together if you rename it (you will, unless you own that ID).
7. `APNS_USE_SANDBOX`: **`true` while you run the app from Xcode**
   (development builds talk to `api.sandbox.push.apple.com`); switch to
   `false` only for TestFlight/App Store builds.

The backend signs ES256 provider JWTs from the `.p8` (PyJWT) and posts
alerts over HTTP/2 to every device token registered via
`POST /device/register` — the app registers its raw APNs device token when
you tap **Enable ›** under Push notifications in Settings. Proactive
routine pushes are budgeted to 4 per day (`push_log` table); doorbell
pushes are exempt.

## 11. Code sandbox providers

`SANDBOX_PROVIDER` selects where the agent's `/workspace/` files and code
execution live (`_workspace_backend()` in `assistant/agent/agent.py`):

| Value | Backend | Extra setup |
|---|---|---|
| `none` (default) | `FilesystemBackend` on `assistant/data/workspace` (virtual mode) — plain disk, no code execution isolation | none |
| `daytona` | `langchain_daytona.DaytonaSandbox` | `pip install langchain-daytona`, `DAYTONA_API_KEY` from app.daytona.io |
| `e2b` | `langchain_e2b.E2BSandbox` | `pip install langchain-e2b`, `E2B_API_KEY` from e2b.dev |
| `modal` | `langchain_modal.ModalSandbox` | `pip install langchain-modal`, then Modal's own CLI auth (`modal token new`) |

The packages are imported lazily — the server starts fine with
`SANDBOX_PROVIDER=none` and none of them installed. Install exactly the one
you use (they are the commented lines in `assistant/requirements.txt`).

## 12. Running the server

```bash
source .venv/bin/activate
uvicorn assistant.server.app:app --host 0.0.0.0 --port 8787
```

Startup sequence (lifespan in `assistant/server/app.py`): create the
`hermes` schema tables → open the LangGraph pools and run checkpointer/
store `setup()` → build the chat graph and mount the AG-UI endpoint at
`POST /agent` → start the APScheduler routine engine. You should see
`Hermes server ready on :8787`.

Smoke tests:

```bash
curl http://localhost:8787/health
# {"ok":true,"model":"anthropic:claude-sonnet-5"}

curl -H "Authorization: Bearer $API_AUTH_TOKEN" http://localhost:8787/integrations/status
# per-integration connected flags — handy to confirm your .env took effect
```

`/health` is public; `/integrations/status` requires the bearer token, so
it doubles as an auth test. To keep the server running unattended on a Mac,
a `launchd` agent or `tmux` session around the `uvicorn` command is
sufficient; there is no daemon mode of its own.

## 13. Exposing the server to the phone

The app needs plain HTTP(S) reachability to port 8787. Three tiers:

**Same Wi-Fi (quickest test).** Use `http://<machine-LAN-IP>:8787` as the
server URL. Fine on the sofa; breaks the moment you leave the network.

**Tailscale (recommended daily driver).** Install Tailscale on the server
machine and the iPhone, sign both into the same tailnet. The server is then
reachable from anywhere at `http://<machine-name>.<tailnet>.ts.net:8787`
(MagicDNS) with WireGuard encryption and zero open firewall ports. For an
HTTPS URL (needed for the Google *web* OAuth redirect URI), front it with
`tailscale serve 8787`, which gives `https://<machine>.<tailnet>.ts.net`.
For the WhatsApp webhook, which must be on the public internet, use
`tailscale funnel 8787` — or scope the funnel/tunnel to `/webhooks/whatsapp`
only if you prefer to keep the rest tailnet-private.

**Public tunnel (ngrok / cloudflared).** Works for everything including
webhooks, but the whole API is then internet-facing — a strong
`API_AUTH_TOKEN` is mandatory, and note the public paths (`/health`,
`/webhooks/whatsapp`, OAuth) are by design unauthenticated. Prefer
Tailscale for the app traffic and reserve tunnels for the webhook. If chat
streaming stalls behind a proxy, that proxy is buffering SSE — Tailscale's
direct connection does not have this problem.

Whichever URL you choose, use it consistently: it is the app's Server URL
(section 15), the base of the Google web-flow redirect URI (6.3 B), the
WhatsApp callback host (9.3), and the `server_url` in Data Jar (16).

## 14. Building the iPhone app

```bash
cd HermesApp
npm install
npx expo prebuild -p ios      # generates the native ios/ project + pods
npx expo run:ios              # build & launch (add --device for a real phone)
```

Or, after `prebuild`, open `ios/Hermes.xcworkspace` in Xcode, select your
device, and run.

Notes:

- **Bundle identifier.** `app.json` ships `com.kevyn.hermes`. Unless you
  own that App ID, change `expo.ios.bundleIdentifier` to your own reverse-
  DNS ID *before* prebuild, and set `APNS_BUNDLE_ID` in `assistant/.env`
  to the same value.
- **Signing.** In Xcode → target Hermes → Signing & Capabilities, pick
  your team. A free account can sideload (rebuild every 7 days); the Push
  Notifications capability the `expo-notifications` plugin adds during
  prebuild requires a paid team to produce a valid `aps-environment`
  entitlement — without one, build and run with push disabled.
- **Physical device required** for push notifications, the Shortcuts pack,
  and deep-link device control; the simulator is only useful for the chat
  UI.
- **Permissions** are declared in `app.json` (calendar, reminders,
  notification background mode, and the `LSApplicationQueriesSchemes` used
  by device control: `shortcuts`, `youtube`, `spotify`, `whatsapp`,
  `comgooglemaps`); iOS prompts on first use.
- `npm run typecheck` runs the strict TypeScript check if you modify the
  app.

## 15. First-launch app configuration

Open Hermes on the phone, then the avatar → **Settings**
(`HermesApp/app/settings.tsx`):

1. **SERVER** — enter the Server URL from section 13 (e.g.
   `http://mac.tailnet.ts.net:8787`; trailing slash is stripped) and the
   `API_AUTH_TOKEN` value, then tap **Save & test**. You should see
   `Connected ✓ (<model>)` — this calls `GET /health`.
2. **INTELLIGENCE** — pick provider/model from the model sheet (any
   provider whose key is in `.env`); toggle long-term memory as desired.
   The model chip in the composer changes it per message.
3. **CONNECTED ACCOUNTS** — status dots come from
   `GET /integrations/status`. Tap **Sign in ›** next to Google to run the
   web OAuth flow (6.3 B). Apple Mail, WhatsApp, web search, and YouTube
   turn green purely from `.env` configuration.
4. **PHONE** — tap **Enable ›** under Push notifications to request
   permission and register the APNs device token with the backend
   (`POST /device/register`). Expect `Registered ✓`.
5. The **Shortcut pack** list below it comes from
   `GET /shortcuts/manifest`; entries show *build manually* until you have
   built and shared each shortcut (next section).

Connectors (menu → Connectors) need no setup here: catalog apps, MCP URLs,
and OpenAPI specs attach tools live on the next message.

## 16. Shortcut pack

Follow [`shortcuts/README.md`](../../shortcuts/README.md) — it contains the
full step-by-step recipe for every shortcut. Summary of the one-time setup:

1. Install **Data Jar** (free) on the iPhone.
2. Build **AI: Setup** in the Shortcuts app and run it once — it stores
   `server_url` and `api_token` in Data Jar and makes one test request so
   iOS shows its "Allow to connect" prompt exactly once.
3. Build the remaining shortcuts from the recipes: **AI: Poll** (the
   zero-tap workhorse that drains `GET /device/next-command` and reports
   via `POST /device/results`), AI: Send iMessage, AI: Send Email, AI: Set
   Focus, AI: Timer, AI: Home Scene, AI: Navigate, AI: Prefill WhatsApp.
4. Create the zero-tap automation: Shortcuts → Automation → New →
   **Notification** → app = Hermes → **Run Immediately ON, Notify When Run
   OFF** → Run Shortcut → `AI: Poll`. From then on a backend doorbell push
   silently triggers command execution with the phone in your pocket.

Optionally share each shortcut as an iCloud link and paste the URLs into
the `/shortcuts/manifest` handler (`assistant/server/app.py`) so the app's
Settings screen offers one-tap **Install ›** buttons; the pack works
identically without this.

## 17. Troubleshooting

**`type "vector" does not exist` / mem0 fails to create its collection.**
You are pointing at a Postgres without the pgvector extension — typically a
plain `postgres` image or a pre-existing local install. Use the shipped
`pgvector/pgvector:pg17` compose service, or install pgvector on your
instance and run `CREATE EXTENSION vector;` as a superuser in the `hermes`
database. (In the compose container the `hermes` user is superuser, so
mem0's own `CREATE EXTENSION IF NOT EXISTS` succeeds automatically.)

**Local memory errors mentioning OpenAI / embeddings.** With
`MEM0_API_KEY` empty, mem0 runs locally and defaults to OpenAI for both
embedding and its internal extraction LLM — set `OPENAI_API_KEY`, or use
the hosted platform by setting `MEM0_API_KEY`.

**`connection refused` on port 5433.** Container not running or unhealthy:
`docker compose -f assistant/docker-compose.yml ps`, then `... logs db`.
If another service owns 5433, change the port mapping and `DATABASE_URL`
together.

**HTTP 401 `{"detail":"unauthorized"}` from every endpoint.** The bearer
token does not match `API_AUTH_TOKEN`: check for trailing whitespace or a
missing `Bearer ` prefix; re-enter the token in app Settings and in Data
Jar (`api_token`) after any change; remember auth is enforced only when
`API_AUTH_TOKEN` is non-empty, so a 401 always means a mismatch, not a
missing feature. `/health` never 401s — use it to separate networking
problems from auth problems.

**Google `redirect_uri_mismatch`.** The web client's authorised redirect
URI must equal `{server}/auth/google/callback` for the exact URL the phone
opened — scheme, host, and port included. Behind Tailscale Serve the port
is 443 and must be omitted.

**Google `access_denied` or "app not verified".** Your account is not in
the consent screen's test users (Testing mode only admits listed testers),
or you stopped at the warning interstitial — "Advanced → continue" is
expected for an unverified personal app.

**Google works, then breaks after a week.** Consent screen left in
"Testing" — refresh tokens for test users expire after 7 days. Set the
publishing status to "In production" and re-run the sign-in once.

**`assistant/credentials.json missing`.** Raised by both the CLI flow and
`/auth/google/start`. Download the OAuth client JSON (either type) to that
exact path — see `GOOGLE_CREDENTIALS_PATH`.

**WhatsApp webhook "verification failed".** Meta's GET handshake reached
the server but `hub.verify_token` differed from `WHATSAPP_VERIFY_TOKEN`
(HTTP 403 from `whatsapp_verify`). If the dashboard says the URL is
unreachable instead, the server is not publicly accessible — a
tailnet-only address will not do; use Funnel or a tunnel.

**WhatsApp messages arrive but Hermes never replies.** The sender did not
match `WHATSAPP_OWNER_PHONE` — compare the `from` value in the webhook
payload (international format, no `+`) character for character.

**WhatsApp send returns error 131047 / message silently undelivered.**
Outside the 24 h customer-service window; send yourself a message first or
use `send_whatsapp_template`.

**APNs `400 BadDeviceToken`.** Environment mismatch — the token in
`hermes.device_tokens` came from the other APNs environment. Xcode
development builds must run with `APNS_USE_SANDBOX=true`;
TestFlight/App Store builds with `false`. After switching build types,
delete stale tokens (`DELETE FROM hermes.device_tokens;`) and re-register
from app Settings.

**APNs `403 InvalidProviderToken`.** `APNS_KEY_ID` / `APNS_TEAM_ID` do not
match the `.p8`, or the file at `APNS_KEY_PATH` is not the downloaded key.

**APNs `400 TopicDisallowed`.** `APNS_BUNDLE_ID` differs from the bundle
identifier the app was actually built with.

**Pushes "skipped" in server logs.** `APNs not configured — skipping push`
means one of key path / key ID / team ID is unset — intentional when you
have no paid developer account. Also note the daily budget: at most 4
proactive routine pushes per 24 h; overflow lands only in the ledger.

**App shows `Failed: Network request failed` on Save & test.** The phone
cannot reach the URL: verify it in Safari on the phone first; check
Tailscale is connected on both ends; confirm you used the machine's
address, not `localhost`.

**Chat streaming stalls or arrives in one burst.** An intermediate proxy
is buffering the SSE stream from `POST /agent` — bypass it (Tailscale
direct) or disable response buffering on the tunnel.

**`expo prebuild` / pod install failures.** Ensure a current Xcode with
command-line tools selected (`xcode-select -p`) and re-run
`npx expo prebuild -p ios --clean`; the `ios/` directory is generated and
safe to delete.

**Routine cron rejected (HTTP 422 "Invalid cron").** Schedules are
standard 5-field crontab strings validated by APScheduler's
`CronTrigger.from_crontab` and evaluated in `TIMEZONE` — e.g.
`30 7 * * 1-5` for weekday mornings.
