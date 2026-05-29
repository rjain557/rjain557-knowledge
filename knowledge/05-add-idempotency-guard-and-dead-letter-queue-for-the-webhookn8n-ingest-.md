---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-29T03:02:24.196603-07:00
---

# Add idempotency guard and dead-letter queue for the webhook/n8n ingest path

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

Commit f38ea8a added the FastAPI webhook server and commit 9ef5fa9 fixed record_link to be idempotent at the DB layer — but the webhook handler itself has no idempotency check at the HTTP layer, meaning duplicate webhook deliveries from n8n (which retries on timeout) can trigger duplicate deep-research runs and LLM spend before the DB UPSERT catches them. The vault note on persistent-memory AI brains explicitly calls out that production agent pipelines need a dead-letter mechanism for failed events to avoid silent data loss. Adding an idempotency key header check and a dead-letter table would close both gaps.

## Cited evidence

- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the FastAPI webhook server module — likely src/cortex/webhook.py or similar, introduced in commit f38ea8a)
  - sql/  (read all migration files to understand current schema)
  - CLAUDE.md

Task: Add HTTP-layer idempotency and a dead-letter queue to the webhook ingest endpoint.

Step 1 — DB migration sql/006_webhook_idempotency.sql:
  CREATE TABLE webhook_idempotency (
    idempotency_key  NVARCHAR(200) PRIMARY KEY,
    received_at      DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    status           NVARCHAR(20)   NOT NULL DEFAULT 'processing',  -- 'processing'|'ok'|'error'
    response_body    NVARCHAR(2000) NULL
  );

  CREATE TABLE webhook_dead_letter (
    dlq_id           BIGINT IDENTITY PRIMARY KEY,
    idempotency_key  NVARCHAR(200)  NULL,
    payload          NVARCHAR(MAX)  NOT NULL,
    error_type       NVARCHAR(200)  NULL,
    error_msg        NVARCHAR(2000) NULL,
    received_at      DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    retry_count      INT            NOT NULL DEFAULT 0,
    last_retry_at    DATETIMEOFFSET NULL
  );

Step 2 — Update the FastAPI webhook handler:

a) Idempotency check:
  - Require a header `X-Idempotency-Key` (string, max 200 chars). If missing, generate one as sha256(request body)[:40].
  - Before processing: attempt INSERT into webhook_idempotency(idempotency_key, status='processing'). If INSERT fails due to PK conflict, SELECT status from the existing row:
    * If status='ok': return HTTP 200 with cached response_body (already processed)
    * If status='processing': return HTTP 409 with message 'duplicate in flight'
    * If status='error': allow reprocessing (DELETE the row and re-insert)
  - After successful processing: UPDATE webhook_idempotency SET status='ok', response_body=<result> WHERE idempotency_key=<key>
  - On exception: UPDATE webhook_idempotency SET status='error' and INSERT into webhook_dead_letter

b) Dead-letter on failure:
  - Wrap the entire handler body in try/except Exception as e:
    * On exception: INSERT into webhook_dead_letter(idempotency_key, payload=await request.body(), error_type=type(e).__name__, error_msg=str(e)[:2000])
    * Return HTTP 500 with {"error": "queued to dead letter", "key": idempotency_key}
    * Do NOT re-raise (prevents n8n from retrying immediately and creating more DLQ entries)

c) Add a GET /webhook/dead-letter endpoint (protected by the same API key auth already on the server) that returns the 20 most recent DLQ entries for operator inspection.

Step 3 — Add a DLQ retry script:
Create scripts/retry_dead_letter.py:
  - Reads all webhook_dead_letter rows WHERE retry_count < 3 AND (last_retry_at IS NULL OR last_retry_at < DATEADD(hour,-1,SYSDATETIMEOFFSET()))
  - For each row: re-posts the payload to http://localhost:<WEBHOOK_PORT>/webhook/ingest with the original idempotency_key header
  - On success: DELETE from webhook_dead_letter
  - On failure: UPDATE retry_count += 1, last_retry_at = now
  - Reads WEBHOOK_PORT from .env via python-dotenv

Edge cases:
  - request.body() can only be read once in FastAPI — cache it with `body = await request.body()` at the top of the handler before any other reads
  - The idempotency table INSERT race condition: use TRY/CATCH in SQL or catch pyodbc.IntegrityError in Python
  - Payload stored in DLQ may contain PII from emails — add a comment noting this and ensure the GET /webhook/dead-letter endpoint requires auth
  - webhook_idempotency rows older than 7 days should be pruned: add a weekly APScheduler job `prune_idempotency_log` that runs DELETE FROM webhook_idempotency WHERE received_at < DATEADD(day,-7,SYSDATETIMEOFFSET())

Verification:
  - Start the webhook server locally
  - POST the same payload twice with the same X-Idempotency-Key — second call must return 200 with cached response, not trigger a second deep-research run
  - POST a payload that causes a deliberate error (e.g. malformed JSON body) — confirm a row appears in webhook_dead_letter
  - Run scripts/retry_dead_letter.py — confirm it attempts redelivery
  - Run pytest tests/ -k webhook after adding tests/test_webhook_idempotency.py
```
