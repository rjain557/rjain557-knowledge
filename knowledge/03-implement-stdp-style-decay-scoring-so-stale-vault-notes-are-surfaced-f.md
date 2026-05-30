---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-05-30T03:01:42.068502-07:00
---

# Implement STDP-style decay scoring so stale vault notes are surfaced for re-synthesis

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

Vault note [2] ('GET RID OF OBSIDIAN') explains that static knowledge vaults suffer from statelessness – notes that haven't been accessed or linked recently become invisible to agents. The Cortex vault already has a nightly lint step (commit 2026-05-20) but no mechanism to score or decay note relevance over time. Adding a recency+link-degree score to each note's frontmatter (updated nightly) would let the MCP retrieval layer and deep-research scheduler prioritize genuinely stale knowledge for re-synthesis rather than always picking the newest notes.

## Cited evidence

- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/cortex/ (find the nightly lint script referenced in commit 2026-05-20)
  - knowledge/ (read 3-5 sample .md files to understand frontmatter fields)
  - scripts/ (find the scheduler or cron entry that runs nightly lint)

Task: Add a decay-score field to vault note frontmatter, updated nightly.

Step 1 – Scoring function
Create src/cortex/vault/decay_score.py with:

  HALF_LIFE_DAYS = 30  # configurable via env CORTEX_DECAY_HALF_LIFE

  def compute_score(note_date: date, inbound_link_count: int, last_synthesized: date | None) -> float:
      '''
      score = link_weight * e^(-lambda * age_days)
      link_weight = log1p(inbound_link_count) + 1
      lambda = ln(2) / HALF_LIFE_DAYS
      If last_synthesized is within 7 days, apply a 0.5x recency penalty (already fresh).
      Returns float in [0, inf); higher = more stale/valuable to re-synthesize.
      '''

Step 2 – Nightly updater
Create src/cortex/vault/update_scores.py that:
  a) Builds inbound link counts by scanning all .md files for [[WikiLink]] and markdown links (reuse logic from the graph builder if you implemented it, otherwise implement inline).
  b) For each .md file, reads frontmatter, computes score, writes back ONLY if the score changed by >0.05 (avoid noisy diffs).
  c) Adds/updates frontmatter field: cortex_decay_score: <float rounded to 3 dp>
  d) Writes files atomically (tmp + rename).
  e) Prints a summary: 'Updated N notes, top 5 stale: [slugs]'.

Step 3 – Scheduler hook
In the nightly lint script (found in step above), add a call to update_scores.py after the lint step.

Step 4 – MCP exposure
In the MCP server, add a tool get_stale_notes(domain: str | None, top_n: int = 10) that reads vault_graph.json (or scans frontmatter directly if graph not yet built) and returns the top_n notes sorted by cortex_decay_score descending.

Edge cases:
  - Notes with no date frontmatter: use file mtime as fallback.
  - Notes with cortex_decay_score already present: overwrite.
  - Very large vaults (>1000 files): process in batches of 100 to avoid memory spikes.

Verification:
  1. Run python -m cortex.vault.update_scores; confirm frontmatter of several notes now contains cortex_decay_score.
  2. Run twice; confirm only notes with score delta >0.05 are rewritten (check file mtimes).
  3. Call get_stale_notes(domain=None, top_n=5) via MCP and confirm it returns the oldest/least-linked notes.
```
