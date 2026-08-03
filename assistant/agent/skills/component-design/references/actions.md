# Actions — the hermes:// contract

Components are alive because the host intercepts navigation. Exact behavior
(HermesApp/src/components/HtmlComponentCard.tsx, `handleAction`):

- `hermes://open?url=<encoded>` — the host runs
  `new URL(href).searchParams.get('url')` and passes the decoded value to
  `Linking.openURL(target)`. Opens ANYTHING the phone can open: app URL
  schemes, universal https links, tel/sms/mailto. Failures are swallowed
  (`.catch(() => undefined)`) — a bad scheme just does nothing, silently.
- `hermes://say?text=<encoded>` — the decoded value is sent as a **user
  message** into the current chat (`useChat.getState().send(text)`). You will
  receive it as the next user turn and act on it with your tools.
- Every other navigation is blocked (only `about:blank` and `data:` may
  load). A plain `<a href="https://…">` does nothing at all.

There is exactly ONE URL per open — no fallback chain. The device-queue tools
try scheme-then-https; your links cannot. So default to universal https links
(iOS routes them into the installed app for YouTube, Spotify, WhatsApp, Apple
Maps) and use bare schemes only for targets with no https form
(`tel:`, `sms:`, `weather://`, `calshow://`, `mobilenotes://`).

## Encoding — the part that actually breaks

1. Build the target URL or say-text as a plain string.
2. `encodeURIComponent` the WHOLE string once. This turns `:` `/` `?` `=` `&`
   `#` `+` `%` into safe escapes. An unencoded `&` truncates your payload at
   parse time; an unencoded `#` deletes everything after it.
3. If the target already contains percent-escapes, they get encoded again —
   that is correct and required:

```text
target:  https://www.youtube.com/results?search_query=daft%20punk
encoded: https%3A%2F%2Fwww.youtube.com%2Fresults%3Fsearch_query%3Ddaft%2520punk
                                                                       ^^ %20 → %2520
```

Use double-quoted href attributes: `encodeURIComponent` leaves apostrophes
alone (`Sarah's` stays `Sarah's`), which breaks single-quoted attributes.

## open vs say — decide in one line

| Situation | Use |
|---|---|
| Result lives in another app (video, route, call, compose) | `hermes://open` — instant, no agent round-trip |
| Work needs your tools (reply to email, create event, fetch more) | `hermes://say` |
| Confirmation of a staged action ("Send it") | `hermes://say` |
| Drill-down / pagination / refinement | `hermes://say` |

Never mint a `say` chip for something `open` does instantly (a play button
must play NOW), and never `open` something that needs server-side state.

## Deep-link catalog (verified against HermesApp/src/device/toolExecutor.ts)

| App | Target (pre-encoding) | Notes |
|---|---|---|
| YouTube video | `https://www.youtube.com/watch?v=<id>` | universal link; get id from `search_youtube_videos` |
| YouTube search | `https://www.youtube.com/results?search_query=<q>` | scheme form: `youtube://results?search_query=<q>` |
| Spotify | `spotify:track:<id>` / `spotify:search:<q>` / `spotify:playlist:<id>` | https form: `https://open.spotify.com/track/<id>` |
| Apple Maps place | `maps:?q=<query>` | also `https://maps.apple.com/?q=<query>` |
| Apple Maps route | `maps:?daddr=<destination>` | Google Maps: `comgooglemaps://?q=<q>` |
| Mail inbox | `message://` | opens Apple Mail |
| Mail compose | `mailto:<addr>?subject=<s>&body=<b>` | the `&` MUST end up encoded |
| Phone / SMS | `tel:+<E164>` / `sms:+<E164>&body=<text>` | iOS uses `&body` on sms |
| WhatsApp | `https://wa.me/<number>?text=<msg>` | scheme: `whatsapp://send?phone=<n>&text=<m>` |
| Calendar | `calshow://` | day view; no reliable event deep link |
| Weather | `weather://` | Apple Weather |
| Notes / Photos / Camera | `mobilenotes://` / `photos-redirect://` / `camera://` | |
| Shortcuts | `shortcuts://run-shortcut?name=<name>` | runs a user shortcut directly |
| Any web page | `https://…` | Safari (or the owning app via universal link) |

