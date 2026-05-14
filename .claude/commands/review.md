---
description: Weekly vault review — checklist of topics added/changed, contradictions to resolve, volatility to retune, ephemeral pages near auto-archive
---

You are running the **weekly vault review** for the rjain557-knowledge / Cortex repo. Target time: 5–10 minutes for the user.

## Inputs to read

1. `claude-memory/HEALTH.md` — the dashboard
2. `claude-memory/CHANGELOG.md` — last 7 days of mutations only
3. `claude-memory/topics/*.md` — to spot-check anything flagged
4. The `## Open questions` sections in any topic — these are the contradictions to resolve

## What to produce

A markdown checklist organized into 6 sections. Each item must include a topic link and a one-line context. The user reads, decides, and tells you which to act on.

### 1. New topics this week

Scan CHANGELOG for `[bootstrap]`, `[consolidate]` entries that created new topic pages. List them. Quick quality check: does each have all required frontmatter fields? Is the body non-trivial? Does it duplicate an existing topic?

### 2. Topics updated this week

Scan CHANGELOG for `[consolidate]` entries that touched existing pages. List them. Spot-check: does the update preserve prior content (or correctly mark contradictions / replacements)?

### 3. Unresolved contradictions

Read every topic file's `## Open questions` section. Surface any line containing the word "CONTRADICTION". For each, state the conflict and offer a recommendation (preserve both / pick one / merge / dismiss).

### 4. Volatility candidates to reclassify

- `stable` topics changed in the last 30 days → maybe should be `evolving`
- `evolving` topics that have been stable for 90+ days → maybe should be promoted to `stable`
- `evolving` topics describing transient state ("current state of X", "today's failing tests") → maybe should be `ephemeral`

For each candidate, propose the new tier and ask for confirmation.

### 5. Ephemeral topics approaching 60-day auto-archive

Find every `volatility: ephemeral` topic where `last_updated` is older than 50 days AND `access_count` was unchanged in that window. List them. The user can extend (touch + update) or let auto-archive proceed.

### 6. Prune candidates

- `access_count: 0` AND `last_updated` > 60 days → suspect dead weight
- Topics that exist but never appear in `claude-memory/index.md` → orphans
- Near-duplicate topics (similar names / aliases) → consolidation opportunities

## Output format

```
# Weekly Vault Review — <date>

## 1. New topics this week
- [ ] [[topic_name]] — context · QUALITY: ok / needs work / duplicate of [[other]]

## 2. Topics updated this week
- [ ] [[topic_name]] — what changed · update preserved prior content? yes/no

## 3. Unresolved contradictions
- [ ] [[topic_name]] — "old says X, new says Y" · my recommendation: ...

## 4. Volatility candidates
- [ ] [[topic_name]] (stable → evolving) because ...
- [ ] [[topic_name]] (evolving → ephemeral) because ...

## 5. Ephemeral approaching auto-archive
- [ ] [[topic_name]] — last_updated 56 days ago, access_count 0 since · keep / archive

## 6. Prune candidates
- [ ] [[topic_name]] — access_count 0, last_updated 75 days ago · keep / archive / merge into [[other]]

---

After the user marks decisions, apply them:
- Update topic frontmatter (volatility, last_updated)
- Move archived pages to `_archive/`
- Commit with `[reorg]` or `[archive]` tag prefix
- Update HEALTH.md `Last /review run` date to today
- Append a `[manual]` entry to CHANGELOG summarizing decisions
```

After completion, the user has run a review and HEALTH.md `Last /review run` is now today — the SessionEnd hook will stop nagging.
