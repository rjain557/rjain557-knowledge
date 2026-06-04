---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S
generated_at: 2026-06-04T03:01:21.721962-07:00
---

# Add active-memory decay and staleness tagging to vault notes

**Impact:** medium  ·  **Effort:** S

## Rationale

Vault note [2] (Neuromorphic & Active Memory) argues that a static file store is fundamentally limited because it never forgets or re-weights knowledge — notes from 18 months ago are treated identically to notes from yesterday. The daily knowledge-refresh commits show the vault is growing continuously. Without a staleness signal, the synthesis and retrieval steps will increasingly surface outdated content. Adding a `stale_after_days` frontmatter field and a nightly lint pass that tags notes as `status: stale` when they exceed their TTL would give the retrieval layer a cheap filter and prompt human review of decaying knowledge.

## Cited evidence

- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the nightly lint script referenced in commit 2a17649)
  - knowledge/  (read 5-10 sample notes to understand current frontmatter fields)
  - CLAUDE.md

Task: Implement staleness tagging in the nightly vault lint pass.

Step 1 — Frontmatter convention:
  Define that any vault note MAY include:
    stale_after_days: 90   # integer; absence means never-stale
    status: fresh | stale  # written by the lint pass, not by humans
  Document this in docs/vault_schema.md (create if absent).

Step 2 — Lint pass addition (add to existing lint script or create src/cortex/vault_lint.py):
  - Walk all .md files in knowledge/.
  - Parse frontmatter with python-frontmatter.
  - If `stale_after_days` is set:
      age_days = (today - note['date']).days
      if age_days > stale_after_days and note.get('status') != 'stale':
          note['status'] = 'stale'
          note['stale_flagged_at'] = today_iso
          write back the file with updated frontmatter
  - Collect all newly-staled notes; write a summary to logs/staleness_report_YYYY-MM-DD.md.

Step 3 — Retrieval filter:
  - In the MCP server's existing search/retrieval tool, add an optional parameter `include_stale: bool = False`.
  - When False, filter out notes where status == 'stale' before returning results.

Step 4 — Backfill:
  - For Inbox/ notes (sourced articles), default stale_after_days to 180 if not set.
  - For Topics/ synthesis notes, default to 365.
  - Write a one-time migration script scripts/backfill_stale_ttl.py that adds the field to all existing notes that lack it.

Edge cases:
  - Notes without a `date` field must be skipped with a warning, not crashed on.
  - The lint pass must be idempotent: running twice on the same day must not re-write files.
  - Do not mark notes as stale if they were updated (git mtime) more recently than stale_after_days, even if original `date` is old.

Verify:
  - `uv run python scripts/backfill_stale_ttl.py --dry-run` prints affected files without writing.
  - `uv run python -m cortex.vault_lint` on a test vault with a note dated 200 days ago and stale_after_days=90 produces status: stale in that note's frontmatter.
  - `uv run pytest tests/test_vault_lint.py -v` covers: fresh note unchanged, stale note tagged, missing date skipped.
```
