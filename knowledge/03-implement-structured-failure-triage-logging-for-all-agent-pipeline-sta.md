---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-29T03:02:24.196603-07:00
---

# Implement structured failure triage logging for all agent pipeline stages

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note 'Your AI agent is rediscovering 85% of its context every run' includes a Contract Spec and Failure Triage section that states agents without structured failure logs force operators to re-diagnose the same failure modes repeatedly — exactly the rediscovery problem at the ops layer. The repo's .gitignore excludes *.log and logs/ entirely, and the commit history shows multiple ad-hoc fix commits (fix(db), fix(extractor), fix(poll)) that suggest failures are being discovered reactively. Adding a structured triage log (JSON-lines, one record per pipeline stage per run) would make failure patterns machine-readable and enable the Cortex self-improvement loop to auto-generate fix prompts from real error data.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (read all pipeline orchestration modules — look for the main poll/ingest loop, the deep-research runner, the repo-review runner, and the synthesis runner)
  - CLAUDE.md
  - pyproject.toml (note: structlog>=24.1 is already a dependency)
  - .gitignore (note that logs/ is excluded — we will write to a DB table instead, not a file)

Task: Add a structured pipeline triage log that writes one JSON-lines record per stage per run to a new SQL Server table, and expose a query helper so the self-improvement loop can read recent failures.

Step 1 — DB migration:
Create sql/005_pipeline_triage.sql:
  CREATE TABLE pipeline_triage (
    triage_id       BIGINT IDENTITY PRIMARY KEY,
    run_id          NVARCHAR(36)   NOT NULL,   -- UUID per top-level pipeline invocation
    pipeline        NVARCHAR(100)  NOT NULL,   -- 'ingest', 'deep_research', 'repo_review', 'synthesis', 'lint'
    stage           NVARCHAR(100)  NOT NULL,   -- e.g. 'extract', 'embed', 'llm_call', 'vault_write'
    status          NVARCHAR(20)   NOT NULL,   -- 'ok' | 'warn' | 'error' | 'skip'
    error_type      NVARCHAR(200)  NULL,       -- exception class name
    error_msg       NVARCHAR(2000) NULL,
    source_url      NVARCHAR(1000) NULL,
    duration_ms     INT            NULL,
    recorded_at     DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()
  );
  CREATE INDEX ix_triage_pipeline_status ON pipeline_triage(pipeline, status, recorded_at DESC);

Step 2 — Python triage module:
Create src/cortex/triage.py with:
  - `class TriageLogger` that accepts a db connection and a pipeline name
  - `def log_stage(self, run_id, stage, status, error=None, source_url=None, duration_ms=None)` — inserts one row; swallows its own exceptions (never crash the pipeline)
  - `def get_recent_failures(conn, pipeline=None, hours=24, limit=50) -> list[dict]` — SELECT from pipeline_triage WHERE status IN ('error','warn') AND recorded_at > DATEADD(hour,-hours,SYSDATETIMEOFFSET())
  - `def generate_run_id() -> str` — returns str(uuid.uuid4())

Step 3 — Instrument existing pipelines:
For each of the following pipeline entry points (find them in src/):
  - ingest/poll loop
  - deep_research runner
  - repo_review runner  
  - synthesis runner
Wrap each major stage in a try/except that calls triage_logger.log_stage() with status='ok' on success and status='error' + error_type + error_msg on exception, then re-raises. Use time.perf_counter() to capture duration_ms.

Step 4 — Wire into self-improvement loop:
In the existing repo-review / self-improvement scheduler job, after the vault-review step, add a call to `get_recent_failures(conn, hours=24)` and include the top 10 failures as a JSON block in the context passed to the improvement-prompt generator. This gives the LLM real error data to reason about.

Edge cases:
  - error_msg must be truncated to 2000 chars before insert (use [:2000])
  - run_id must be generated once at the top of each pipeline invocation and threaded through all stages (do not generate a new UUID per stage)
  - TriageLogger.log_stage must never raise — wrap the INSERT in try/except Exception and log to structlog at warning level if the DB write itself fails
  - Unicode in error messages: use NVARCHAR and ensure pyodbc connection has unicode enabled (already fixed in commit 8c12bef)

Verification:
  - Run sql/005_pipeline_triage.sql against local DB, confirm table exists
  - Trigger one ingest run manually, then: SELECT pipeline, stage, status, error_type FROM pipeline_triage ORDER BY recorded_at DESC — confirm rows appear
  - Introduce a deliberate ValueError in one stage, run again, confirm status='error' row with correct error_type
  - Run pytest tests/ -k triage after adding tests/test_triage.py with: test_log_stage_ok, test_log_stage_error_truncates_long_message, test_get_recent_failures_filters_by_hours
```
