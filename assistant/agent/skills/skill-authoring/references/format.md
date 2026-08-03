# Skill Package Format

Exactly what the loader (deepagents `SkillsMiddleware`) accepts, what it does
on violations, and the house templates. Written for skills you author under
`/skills/<name>/`.

## Anatomy

```
/skills/gmail-triage/
├── SKILL.md                  # required — frontmatter + operating procedure
├── references/
│   └── vip-rules.md          # optional — deep material, read on demand
└── senders.md                # optional — machine-readable state you maintain
```

Only directories directly under `/skills/` that contain a `SKILL.md` are
skills. Extra files are invisible to the index; they exist only because your
SKILL.md body points at them.

## How the index works (what you're writing FOR)

At the start of each conversation the loader scans every source and injects
one entry per skill into the system prompt:

```
- **gmail-triage**: Inbox triage — unread sweep, VIP flags, staged replies.
  -> Read `/skills/gmail-triage/SKILL.md` for full instructions
```

Two consequences that shape everything below:

1. **The description is the ONLY text in context at trigger time.** The body
   is read with `read_file(path, limit=1000)` *after* the decision to use the
   skill. A description that doesn't say when to fire means the skill never
   fires.
2. **Every description rides in every system prompt of every session** —
   chat, routine runs, and webhook handling alike. Your skills accumulate for
   months; the index is a permanent per-turn token tax.

## Frontmatter

First bytes of the file, fenced by `---` lines, YAML mapping:

```yaml
---
name: gmail-triage
description: Inbox triage — unread sweep, VIP flags, staged replies.
---
```

| Field | Rule | On violation |
|---|---|---|
| `---` fences | must open at byte 0 and close before the body | skill silently skipped — no error reaches you |
| `name` | required; MUST equal the directory name; lowercase a-z, digits, single hyphens; no leading/trailing `-`, no `--`; ≤64 chars | missing → skipped silently; mismatch/format → loads with a server-side warning only — keep it legal anyway |
| `description` | required; house rule ≤60 chars; hard cap 1024 | missing → skipped silently; >1024 → truncated at 1024, the rest never seen at trigger time |
| `license`, `compatibility`, `metadata`, `allowed-tools` | optional spec fields | you will essentially never need these — omit |

All failures above surface only in backend logs, never in chat. That is why
verification always ends with reading the file back.

### Description: the 60-char rule and why

The spec allows 1024 chars, but for skills YOU author the rule is **≤60**:

- At trigger time it competes with every other index line for one decision —
  a long description is skimmed, not read, and blurs discrimination between
  adjacent skills.
- The index is paid for on every turn forever. Twenty self-authored skills at
  200 chars each is a permanent ~1000-token overhead that buys nothing.
- 60 chars forces trigger-phrasing: domain noun + firing situation, nothing
  else. Rationale, features, and caveats belong in the body.

Formula: `<domain> — <when it fires>`.

| | |
|---|---|
| GOOD | `Inbox triage — unread sweep, VIP flags, staged replies.` (55) |
| GOOD | `Weekly review — Sunday summary of calendar, mail, goals.` (56) |
| BAD | `A comprehensive skill for handling all aspects of email management including reading, triaging, and responding to messages` — 122 chars, zero trigger words, "comprehensive/all aspects" is anti-signal |
| BAD | `Email helper.` — fires never (no situation) or always (too broad) |

## Body: the four sections

Copy this skeleton; every section is mandatory:

```markdown
# <Title> — <one-phrase promise>

## When to Use
- <trigger phrased in the user's words, not the skill's internals>
- <second trigger>
- NOT for <nearest non-trigger> — <what to do instead>.

## Procedure
1. **<Verb phrase>** — `tool_name(param="literal example")`. <what the
   result feeds into the next step>
2. ...

## Pitfalls
- **<trap>** — <consequence>. <the correct move>.

## Verification
- <a call to run and the exact shape its result must have>
```

Per-section rules:

- **When to Use** — at least one NOT line. The NOT line is what stops a skill
  from greedily absorbing neighboring tasks.
- **Procedure** — 3–9 numbered steps. Every step is anchored on a real tool
  call with real parameter names and literal example values
  (`list_gmail_messages(query="in:inbox is:unread newer_than:1d",
  max_results=25)`, never "fetch the emails"). Make data flow explicit:
  "record the `message_id`; step 3 needs it."
