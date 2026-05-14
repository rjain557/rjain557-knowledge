---
description: Distill the recent exchange into vault topics — update existing, create new where substantial. Runs contradiction detection.
---

Walk through this exact sequence:

1. Read `claude-memory/index.md` for the topic taxonomy.
2. Read the last hour of conversation log at `C:/Users/Administrator/.claude/projects/d--VSCode-rjain557-knowledge-rjain557-knowledge/conversation-log/<today>.md`.
3. Decide if the exchange produced **durable human knowledge**. Skip if trivial, code-structural-only (GitNexus would derive it), or purely procedural.

For each candidate piece of durable knowledge:

4. Find a matching topic file (by name or aliases). If a clear match exists:
   - Compare the new info against the existing `## Key facts` and `## Decisions & rationale` sections.
   - Classify: **compatible / clarifying / contradicting / replacing**.
   - Apply the rule from CLAUDE.md (Contradiction handling).
5. If no matching topic exists and the new info is substantial (>1 paragraph of durable content), create a new topic page using the schema:

```yaml
---
topic: <short name>
aliases: [<alternate names>]
volatility: stable | evolving | ephemeral
last_updated: <today>
confidence: high | medium | low
sources: [session:<id>, commit:<sha>, ...]
access_count: 0
last_accessed: <today>
---

# <Topic>

## Summary
## Key facts
## Decisions & rationale
## Open questions
## Related code
## Related topics  (use [[wiki-links]] to neighbors)
```

6. Update `claude-memory/index.md` with any new topic.
7. Append to CHANGELOG with the appropriate tag (`[consolidate]`, `[contradiction]`, `[replaced]`).
8. Run `git -C <vault> add claude-memory && git -C <vault> commit -m "[consolidate] <summary>"`.

Conservative defaults:
- Prefer updating existing topics over creating new ones.
- Default new topics to `evolving`. Only mark `stable` if the content is canonical reference material; only mark `ephemeral` if it's clearly transient.
- Never silently overwrite existing content. Use the contradiction flow.
