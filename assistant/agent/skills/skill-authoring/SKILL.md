---
name: skill-authoring
description: Write, patch, shadow, and retire your own skills in /skills/ — after hard-won tasks, repeated corrections, or when a loaded skill was wrong.
---

# Skill Authoring — self-improvement

Skills live in two layers: bundled (developer-maintained, read-only) and
`/skills/` (yours — a persistent store that survives every session; on a
name collision `/skills/` wins). Writing a skill makes a hard-won procedure
permanent. Writing a bad one makes a mistake permanent. Both compound —
author accordingly.

## When to Use
- A task took 3+ attempts, a non-obvious tool sequence, or user corrections
  before it worked — offer (one line) to save the working procedure.
- A skill you loaded this conversation had a wrong call, a missing step, or
  a stale claim — patch it before finishing, don't just work around it.
- The user asks for a standing *procedure* ("always do X this way"). A fact
  about them still goes to memory, not a skill.
- A whole new *capability* ("be my budget coach") → the domain-builder
  skill instead; it produces a domain skill as one of its steps.
- NOT for: one-off fixes, facts (→ manage_memory_file / remember_fact),
  or anything on the do-not-capture list. Read references/lifecycle.md
  whenever unsure whether to create, patch, shadow, or capture nothing.

## Procedure
1. **Check the index first.** Your system prompt lists every loaded skill;
   `ls("/skills/")` shows yours. Overlap → patch that skill (step 4);
   never create a near-duplicate.
2. **Distill from what ACTUALLY worked this conversation**: exact tool
   names, exact parameters, the order, every trap you hit. Drop anything
   you did not verify end-to-end.
3. **New skill** — read references/format.md before writing (frontmatter
   rules, section skeletons, a good-vs-bad worked example), then
   `write_file("/skills/<name>/SKILL.md", ...)`. Name = directory name,
   lowercase-with-hyphens. Description ≤60 chars, trigger-phrased. Body:
   When to Use → Procedure (numbered, real calls) → Pitfalls →
   Verification. Depth beyond ~120 lines goes to
   `/skills/<name>/references/<topic>.md`, pointed to from the body.
4. **Existing skill** — `read_file` it, then
   `edit_file(file_path, old_string, new_string)` with surgical edits.
   Bundled skills cannot be edited in place: shadow one by writing
   `/skills/<same-name>/SKILL.md` — read references/lifecycle.md
   (Shadowing) first; a shadow replaces, it does not merge.
5. **Verify** (below), then tell the user in one line what you saved —
   it is their assistant learning; they can veto.

## Pitfalls
- **Refusal hardening — the worst failure.** Never record
  environment-dependent failures, "tool X doesn't work / can't do Y"
  claims, or procedures that never actually succeeded. Skills reload every
  session as trusted ground truth; a captured negative claim blocks the
  very retry that would disprove it. Full do-not-capture list and the one
  sanctioned exception: references/lifecycle.md.
- **The index refreshes per conversation, not per turn.** A new skill (or
  changed name/description) appears in the skill list only in the next
  conversation; body edits take effect immediately, because bodies are
  read live via `read_file`. Don't re-write a skill because the index
  looks stale.
- Malformed frontmatter (missing `---` fences, or no name/description)
  makes the skill vanish from the index with no error you can see — hence
  the verification step.
- Class-level scope ("email triage"), never incident-level ("fix
  Tuesday's thread"). If it names one dated event, it's a memory.
- Descriptions over 1024 chars are hard-truncated; over ~60 they tax every
  future system prompt — the why is in references/format.md (Description).
- A skill that restates a tool's docstring is noise. Capture only what
  docstrings don't say: sequence, glue between calls, traps.
- `/skills/<name>/` is also the only place you can write files AND read
  them back in later sessions — colocate a skill's machine-readable state
  (ledger, progress) there, and name those paths in its body.

## Verification
1. `read_file("/skills/<name>/SKILL.md")` — frontmatter fenced by `---`,
   name equals the directory name, description present and ≤60 chars.
2. Every Procedure step names a real tool with real parameter names,
   copied from calls that succeeded this conversation.
3. Stranger test: the next session gets ONLY this text — no memory of
   today. Would it run? Any "as discussed", unstated id, or dangling
   reference fails.
4. Every references/ pointer resolves: `ls("/skills/<name>/")` shows the
   files the body cites.
5. Patched a skill? Re-read the edited section whole — confirm the edit
   didn't orphan a step number or contradict a pitfall.
