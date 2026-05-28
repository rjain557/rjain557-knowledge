---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-28T03:02:17.091238-07:00
---

# Replace ad-hoc per-extractor error handling with a unified dead-letter queue

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

The commit history shows multiple fix commits targeting individual extractors (fix(extractor): block email-signature URLs, fix(db): decode NVARCHAR as UTF-16LE, fix(db): make record_link idempotent). This pattern — patching one extractor at a time after silent failures — indicates there is no centralized failure surface. Vault note 'Persistent-Memory AI Brains' (Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md) specifically calls out that production memory layers require reliable ingestion pipelines with observable failure modes. A dead-letter table in the existing SQL Server DB (already used for links/records) would capture failed source rows with error type, traceback, and retry count, making failures visible and retryable without code changes.

## Cited evidence

- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - sql/ (read ALL .sql files to understand current schema)
  - src/cortex/db.py (or equivalent database module — find it with `grep -r 'pyodbc' src/ -l`)
  - src/cortex/extractors/ (scan all extractor files)
  - .env.example (confirm DB connection env var names)

Task: Add a dead-letter queue for failed extractions.

1. In `sql/`, create `004_dead_letter.sql`:
```sql
CREATE TABLE IF NOT EXISTS cortex.dead_letter (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    source_url    NVARCHAR(2048)  NOT NULL,
    extractor     NVARCHAR(128)   NOT NULL,
    error_type    NVARCHAR(256)   NOT NULL,
    error_detail  NVARCHAR(MAX),
    retry_count   INT             NOT NULL DEFAULT 0,
    last_attempt  DATETIMEOFFSET  NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    resolved_at   DATETIMEOFFSET  NULL,
    CONSTRAINT uq_dead_letter_url_extractor UNIQUE (source_url, extractor)
);
```
(Adjust schema prefix to match existing tables found in sql/ directory.)

2. In the DB module, add two functions:
```python
def record_dead_letter(url: str, extractor: str, exc: Exception) -> None:
    """Upsert a failure record; increment retry_count on conflict."""
    # Use MERGE or INSERT ... ON CONFLICT pattern matching existing db style
    ...

def resolve_dead_letter(url: str, extractor: str) -> None:
    """Mark a previously-failed record as resolved."""
    ...
```

3. In each extractor's top-level try/except (find the common base class or the dispatch loop in `src/cortex/extractors/`), add:
```python
except Exception as exc:
    log.error("extraction_failed", url=url, extractor=extractor_name, exc_info=True)
    record_dead_letter(url, extractor_name, exc)
    raise  # or continue, depending on existing flow
```
And on success, call `resolve_dead_letter(url, extractor_name)` to clear any prior failure.

4. Add a `scripts/show_dead_letters.py` script that queries the table and prints a summary table (url, extractor, retry_count, error_type, last_attempt) sorted by retry_count DESC.

Edge cases:
  - The UPSERT must be idempotent (same URL + extractor = update, not insert) — mirror the pattern already used in `record_link`.
  - `error_detail` should be `traceback.format_exc()[:4000]` to stay within NVARCHAR(MAX) practical limits and avoid log spam.
  - Do NOT swallow exceptions — dead-letter recording is a side effect, not a replacement for the existing error propagation.

Verification:
  - Run `sql/004_dead_letter.sql` against the dev DB.
  - Manually trigger a known-bad URL through the extractor pipeline and confirm a row appears in `cortex.dead_letter`.
  - Run `python scripts/show_dead_letters.py` and confirm it prints the row.
```
