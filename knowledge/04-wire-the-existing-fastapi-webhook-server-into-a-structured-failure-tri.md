---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-05-30T03:01:42.068502-07:00
---

# Wire the existing FastAPI webhook server into a structured failure-triage log with auto-retry

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

Commit 2026-05-16 added a FastAPI webhook server and n8n workflow, and commit 2026-05-17 fixed a crash on retried extractions (idempotent UPSERT). Vault note [4] specifically calls out that production agents fail because the retrieval/action system can't assemble what it needs before acting – and that failure triage is a first-class concern. Currently errors appear to be logged to *.log files (gitignored) with no structured retry queue. Adding a SQL-backed triage table (schema already exists in sql/) and a /retry endpoint would make failures visible and recoverable without manual intervention.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/cortex/ (find the FastAPI webhook server module added in commit 2026-05-16)
  - sql/ (read all .sql files to understand existing schema)
  - src/cortex/ (find the DB connection/pyodbc module)
  - .env.example (confirm DB connection env vars)

Task: Add a structured failure-triage table and /retry endpoint to the webhook server.

Step 1 – SQL migration
Create sql/004_failure_triage.sql:
  CREATE TABLE IF NOT EXISTS cortex_failure_triage (
      id            INT IDENTITY PRIMARY KEY,
      created_at    DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(),
      workflow      NVARCHAR(100)  NOT NULL,  -- e.g. 'extractor', 'deep_research', 'repo_review'
      source_url    NVARCHAR(2000) NULL,
      error_type    NVARCHAR(200)  NOT NULL,
      error_detail  NVARCHAR(MAX)  NULL,
      retry_count   INT            DEFAULT 0,
      resolved_at   DATETIMEOFFSET NULL,
      resolved_by   NVARCHAR(100)  NULL
  );
  CREATE INDEX IF NOT EXISTS ix_triage_resolved ON cortex_failure_triage(resolved_at) WHERE resolved_at IS NULL;

Note: SQL Server syntax – use IF NOT EXISTS equivalent (wrap in IF NOT EXISTS check or use CREATE TABLE with a guard).

Step 2 – DB helper
In the existing DB module, add:
  def record_failure(workflow: str, error_type: str, source_url: str | None = None, error_detail: str | None = None) -> int  # returns new row id
  def resolve_failure(failure_id: int, resolved_by: str) -> None
  def get_open_failures(limit: int = 50) -> list[dict]  # returns rows where resolved_at IS NULL

Step 3 – Webhook endpoints
In the FastAPI app, add:
  POST /failures  – body: {workflow, error_type, source_url?, error_detail?} – calls record_failure, returns {id}
  GET  /failures  – query param: limit=50 – calls get_open_failures
  POST /failures/{id}/retry – calls the appropriate workflow function based on 'workflow' field, then calls resolve_failure on success

For /failures/{id}/retry, implement a simple dispatch dict:
  RETRY_HANDLERS = {'extractor': retry_extraction, 'deep_research': retry_deep_research}
If no handler registered, return 422.

Step 4 – Instrument existing workflows
In the extractor and deep-research modules, wrap the main execution block in try/except and call record_failure() in the except branch (import the DB helper). Don't let the record_failure call itself crash the workflow (wrap in a nested try/except that just logs).

Edge cases:
  - DB unavailable when recording failure: log to structlog only, don't raise.
  - retry_count overflow: cap at 10, return 429 if exceeded.
  - Concurrent retries of same failure: use optimistic locking (check resolved_at IS NULL before updating).

Verification:
  1. Run sql/004_failure_triage.sql against the dev DB; confirm table created.
  2. POST /failures with a test payload; confirm row appears in DB.
  3. GET /failures; confirm the row is returned.
  4. Trigger a deliberate extraction failure (pass an invalid URL); confirm a row is auto-inserted.
  5. POST /failures/{id}/retry; confirm resolved_at is set on success.
```
