---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-06-01T03:01:55.850017-07:00
---

# Add structured retry + dead-letter queue for failed extractor runs instead of silent drops

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

The commit history shows multiple extractor fixes (2026-05-16: block email-signature URLs; 2026-05-17: make record_link idempotent; 2026-05-24: fix NVARCHAR UTF-16LE decode bug). These are all reactive patches to silent failures. Vault note [3] ('agents fail because the retrieval system can't assemble what the agent needs') identifies missing or corrupted source material as a primary failure mode. Currently failed extractions appear to be dropped (the idempotent UPSERT fix prevents crashes but doesn't retry). A dead-letter table in SQL Server + an exponential-backoff retry scheduler would surface failures and allow automatic recovery.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - sql/  (all .sql schema files)
  - src/  (find extractor runner — likely src/cortex/extractors/ or src/cortex/poll.py)
  - src/  (find the DB layer — search for pyodbc usage)
  - CLAUDE.md

Task: Implement a dead-letter queue and retry mechanism for failed extractions.

1. Add a new SQL table. Create sql/add_dead_letter_queue.sql:
   CREATE TABLE IF NOT EXISTS extraction_dlq (
       id            INT IDENTITY PRIMARY KEY,
       source_url    NVARCHAR(2048) NOT NULL,
       extractor     NVARCHAR(128)  NOT NULL,
       error_message NVARCHAR(MAX),
       attempt_count INT            NOT NULL DEFAULT 1,
       last_attempt  DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
       next_retry    DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
       resolved      BIT            NOT NULL DEFAULT 0
   );
   Run this migration in the DB init path.

2. In the extractor runner, wrap each extractor call in a try/except:
   - On success: if a DLQ row exists for this URL, mark it resolved=1.
   - On failure (any exception):
     a. Log via structlog at ERROR with exc_info=True.
     b. UPSERT into extraction_dlq: increment attempt_count, set error_message, set next_retry = SYSDATETIMEOFFSET() + POWER(2, attempt_count) minutes (exponential backoff, cap at 1440 minutes / 24h).
     c. Do NOT re-raise — continue processing other items.

3. Add a retry worker function `retry_dlq()` in the extractor runner:
   - Query: SELECT top 50 * FROM extraction_dlq WHERE resolved=0 AND next_retry <= SYSDATETIMEOFFSET() ORDER BY next_retry.
   - For each row, re-invoke the appropriate extractor by name.
   - Call this function at the start of each hourly poll run (before processing new items).

4. Add a structlog summary at the end of each poll run:
   - Total DLQ rows unresolved, oldest unresolved item age, items retried this run.

5. Add a CLI command `cortex-dlq-report` that prints the current DLQ state as a table to stdout.

Edge cases:
  - If attempt_count > 10, set next_retry far in the future (30 days) and log a CRITICAL alert so a human reviews it.
  - The extractor name stored in DLQ must match the class/function name exactly so retry dispatch works.
  - NVARCHAR fields: use the UTF-16LE encoding fix already in the codebase (see the 2026-05-24 commit) when reading error_message back.

Verification:
  - Manually insert a row into extraction_dlq with a bad URL and attempt_count=1.
  - Run the poll script and confirm retry_dlq() picks it up, increments attempt_count, and updates next_retry.
  - Confirm `cortex-dlq-report` shows the row.
  - Simulate a successful retry and confirm resolved=1.
```
