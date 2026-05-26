---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-26T03:02:07.112020-07:00
---

# Replace ad-hoc Claude API calls with a structured retry + cost-tracking wrapper

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

The commit log shows rapid feature additions (deep-research, auto-DR, Haiku verifier, Sonnet swap) all landing in the same week, each likely adding its own direct anthropic client calls. Vault note 'Claude Code Maturity Levels' (Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md) identifies that Level 3+ systems require explicit cost-awareness and retry discipline to avoid runaway spend. Without a central wrapper, there is no single place to enforce model-selection policy, log token usage to SQL, or add exponential backoff when the API rate-limits.

## Cited evidence

- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
  - src/  (find every file that imports anthropic or instantiates Anthropic() / AsyncAnthropic())
  - sql/  (understand the existing schema so you can add a token_usage table)
  - pyproject.toml

Task: Introduce a single LLMClient wrapper that all callers use, with retry logic, cost logging, and model-selection policy.

Step 1 — Create src/cortex/llm/client.py
  class LLMClient:
    def __init__(self, default_model: str = 'claude-sonnet-4-5', max_retries: int = 4)
    async def complete(self, messages: list[dict], *, model: str | None = None, system: str = '', max_tokens: int = 4096, **kwargs) -> anthropic.types.Message

  Inside complete():
    - Use tenacity (add to pyproject.toml deps) for exponential backoff: wait_exponential(min=2, max=60), retry on anthropic.RateLimitError and anthropic.APIStatusError with status 529.
    - After a successful response, call _log_usage(model, response.usage) in a fire-and-forget asyncio.create_task.

  _log_usage() should INSERT into a token_usage table (see Step 2) via the existing pyodbc connection pool.

Step 2 — Add migration sql/004_token_usage.sql
  CREATE TABLE token_usage (
    id          BIGINT IDENTITY PRIMARY KEY,
    ts          DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(),
    model       NVARCHAR(80)   NOT NULL,
    caller      NVARCHAR(200)  NOT NULL,   -- __name__ of calling module
    input_tok   INT            NOT NULL,
    output_tok  INT            NOT NULL,
    cache_read  INT            NOT NULL DEFAULT 0,
    cache_write INT            NOT NULL DEFAULT 0
  );

Step 3 — Model-selection policy
  Add a ModelPolicy enum in the same file:
    FAST = 'claude-haiku-4-5'      # verifier, lint, cheap classification
    BALANCED = 'claude-sonnet-4-5' # default
    DEEP = 'claude-opus-4-5'       # deep-research synthesis only
  LLMClient.complete() should accept policy: ModelPolicy | None = None; if provided it overrides the model kwarg.

Step 4 — Migrate existing callers
  Find every direct anthropic.Anthropic() / AsyncAnthropic() instantiation in src/ and replace with a shared singleton: from cortex.llm.client import get_client; client = get_client().
  get_client() returns a module-level LLMClient instance (lazy-init, thread-safe via asyncio.Lock).

Edge cases:
  - Sync callers (if any) should use asyncio.run(client.complete(...)) or a sync shim complete_sync().
  - The _log_usage fire-and-forget must not swallow exceptions silently — log them via structlog at WARNING level.
  - If the SQL connection is unavailable, _log_usage should fail gracefully (log + skip) so a DB outage never blocks an LLM call.

Verification:
  1. Run existing tests: `uv run pytest` — no regressions.
  2. Trigger one deep-research run; confirm a row appears in token_usage.
  3. Temporarily set max_retries=1 and mock a RateLimitError; confirm tenacity retries and logs correctly.
```
