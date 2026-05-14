---
description: Render a readable dashboard of vault state from HEALTH.md plus quick stats
---

1. Read `claude-memory/HEALTH.md` and pretty-print it.
2. Add quick on-the-fly counts:
   - Number of topic files in `claude-memory/topics/`
   - Number of files in `claude-memory/_archive/`
   - Last 5 entries in `claude-memory/CHANGELOG.md`
3. Show the user:
   - Status (GREEN / YELLOW / RED)
   - Topic count, total words
   - Days since last `/review`
   - Number of unresolved contradictions
   - 3 most recent CHANGELOG entries
4. Recommend next action:
   - If GREEN: "Stay put. Next review due <date>."
   - If YELLOW: "Run /review and act on yellow flags."
   - If RED: "Run /graduate to see if migration is recommended."
