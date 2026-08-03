# Skill Lifecycle — create, patch, shadow, retire, or capture nothing

## The decision

| Situation | Action |
|---|---|
| Procedure worked end-to-end, class-level, will recur | **Create** (if no existing skill shares its trigger) |
| An existing skill shares the trigger | **Patch** that skill — add a step/pitfall, never a sibling skill |
| A bundled skill is wrong for this user | **Shadow** it at `/skills/<same-name>/` |
| Skill superseded, domain dead, shadow obsolete | **Retire** with `delete` |
| Failure, negative claim, one-off, fact | **Capture nothing** into skills — see the do-not-capture list |

## Create

The bar, all four required:
1. It **worked** — completed end-to-end at least once, this conversation.
   A skill is a record of success, never a plan or a hypothesis.
2. **Class-level** — "email triage", "flight booking", not "Tuesday's
   thread". Test: strip every date, id, and proper noun; is there still a
   procedure left?
3. **Will fire again** — you can phrase the trigger in the user's words.
4. **Non-obvious** — a fresh session with only the tool docstrings would
   plausibly get it wrong (order, glue, a trap). If docstrings suffice,
   don't write it.

Then follow format.md and `write_file("/skills/<name>/SKILL.md", ...)`.

## Patch

Patch the moment a defect is found — before the conversation ends, while the
correct call is still in context:

```
read_file("/skills/gmail-triage/SKILL.md")
edit_file(
    file_path="/skills/gmail-triage/SKILL.md",
    old_string="list_gmail_messages(query=\"in:inbox\")",
    new_string="list_gmail_messages(query=\"in:inbox is:unread newer_than:1d\", max_results=25)",
)
```

- Patch triggers: wrong parameter, missing step, a newly discovered trap
  (append to Pitfalls), a stale claim, a better sequence you just proved.
- Keep patches surgical — `edit_file` on the failing line, not a rewrite.
  After editing, re-read the whole section: a patch that renumbers steps or
  contradicts a pitfall is worse than the bug.
- Body patches take effect immediately (bodies are read live). Only
  name/description changes wait for the next conversation's index rebuild.

## Shadow (overriding a bundled skill)

Sources load in order — bundled directory first, `/skills/` second — and on
a name collision **the last source wins**. So
`write_file("/skills/planning/SKILL.md", ...)` replaces the bundled
`planning` skill in the index from the next conversation on.

Rules, because this is powerful and dangerous:
1. Shadow only for a proven, user-specific correction — never on a hunch.
2. A shadow **replaces wholesale, it does not merge**. First
   `read_file` the bundled skill at the path shown in your index, copy the
   full body, then apply the minimal change. A two-line shadow silently
   deletes everything else the bundled skill knew.
3. Bundled `references/` files stay readable at their original bundled
   paths — keep pointing at them rather than copying them.
4. Open the shadowed body with one line of provenance:
   `> Shadows the bundled skill: <what changed and why, date>.`
5. Undo = retire the shadow; the bundled original resurfaces next
   conversation. Cheap to reverse — say so to the user when you shadow.

## Retire

`delete("/skills/<name>")` — recursive: removes SKILL.md, references/, and
any state files under the directory.

- Retire when: superseded (its trigger now belongs to another skill —
  retire in the same turn you patch the survivor), the user confirms a
  domain is over, or a shadow is no longer needed.
- **Check for state first**: `ls("/skills/<name>/")`. Ledgers or progress
  files are user data — offer to preserve via
  `save_note(title=..., content=..., path=...)` before deleting.
- Domain skills (built by domain-builder) have routines pointing at their
  paths: `list_routines()` and delete/update dependents, or tomorrow's
  headless run fails citing a path that no longer exists.
- Never retire on suspicion mid-task. Disable-by-clarifying is free:
  tighten the skill's NOT-line instead.

## The do-NOT-capture list (refusal hardening)

The failure mode: skills reload every session as trusted ground truth — you
wrote them, so future-you believes them over a fresh attempt. A wrong
*positive* procedure is self-correcting: it fails loudly next run and gets
patched. A wrong *negative* claim is **self-sealing**: "the connector is
down" / "search_web can't find Hebrew results" prevents the very retry that
would disprove it. One transient failure, captured, becomes a permanent
refusal you will cite against yourself for months.

Never capture into a skill:
1. **Environment-dependent failures** — auth expiry, rate limits, connector
   outages, timeouts, a service being flaky today. Handle in the moment;
   write nothing.
2. **Negative tool-capability claims** — "tool X doesn't work / can't do
   Y". Sole exception: verified against the tool's own docstring or
   signature (not one failed call), written as a Pitfall in positive form
   with the working path attached — "There is no update_calendar_event;
   reschedule = list → delete → create". A dead end without its detour is
   forbidden.
3. **Unresolved failures** — no skill from a procedure that never
   succeeded. "Attempted approaches" and half-plans harden into fake
   authority.
4. **One-off specifics** — dates, ids, a single thread. → `remember_fact`.
5. **User facts and preferences** — → memory (below).
6. **Secrets and content** — tokens, passwords, message bodies. Skills are
   procedures, not archives.

Gray zone: the user rejecting a staged send/trade is a *preference signal*
(→ memory), not a failure and not a pitfall.

## Skills vs memory vs workspace — the routing table

| It is... | Goes to |
|---|---|
| A repeatable procedure (how-to) | `/skills/<name>/SKILL.md` |
| A durable fact about the user | `manage_memory_file(file="USER" or "MEMORY", action="add", text=...)` |
| A long-tail one-off fact | `remember_fact(fact, category=...)` |
| Something said in a past conversation | `session_search` at need — never pasted into a skill |
| A user-facing document | `save_note` / `create_artifact` (workspace) — write-only from your side |
| Machine state a skill maintains | sibling file in `/skills/<name>/` — the only cross-session read+write location |

Keep each fact in exactly one place. "User prefers window seats" is memory;
the `flight-booking` skill's procedure says
`recall_memories("flight seating airline preferences")` rather than
embedding the preference — so when the preference changes, memory updates
and the skill stays true.

## How loading actually works (why timing surprises happen)

- The index (name + description + path per skill) is built once at the
  start of a conversation and cached in that conversation's state. New
  skills and renamed/redescribed ones appear **next conversation**; body
  edits apply **immediately** because bodies are fetched live with
  `read_file`. After creating a skill you can still use it this
  conversation — you know its path — it just isn't listed yet.
- All three run modes load the same skills — chat, headless routine runs,
  and the WhatsApp webhook handler. A skill written in chat drives
  tomorrow's routine, which has *no conversation context and a reduced
  toolset* (no routine-management tools, for one). So bodies must be
  self-contained (literal paths, literal ids) and degrade gracefully when
  a tool is absent.
- Subagents (`researcher`, `analyst`, anything from `spawn_agent`) load
  **no skills at all**. Never write a skill "for the researcher" — it will
  never see it. Guidance for delegated work belongs in the parent skill's
  Procedure ("delegate X to task(subagent_type='researcher', ...) with
  these instructions: ...") or in the spawned agent's `system_prompt`.
- A skill silently dropped by the loader (bad frontmatter) is
  indistinguishable in chat from one that never existed. If a skill you
  wrote isn't listed next conversation, `read_file` it and check the
  frontmatter before rewriting anything.
