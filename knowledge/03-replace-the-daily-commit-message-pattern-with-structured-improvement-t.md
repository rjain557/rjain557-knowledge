---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-06-12T03:01:20.219071-07:00
---

# Replace the daily commit-message pattern with structured improvement tracking in SQL

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

Every commit for the past 30 days follows the pattern 'Knowledge refresh YYYY-MM-DD — N improvement prompts', meaning the improvement history lives only in git log messages with no queryable structure. The repo already has a SQL Server dependency (pyodbc, sql/ directory) and uses it for link deduplication. Storing improvement prompts in a table (with status, applied_at, repo, impact) would let the system detect when the same improvement is proposed repeatedly — a sign it was never acted on — and escalate or skip it, making the self-improvement loop actually self-aware.

## Cited evidence

- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - sql/  (all existing .sql migration files — understand current schema)
  - src/  (find the repo-review module that generates and commits improvement prompts)
  - CLAUDE.md

Task:
Add a cortex_improvements table and wire the repo-review pipeline to write/read from it.

Step 1 — Migration:
Create sql/004_improvements.sql:
  CREATE TABLE cortex_improvements (
    id            INT IDENTITY PRIMARY KEY,
    repo          NVARCHAR(200)  NOT NULL,
    title         NVARCHAR(500)  NOT NULL,
    prompt_hash   CHAR(64)       NOT NULL,   -- SHA-256 of the prompt text
    impact        NVARCHAR(10),
    effort        NVARCHAR(10),
    proposed_at   DATETIME2      DEFAULT GETUTCDATE(),
    applied_at    DATETIME2      NULL,
    skipped_at    DATETIME2      NULL,
    skip_reason   NVARCHAR(500)  NULL,
    CONSTRAINT uq_repo_hash UNIQUE (repo, prompt_hash)
  );

Step 2 — Write path:
In the repo-review module, after generating each improvement JSON object:
  - Compute SHA-256 of the `prompt` field.
  - INSERT into cortex_improvements (repo, title, prompt_hash, impact, effort) using UPSERT (MERGE or INSERT ... WHERE NOT EXISTS).
  - If the same prompt_hash for the same repo already exists with proposed_at older than 7 days and applied_at IS NULL, set a flag `stale=True` on the improvement object.

Step 3 — Read path / dedup:
  - Before committing the daily improvement prompts, query for stale improvements (proposed >7 days ago, not applied). Prepend a warning comment to the commit message: 'WARNING: N improvements from prior runs not yet applied.'
  - Skip re-proposing any improvement whose prompt_hash already exists and is <7 days old.

Edge cases:
  - DB connection may be unavailable in CI; wrap DB calls in try/except and fall back to file-based dedup using a local JSON cache at .claude/improvement_cache.json.
  - prompt_hash must be computed on the normalized prompt (strip leading/trailing whitespace, lowercase) to avoid hash mismatches from minor formatting changes.

Verify:
  - Run the migration: `uv run python scripts/run_migrations.py` (or equivalent).
  - Trigger a dry-run of repo-review and confirm a row appears in cortex_improvements.
  - Trigger it again immediately and confirm no duplicate row is inserted (UPSERT is idempotent).
  - `uv run pytest tests/ -x` passes.
```
