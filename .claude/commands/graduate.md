---
description: Recommend whether to stay on the current vault stack, do cleanup, or upgrade (LightRAG / aliases / etc.)
---

1. Read `claude-memory/HEALTH.md`.
2. If `Days since last review` > 30: refuse to give a recommendation. Print: "Cannot trust health metrics — `/review` is overdue by N days. Run `/review` first." Stop.
3. If `Retrieval log lines` < 100 (insufficient data): print "Need 30 days of retrieval data. Currently <N> log lines. Stay put — recommendation requires more signal."
4. Otherwise, classify and recommend:

### GREEN

```
Stay put. Vault is healthy.
- Topic count: <N> (under 150)
- Hit rate: <X%> (over 70%)
- Stale-180: <Y%> (under 10%)
Next check: <today + 7 days>
```

### YELLOW

```
Cleanup before upgrade. Run these in order:
1. /consolidate (collapse near-duplicates)
2. /review (handle volatility candidates and prune)
3. Touch hot stale topics (high access, last_updated >60 days)
Recheck in a week. If still YELLOW, then consider upgrade.
```

### RED — pick the recommendation that matches the cause

- Topic count > 400 with hit rate < 50% → "Migrate to LightRAG. The vault has outgrown markdown-as-knowledge-base."
- Miss rate > 30% with topic count moderate → "Add aliases first. Many prompts aren't matching topics they should. Try aliases for two weeks. If still RED, then LightRAG."
- Stale > 25% → "Not a tooling problem — it's neglect. Run `/consolidate` aggressively over a week. Don't migrate yet."
- Heavy PDF / large-document corpus → "LightRAG for this repo specifically — markdown is the wrong shape for that volume."

For each recommendation include:
- The migration command (if any)
- What you'd lose by upgrading (eg. easy human edits in markdown, free Obsidian search, simple git history)

End every output with: `Last review: <date>. Days since: <N>. Next review due: <date+7>.`
