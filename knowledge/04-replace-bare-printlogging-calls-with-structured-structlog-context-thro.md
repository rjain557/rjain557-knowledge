---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-05-24T07:12:31.038902-07:00
---

# Replace bare print/logging calls with structured structlog context throughout the pipeline

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

structlog is already declared as a core dependency in pyproject.toml but the recent commits (e.g. fix(extractor), feat(deep-research), feat(webhook)) show rapid feature addition with no evidence of consistent structured logging. Without bound context (source_id, run_id, domain, extractor), log lines from concurrent hourly runs are impossible to correlate. Vault note [10] ('Persistent-Memory AI Brains') notes that production agentic systems require observable pipelines to debug cross-agent failures — unstructured logs are the first thing that breaks incident response.

## Cited evidence

- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Files to read first:
  - src/  (full tree)
  - pyproject.toml  (confirm structlog version)
  - CLAUDE.md

Task: Establish a single structlog configuration module and migrate the three highest-traffic pipeline modules to use bound context loggers.

Steps:
1. Create src/cortex/logging_config.py:
   import structlog, logging, sys

   def configure_logging(level: str = 'INFO'):
       structlog.configure(
           processors=[
               structlog.contextvars.merge_contextvars,
               structlog.stdlib.add_log_level,
               structlog.stdlib.add_logger_name,
               structlog.processors.TimeStamper(fmt='iso', utc=False),
               structlog.processors.StackInfoRenderer(),
               structlog.processors.format_exc_info,
               structlog.processors.JSONRenderer(),
           ],
           wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
           context_class=dict,
           logger_factory=structlog.PrintLoggerFactory(sys.stdout),
       )

   def get_logger(name: str):
       return structlog.get_logger(name)

2. Call configure_logging() once at each entrypoint (webhook server startup, poll script, scheduler startup). Find entrypoints with: grep -r 'if __name__' src/ scripts/

3. Migrate these three modules (highest churn based on commits):
   a. The extractor dispatcher (feat(extractors) commit) — bind: extractor=<name>, source_id=<id>
   b. The deep-research pipeline — bind: topic=<topic>, run_id=<id>
   c. The webhook/FastAPI server — bind: event_type=<type>, message_id=<id>

   Pattern for each:
     OLD: print(f'Processing {url}')  or  logger.info('Processing %s', url)
     NEW: log = get_logger(__name__).bind(source_id=source_id, url=url)
          log.info('extraction_started')
          ...on error...
          log.exception('extraction_failed', error=str(e))

4. Do NOT change any business logic — only logging calls. Use structlog.contextvars.bind_contextvars() at the top of each request/job handler so all downstream calls in that call stack automatically inherit the context.

Edge cases:
  - Modules that currently use Python's stdlib logging: structlog.stdlib bridge is already handled by the config above; existing handlers will still work
  - Windows vs Linux: JSONRenderer writes to stdout; ensure the poll PowerShell wrapper captures stdout (it should already via pipe)
  - Don't log secrets: audit each bind() call to ensure no API keys or email content are included — use source_id/run_id references only

Verification:
  - Start the webhook server and POST a test event; confirm stdout shows a single JSON line with event_type and message_id fields
  - Trigger one extraction; confirm log lines include source_id and extractor fields
  - grep -r 'print(' src/ | grep -v test | grep -v logging_config  — should return zero results in migrated modules
  - Run pytest; confirm no test failures from the logging change
```
