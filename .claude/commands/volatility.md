---
description: Set a topic's volatility tier — stable | evolving | ephemeral
arg_hint: <topic-slug> <stable|evolving|ephemeral>
---

Arguments come in as `$1` = topic slug (filename without `.md`), `$2` = new tier.

1. Locate the file at `claude-memory/topics/$1.md`. If missing, list available topics and stop.
2. Validate `$2` is one of `stable`, `evolving`, `ephemeral`. If not, abort with the valid set.
3. Read the file. Replace the `volatility:` frontmatter line with the new value. Update `last_updated:` to today.
4. Append to CHANGELOG: `[manual] volatility: $1 → $2` and the date.
5. Commit with `[manual]` tag prefix.

Volatility legend (remind the user once per `/volatility` invocation):

- **stable** — yearly review; consolidation is conservative
- **evolving** — quarterly review; default; normal consolidation
- **ephemeral** — aggressive review; auto-archive after 60 days no access; consolidate liberally
