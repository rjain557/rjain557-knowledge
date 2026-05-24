---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-24T07:12:31.038902-07:00
---

# Implement idempotent, resumable deep-research runs with a status state-machine in the DB

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Commit 9ef5fa9 fixed record_link to be idempotent after retried extractions crashed, revealing that the pipeline lacks crash-safe resumability at the deep-research layer. Vault note [6] ('agents without memory start cold') warns that stateless pipelines re-do expensive work on restart. Currently a failed deep-research run leaves no durable status, so a retry either duplicates API calls or silently skips. Adding a runs table with states (pending→running→done/failed) and checking it before launching a new run would make the pipeline safe to retry from cron without duplicate Anthropic API charges.

## Cited evidence

- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Files to read first:
  - sql/  (all .sql migration files — understand current schema)
  - src/cortex/deep_research/  (or wherever the deep-research pipeline lives — find it with: find src -name '*.py' | xargs grep -l 'deep_research\|DeepResearch' | head -20)
  - src/cortex/db/  (connection helpers, record_link, etc.)
  - CLAUDE.md

Task: Add a durable state-machine for deep-research runs so retries are safe and idempotent.

Steps:
1. Add a migration file sql/004_deep_research_runs.sql (increment number to match existing sequence):
   CREATE TABLE deep_research_runs (
     id            INT IDENTITY PRIMARY KEY,
     topic         NVARCHAR(500)  NOT NULL,
     source_id     INT            NULL REFERENCES sources(id),  -- nullable for topic-only runs
     status        NVARCHAR(20)   NOT NULL DEFAULT 'pending',   -- pending|running|done|failed
     started_at    DATETIMEOFFSET NULL,
     finished_at   DATETIMEOFFSET NULL,
     error_msg     NVARCHAR(MAX)  NULL,
     vault_path    NVARCHAR(1000) NULL,
     created_at    DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
     CONSTRAINT uq_dr_topic_source UNIQUE (topic, source_id)
   );

2. In src/cortex/db/ add helpers:
   - upsert_dr_run(topic, source_id) -> run_id  (INSERT if not exists, return id)
   - set_dr_status(run_id, status, error_msg=None, vault_path=None)
   - get_dr_run(topic, source_id) -> dict | None

3. In the deep-research pipeline entry point:
   - At start: call upsert_dr_run; if existing status == 'done', log and return early (idempotent)
   - If status == 'running' and started_at < now - 2h, treat as stale and re-run (hung process guard)
   - Call set_dr_status(run_id, 'running') before the Anthropic API call
   - On success: set_dr_status(run_id, 'done', vault_path=written_path)
   - On exception: set_dr_status(run_id, 'failed', error_msg=str(e)); re-raise

4. Update the hourly GitHub-trending scanner and any other callers to pass source_id where available.

Edge cases:
  - topic normalisation before UNIQUE check: strip whitespace, lowercase
  - source_id=NULL uniqueness: SQL Server treats two NULLs as distinct in UNIQUE constraints — use a filtered index or a sentinel value (e.g. source_id=0 for topic-only)
  - Concurrent runs: add a TRY/CATCH around the INSERT in upsert_dr_run and return existing id on duplicate key

Verification:
  - Apply migration: run the .sql file against the dev DB
  - Trigger a deep-research run manually; confirm row appears in deep_research_runs with status='done'
  - Trigger the same topic again; confirm it returns early without calling the Anthropic API (check logs)
  - Simulate failure by raising inside the pipeline; confirm status='failed' and error_msg is populated
  - Run existing pytest suite to confirm no regressions
```
