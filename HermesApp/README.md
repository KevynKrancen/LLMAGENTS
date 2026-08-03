# Hermes — iPhone App

A minimalist, classy personal-assistant app in the spirit of the Claude
iPhone app: **one serene chat screen is the whole front page** — history,
artifacts, routines, settings, model choice, and phone control all live
behind it (drawer, sheets, and the composer's ＋ button).

Built with Expo SDK 57 / React Native 0.86, TypeScript strict, expo-router.
Talks to the backend in [`../assistant`](../assistant/README.md) over the
AG-UI protocol (hand-rolled typed SSE client on `expo/fetch`).

## What's inside

- **Chat home** — streaming markdown, collapsible thinking, tool-activity
  chips, generative-UI cards (plan, media, event, email draft, chart)
  rendered when the agent calls `show_*` frontend tools, native approval
  sheets for outbound actions (approve / reject), thread drawer with search.
- **Composer** — ＋ capability grid (hidden depth), model chip (switch
  provider/model per message: Anthropic · OpenAI · Google · OpenRouter ·
  Ollama), morphing send/stop button, haptics.
- **Artifacts** — live canvas: HTML artifacts render in a WebView and
  update in place as the agent streams STATE_DELTA patches; markdown,
  tables, and charts render natively.
- **Routines** — create/pause/delete scheduled runs with cron presets.
- **Connectors** — the app platform: one-tap catalog apps (Weather,
  Telegram, GitHub, Spotify, Notion), or add your own — any MCP server URL
  or any REST API via its OpenAPI spec — and the tools attach to Hermes
  automatically, live on the next message.
- **Settings** — server URL + token, Google OAuth sign-in (opens the
  backend's `/auth/google/start`), integration status dots, push
  registration, shortcut-pack installer.
- **Device control** — executes agent device commands: YouTube playback,
  deep links, Apple Shortcuts via x-callback (results return to the agent),
  EventKit reminders; drains the backend device queue on push doorbells.

## Run it

```bash
cd HermesApp
npm install
npx expo prebuild -p ios     # generates the ios/ project
npx expo run:ios             # or open ios/Hermes.xcworkspace in Xcode
```

On first launch open **Settings** (avatar → Settings):

1. Server URL — e.g. `http://<your-mac>:8787` (same Wi-Fi) or your
   Tailscale/tunnel URL.
2. API token — the `API_AUTH_TOKEN` from `assistant/.env`.
3. Tap **Save & test**, then sign in to Google and enable push.

Push notifications require a paid Apple Developer account (APNs key
configured on the backend). Everything else works without it.

## Architecture notes

- `src/agui/` — typed AG-UI client: SSE parser, event vocabulary,
  RFC 6902 patch application for shared state.
- `src/state/chat.ts` — the event reducer: streams text/reasoning, renders
  tool cards, coordinates device-tool execution through the backend queue
  (single execution path — commands never run twice), auto-runs the
  follow-up turn that returns frontend tool results, and surfaces
  `interrupt_on` approvals (resumed via `forwardedProps.command.resume`).
- `src/device/` — frontend tool schemas + the on-phone executor.
- Design tokens in `src/theme/tokens.ts` — warm off-whites / near-blacks,
  bronze accent, hairlines, 4pt grid, New York titles.