- **Pitfalls** — each entry is trap → consequence → correct move. This is
  the ONLY sanctioned place for a negative capability claim, and only in
  positive framing with the working path attached: "There is no
  update_calendar_event. Rescheduling = list → delete → create." (see
  lifecycle.md for why free-floating negatives are forbidden).
- **Verification** — only checks executable next session: a tool call plus
  what its output must show. "Make sure it worked" is not a verification.

Keep SKILL.md under ~120 lines. Past that, split.

## references/ conventions

- Split when the body would exceed ~120 lines, when material is needed only
  sometimes (templates, cookbooks, worked walkthroughs), or when it's bulky
  (HTML/scaffold blocks).
- Pointer form in the body — a *condition*, not "see also":
  `Read references/vip-rules.md when a sender isn't in senders.md.`
- 2–3 references max, named by topic (`scheduling.md`, `dashboard-templates.md`)
  — never `notes.md` or `misc.md`.
- Each reference is standalone-deep: full templates, exact call sequences,
  worked examples. Zero repetition of SKILL.md — a reference that restates
  the procedure is dead weight read twice.
- Write via `write_file("/skills/<name>/references/<topic>.md", ...)`; read
  back any later session with `read_file`.

## State files

`/skills/<name>/` is the only location that is both writable and readable
across sessions (workspace notes and artifacts cannot be read back). Keep a
skill's canonical machine state as sibling `.md` files — ledger, progress,
watch-list — one record per line for easy `edit_file` appends. The SKILL.md
body must name these paths literally, since routine runs execute headless
with no conversation context.

## Worked example

### GOOD — `/skills/gmail-triage/SKILL.md`

```markdown
---
name: gmail-triage
description: Inbox triage — unread sweep, VIP flags, staged replies.
---

# Gmail Triage

## When to Use
- "Check my email", "anything important?", morning-brief inbox section.
- NOT for composing new outbound mail from scratch — do that directly
  (send_gmail is approval-gated; just stage it).

## Procedure
1. **Sweep** — `list_gmail_messages(query="in:inbox is:unread
   newer_than:1d", max_results=25)`. Record each `message_id`.
2. **Rank** — people over automated senders. VIPs live in
   `/skills/gmail-triage/senders.md` (one address per line); read it
   first. Unknown-but-human sender → read
   references/vip-rules.md and classify.
3. **Read only the top 3** — `read_gmail_message(message_id)` each.
   Never read all 25; the subject line is enough for the rest.
4. **Stage replies, don't offer** — for anything expecting an answer:
   `draft_gmail_reply(message_id, body)` with a full draft. Approval
   surfaces natively; the user one-taps.
5. **Show, don't tell** — one render_component inbox card
   (component-design skill), one sentence of text.

## Pitfalls
- **There is no mark-as-read tool.** Don't claim mail was "handled" —
  say what was flagged and what's staged.
- `newer_than:2d` on Mondays (weekend backlog), `1d` otherwise.
- A staged reply the user rejects is a preference signal — add one line
  to senders.md or MEMORY, don't re-stage.

## Verification
- Every staged draft's message_id came from step 1's sweep this turn.
- The card shows only ranked unread mail, no invented senders.
```

Why it works: description fires on the user's actual words (55 chars);
every step is a real tool with real params; state file named literally;
the one negative claim is pitfall-framed with the honest alternative;
verification is checkable.

### BAD — `/skills/fix-newsletter-problem/SKILL.md`

```markdown
---
name: Fix_Newsletter_Problem            ← uppercase + underscores: spec-illegal,
                                          and ≠ directory name
description: This skill helps deal with the annoying problem where the
  inbox gets flooded with newsletters and the user asked me on Tuesday
  to fix it...                          ← 150+ chars, narrates an incident,
                                          contains zero trigger words
---

# Fixing the newsletter problem

Last Tuesday the user complained about newsletters.   ← incident, not class →
                                                        this is remember_fact
                                                        material at best
Gmail search doesn't work well for newsletters.       ← unverified negative
                                                        claim: refusal
                                                        hardening — forbidden
Go through the emails from before and archive them.   ← "from before": no ids,
                                                        no query, no tool —
                                                        unrunnable next session
                                                        (and there is no
                                                        archive tool at all)
```

No When to Use / Pitfalls / Verification, procedure references dead context,
name breaks two rules, and it enshrines a false negative. Everything real in
it compresses to one senders.md line inside gmail-triage plus one
remember_fact — which is exactly where it should have gone.
