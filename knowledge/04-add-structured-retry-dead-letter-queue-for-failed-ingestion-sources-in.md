---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-31T03:02:02.165089-07:00
---

# Add structured retry + dead-letter queue for failed ingestion sources instead of silent drops

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

The commit history shows multiple fixes for ingestion reliability (2026-05-17: make record_link idempotent; 2026-05-16: block email-signature URLs; 2026-05-16: fix mailbox cleanup on already-processed emails), indicating the ingestion pipeline has recurring failure modes. Vault note 'Your AI agent is rediscovering 85% of its context every run' warns that production agent failures stem from the retrieval system not being able to assemble what the agent needs — which is compounded when sources silently fail to ingest and leave gaps in the knowledge base. A dead-letter table in the existing SQL Server DB with retry_count, last_error, and next_retry_at columns would make failures visible and automatically retried with exponential backoff, preventing silent knowledge gaps.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
1. sql/ — read all existing schema files to understand current tables (sources, links, etc.)
2. src/ — find the extractor/ingestion pipeline modules; look for try/except blocks that currently log-and-continue on failure
3. pyproject.toml — confirm pyodbc and structlog are available
4. CLAUDE.md — understand the ingestion flow end-to-end

Task: Add a dead-letter queue (DLQ) table and retry logic to the ingestion pipeline.

Step 1 — Add sql/dlq_schema.sql:
```sql
CREATE TABLE IF NOT EXISTS ingestion_dlq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- or IDENTITY(1,1) for SQL Server
    source_url NVARCHAR(2048) NOT NULL,
    source_type NVARCHAR(64) NOT NULL,  -- 'email', 'rss', 'github', 'youtube', 'pdf'
    raw_payload NVARCHAR(MAX),           -- JSON blob of original input
    error_class NVARCHAR(256),
    error_message NVARCHAR(MAX),
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_retry_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT GETDATE(),
    resolved_at DATETIME,
    resolution NVARCHAR(64)  -- 'success', 'abandoned', 'manual'
);
CREATE INDEX idx_dlq_next_retry ON ingestion_dlq(next_retry_at) WHERE resolved_at IS NULL;
```
Adapt syntax for SQLite vs SQL Server based on what sql/ already uses.

Step 2 — Write src/cortex/dlq.py:
```python
def enqueue_failure(db_conn, source_url: str, source_type: str, raw_payload: dict, exc: Exception) -> None:
    """Insert or increment retry count for a failed source."""
    # Check if URL already in DLQ
    # If yes: increment retry_count, set next_retry_at = NOW + 2^retry_count hours (exponential backoff, max 48h)
    # If no: INSERT new row with next_retry_at = NOW + 1 hour
    # If retry_count >= max_retries: set resolution='abandoned', resolved_at=NOW, log warning

def get_due_retries(db_conn) -> list[dict]:
    """Return all DLQ rows where next_retry_at <= NOW and resolved_at IS NULL."""

def mark_resolved(db_conn, dlq_id: int, resolution: str = 'success') -> None:
    """Mark a DLQ entry as resolved after successful retry."""
```

Step 3 — Wire into the ingestion pipeline:
- Find every `except Exception` block in the extractor modules that currently logs and continues
- Replace with: log the error AND call `dlq.enqueue_failure(conn, url, source_type, payload, exc)`
- At the START of each ingestion run (before processing new sources), call `dlq.get_due_retries()` and attempt to re-process each returned row using the appropriate extractor
- On retry success: call `dlq.mark_resolved()`
- On retry failure: `dlq.enqueue_failure()` will automatically increment the counter

Step 4 — Add a daily DLQ report to the existing structlog output:
- After the retry pass, log: `{"event": "dlq_summary", "pending": N, "abandoned_today": M, "resolved_today": K}`
- If abandoned_today > 0, also write a vault note to knowledge/ops/dlq-report-YYYY-MM-DD.md listing the abandoned URLs so a human can review

Edge cases:
- The same URL may appear in multiple source types (e.g. a GitHub URL ingested as both RSS and direct) — use (source_url, source_type) as the logical unique key
- Exponential backoff must cap at 48 hours to prevent indefinite deferral
- The retry pass must run BEFORE new source ingestion so the pipeline processes old failures first
- If the DLQ table doesn't exist yet (first run after migration), create it automatically in dlq.py using the schema above
- Abandoned entries (retry_count >= max_retries) must never be retried automatically — only manual resolution resets them

Verification:
1. Manually insert a row into ingestion_dlq with next_retry_at in the past, run the pipeline, confirm it attempts retry and logs the result
2. Insert a row with retry_count=3 (at max), run the pipeline, confirm it is marked 'abandoned' and a vault report is written
3. Trigger a real extraction failure (e.g. pass an invalid URL to the extractor), confirm it lands in the DLQ rather than being silently dropped
4. Query `SELECT COUNT(*) FROM ingestion_dlq WHERE resolved_at IS NULL;` before and after a run that includes successful retries — count should decrease
```
