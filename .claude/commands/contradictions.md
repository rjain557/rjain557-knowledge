---
description: List every unresolved contradiction in the vault with context, then offer to resolve each
---

Scan every file under `claude-memory/topics/`. Read each file's `## Open questions` section. Find every line that begins with `CONTRADICTION` (case-insensitive).

For each contradiction:

1. Topic name and link
2. Date the contradiction was detected
3. The conflicting claims (verbatim)
4. Brief recommendation:
   - **Preserve both** if both versions might still be true in different contexts
   - **Pick one** with rationale (often the newer source if reproducible / authoritative)
   - **Investigate further** if neither claim is well-sourced

After the user decides per-contradiction:

- Update the topic frontmatter `confidence:` (raise it back up after resolution)
- Edit the topic body to remove the contradiction line and update the affected `## Key facts` / `## Decisions` sections
- Append a `[manual]` line to CHANGELOG summarizing the resolution
- Commit with `[manual]` tag

If there are no contradictions, output: `No unresolved contradictions in the vault.`