## 10 worked examples (complete, correctly encoded)

1. Play a specific YouTube video (media card play button):
```html
<a href="hermes://open?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DdQw4w9WgXcQ">▶</a>
```

2. Open YouTube search results ("more like this"):
```html
<a href="hermes://open?url=https%3A%2F%2Fwww.youtube.com%2Fresults%3Fsearch_query%3Dlofi%20beats">More on YouTube ↗</a>
```

3. Play a Spotify track:
```html
<a href="hermes://open?url=spotify%3Atrack%3A4uLU6hMCjMI75M1A2tKUQC">Play on Spotify ↗</a>
```

4. Directions in Apple Maps (schedule card, next meeting's venue):
```html
<a href="hermes://open?url=maps%3A%3Fdaddr%3DBen%20Gurion%20Airport">Route ↗</a>
```

5. Compose an email in Mail (note `?` and the pre-encoded space both escaped):
```html
<a href="hermes://open?url=mailto%3Asarah%40acme.com%3Fsubject%3DRe%3A%20Q3%20budget">Compose ↗</a>
```

6. Call, or text with a prefilled body (`&body` encoded as `%26body`):
```html
<a href="hermes://open?url=tel%3A%2B15551234567">Call ↗</a>
<a href="hermes://open?url=sms%3A%2B15551234567%26body%3DRunning%2010%20min%20late">Text ↗</a>
```

7. WhatsApp with prefilled text:
```html
<a href="hermes://open?url=https%3A%2F%2Fwa.me%2F15551234567%3Ftext%3DOn%20my%20way">WhatsApp ↗</a>
```

8. Open a source article (news digest row):
```html
<a href="hermes://open?url=https%3A%2F%2Fexample.com%2Fpost%2Fq3-outlook">Read ↗</a>
```

9. `say` — row-scoped agent work. The `#` must be `%23` or the text truncates:
```html
<a href="hermes://say?text=Summarize%20the%20Stripe%20email%20about%20invoice%20%231284">Summarize</a>
<a href="hermes://say?text=Draft%20a%20reply%20to%20Sarah's%20Q3%20budget%20email%3A%20I'll%20review%20it%20tonight">Reply</a>
```

10. `say` — pagination, drill-down, confirmation:
```html
<a href="hermes://say?text=Show%20me%20the%20next%205%20emails">Show 5 more</a>
<a href="hermes://say?text=Details%20on%20my%20AAPL%20position">Details</a>
<a href="hermes://say?text=Yes%2C%20send%20it">Send it</a>
```

## Writing good say-texts

The decoded text arrives verbatim as the user's next message — write it as a
complete, self-contained user turn:

- Include the identifying context, not a pronoun: "Draft a reply to Sarah
  Chen's Q3 budget email", never "Reply to this" (by the time it fires, "this"
  may be three turns old).
- Imperative, ≤120 chars, one action per chip.
- For confirmations of staged work, name the work: "Yes, send the drafted
  reply to Sarah" beats "Yes".
- Bad → good: `More` → `Show more flight options for Aug 12`;
  `Fix it` → `Retry the failed Stripe payment for invoice #1284`.

## Action pitfalls

- **Nested anchors are invalid HTML** and break tapping: a fully-tappable row
  (`<a class="hit">`) cannot contain chips — put chips in a sibling row.
- Style every `<a>`: default rendering is blue + underlined. Chips and rows
  need explicit `color` and `text-decoration:none`.
- `open` failures are silent. If unsure the app exists, use the https form or
  offer a `say` fallback chip ("Play it for me") that routes through
  `play_youtube_video` / `open_iphone_app` on the backend.
- Don't duplicate the built-in long-press reshape row (Simpler / More detail /
  As a chart) as chips.
- 2–4 affordances per component. A card where everything is tappable
  communicates that nothing is.
