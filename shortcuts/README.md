# Hermes Assistant Shortcut Pack (iOS 26)

These shortcuts let the agent act **inside** other iPhone apps. Build each
one once in the Shortcuts app (recipes below), then share it as an iCloud
link and paste the links into `/shortcuts/manifest` (or keep them local —
the app can trigger any of them by name regardless).

Two ways they get triggered:

1. **In-app** (you're in the Hermes app): the app opens
   `shortcuts://x-callback-url/run-shortcut?name=…&input=text&text=…&x-success=hermes://shortcut-result`
   and receives the result back automatically.
2. **Zero-tap** (phone in your pocket): the backend sends a push → an iOS 26
   automation "When I get a notification from Hermes" (**Run Immediately**,
   Notify When Run OFF) runs `AI: Poll`, which fetches pending commands from
   the backend, executes them, and reports back. One-time setup, then fully
   silent.

## One-time setup

1. Install the **Data Jar** app (free) — stores `server_url`, `api_token`.
2. Build `AI: Setup` and run it once (it asks for your server URL + token,
   saves them to Data Jar, and performs one test request so iOS shows the
   "Allow to connect" prompt exactly once).
3. Build the other shortcuts below.
4. Automation: Shortcuts → Automation → New → **Notification** → app =
   Hermes → Run Immediately ON, Notify When Run OFF → action: Run Shortcut
   → `AI: Poll`.

## Recipes

Every shortcut ends with the same **report block**:
`Get Contents of URL` → POST `{server_url}/device/results`, headers
`Authorization: Bearer {api_token}`, JSON body
`{"command_id": <id>, "status": "success", "output": <result>}`.

### AI: Setup
1. Ask for Input (URL) "Server URL" → Data Jar: Set Value `server_url`
2. Ask for Input (Text) "API token" → Data Jar: Set Value `api_token`
3. Get Contents of URL: GET `{server_url}/health` header Authorization —
   approve the connection prompt → Show Result

### AI: Poll  (the zero-tap workhorse)
1. Data Jar: Get `server_url`, `api_token`
2. Repeat 5 times:
   - Get Contents of URL: GET `{server_url}/device/next-command` (auth header)
   - Get Dictionary from Input → If `id` is empty → Exit Repeat
   - Get Dictionary Value `name` → If/Otherwise chain:
     - `play_youtube_search` → Open URL `youtube://results?search_query={payload.query}` *(needs unlocked phone)*
     - `play_youtube_video` → Open URL `youtube://watch?v={payload.video_id}`
     - `run_shortcut` → Run Shortcut (name from `payload.name`, input `payload.input`)
     - `create_reminder` → Add New Reminder (title/due from payload)
     - `open_app` / `show_map` → Open URL from payload
   - Report block with the command's `id`

### AI: Send iMessage  (input: JSON `{"to": "...", "text": "..."}`)
1. Get Dictionary from Shortcut Input
2. Send Message: text=`{text}` to=`{to}` — **"Show When Run" OFF** (silent)
3. Report block

### AI: Send Email  (input: `{"to","subject","body"}`)
Send Email via Apple Mail account, "Show Compose Sheet" OFF → report block.

### AI: Set Focus  (input: `{"mode": "Work", "minutes": 60}`)
Set Focus `{mode}` until `{minutes}` from now → report block.

### AI: Timer  (input: `{"minutes": 10}`)
Start Timer `{minutes}` → report block.

### AI: Home Scene  (input: `{"scene": "Good Night"}`)
Control Home → run scene → report block. (Also runs from a locked phone.)

### AI: Navigate  (input: `{"destination": "..."}`)
Open URL `comgooglemaps://?daddr={destination}&directionsmode=driving`
(falls back to `maps:?daddr=`) → report block.

### AI: Prefill WhatsApp  (input: `{"phone": "9725…", "text": "..."}`)
Open URL `whatsapp://send?phone={phone}&text={text}` — WhatsApp opens with
the message prefilled; **you tap send** (WhatsApp does not allow silent
third-party sends — that's a WhatsApp policy, not a Hermes limitation).

## Notes

- Silent actions (work with phone locked): iMessage, Mail, Focus, timers,
  HomeKit, HTTP calls. Screen actions (open YouTube/Maps) queue until unlock.
- The pack is versioned: bump `pack_version` in the manifest when you change
  a shortcut, and the app will show an "update available" hint.
- Optional zero-tap upgrade: a spare device running Pushcut Automation
  Server can execute the whole pack headlessly (see docs/assistant/setup.md).
