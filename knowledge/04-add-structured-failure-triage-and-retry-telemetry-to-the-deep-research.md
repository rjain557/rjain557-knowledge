---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-06-02T03:02:04.796423-07:00
---

# Add structured failure triage and retry telemetry to the deep-research pipeline

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

Vault note [3] ('Your AI agent is rediscovering 85% of its context every run') includes a 'Failure Triage' section that identifies the most common production failure modes for agent pipelines: silent context truncation, retrieval returning stale chunks, and LLM calls that succeed (200 OK) but return empty or malformed output. The commit history shows multiple fix commits (UTF-16LE decode bug, idempotent UPSERT, email-signature URL blocking) that were discovered reactively. Adding a structured triage table in SQL and a lightweight telemetry wrapper around LLM calls would surface these failures proactively.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the deep-research runner, the LLM client/router introduced 2026-05-24, and the DB layer)
  - sql/  (all .sql files — understand existing tables)
  - CLAUDE.md

Goal: Add a pipeline_runs telemetry table and a thin wrapper that records every LLM call outcome, so failures are queryable rather than only visible in logs.

Step 1 — Schema (sql/telemetry.sql):
  CREATE TABLE pipeline_runs (
    id            INT IDENTITY PRIMARY KEY,
    run_id        UNIQUEIDENTIFIER DEFAULT NEWID(),
    pipeline      NVARCHAR(128) NOT NULL,   -- 'deep_research' | 'repo_review' | 'synth' | 'extractor'
    stage         NVARCHAR(128),            -- e.g. 'llm_call' | 'extraction' | 'vault_write'
    status        NVARCHAR(32) NOT NULL,    -- 'success' | 'empty_response' | 'error' | 'truncated'
    model         NVARCHAR(128),
    input_tokens  INT,
    output_tokens INT,
    latency_ms    INT,
    error_msg     NVARCHAR(2000),
    metadata_json NVARCHAR(MAX),            -- arbitrary JSON for stage-specific context
    created_at    DATETIME2 DEFAULT GETUTCDATE()
  );
  CREATE INDEX ix_pipeline_runs_pipeline_status ON pipeline_runs(pipeline, status, created_at DESC);

Step 2 — Telemetry wrapper (src/telemetry.py):
  Write a context manager `record_stage(pipeline: str, stage: str, model: str = None)`:
    - On entry: record start time.
    - On exit (success): INSERT a 'success' row with token counts if available.
    - On exit (exception): INSERT an 'error' row with error_msg = str(exception), then re-raise.
    - Detect 'empty_response': if the LLM returns a response with output_tokens == 0 or content == '', INSERT status='empty_response' and raise a custom EmptyResponseError.
    - Detect 'truncated': if stop_reason == 'max_tokens', INSERT status='truncated' and log a warning.
  Make it usable as both a context manager and a decorator.

Step 3 — Instrument the LLM router:
  Find the multi-provider model router (introduced 2026-05-24).
  Wrap every provider call with `record_stage(pipeline=caller_pipeline, stage='llm_call', model=model_id)`.
  Pass pipeline name as a parameter (default to 'unknown' if not provided).

Step 4 — Instrument the deep-research runner:
  Wrap the top-level deep-research function with record_stage(pipeline='deep_research', stage='full_run').
  Wrap the extraction step with record_stage(pipeline='deep_research', stage='extraction').

Step 5 — Add a daily triage query (scripts/triage_report.sql):
  SELECT pipeline, status, COUNT(*) as cnt, AVG(latency_ms) as avg_ms
  FROM pipeline_runs
  WHERE created_at >= DATEADD(day, -1, GETUTCDATE())
  GROUP BY pipeline, status
  ORDER BY cnt DESC;

Edge cases:
  - The telemetry INSERT must never crash the main pipeline — wrap it in a try/except that logs to structlog but does not re-raise.
  - Token counts may not be available for all providers; use None if absent.
  - The table must be created idempotently (IF NOT EXISTS).

Verification:
  1. Run sql/telemetry.sql against the dev DB — confirm table and index created.
  2. Trigger one deep-research run manually.
  3. Run scripts/triage_report.sql — confirm at least one row appears with status='success'.
  4. Simulate an empty response (mock the LLM to return '') — confirm status='empty_response' row is inserted and EmptyResponseError is raised.
```
