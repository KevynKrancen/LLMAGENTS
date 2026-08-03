---
name: skill-authoring
description: How to write and improve your own skills in /skills/. Use after difficult or repeated tasks, or when a loaded skill was wrong or incomplete.
---

# Skill Authoring (self-improvement)

You may write new skills to /skills/<name>/SKILL.md with the file tools.
After a difficult or iterative task, offer to save the working procedure as
a skill. If a skill you loaded was missing steps or had wrong commands,
update it before finishing the conversation.

## Format
YAML frontmatter: name, description (≤60 chars — longer is silently cut
from the index). Body: When to Use → Procedure (numbered) → Pitfalls →
Verification.

## Rules
- Prefer patching an existing skill over creating near-duplicates.
- Class-level skills ("email triage"), never one-off fixes ("fix Tuesday's
  bug").
- Never capture environment-dependent failures or "tool X doesn't work"
  claims — they harden into refusals you'll cite against yourself later.
- Procedures belong in skills; facts about the user belong in memory.
