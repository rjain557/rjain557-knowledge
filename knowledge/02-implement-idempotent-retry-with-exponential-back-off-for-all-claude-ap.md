---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: S (<1 day)
generated_at: 2026-05-25T03:01:49.346493-07:00
---

# Implement idempotent retry with exponential back-off for all Claude API calls

**Impact:** high  ·  **Effort:** S (<1 day)

## Rationale

The repo makes multiple Claude API calls per pipeline stage (deep-research, synth, lint, repo-review, Haiku verifier) with no visible retry logic in the commit history. The vault note on Claude Code maturity levels (Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md) explicitly calls out robust error-handling and retry as a prerequisite for moving from Level 2 to Level 3 autonomous operation. A transient 529/overload from Anthropic currently silently drops a deep-research run or vault write, causing data loss that is hard to detect.

## Cited evidence

- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

First, read:
  - src/cortex/  (list all .py files, then read any file whose name contains 'claude', 'llm', 'ai', 'client', 'research', or 'synth')
  - pyproject.toml  (check if tenacity is already a dependency)

Task: Add a centralized, reusable retry wrapper for all Anthropic SDK calls.

Steps:
1. Add 'tenacity>=8.3' to the dependencies list in pyproject.toml.
2. Create src/cortex/llm_client.py (or add to an existing llm/client file if one exists) with:

   from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
   import anthropic, logging

   logger = logging.getLogger(__name__)

   def _is_retryable(exc: BaseException) -> bool:
       """Retry on 429, 529, and transient network errors only."""
       if isinstance(exc, anthropic.RateLimitError): return True
       if isinstance(exc, anthropic.APIStatusError) and exc.status_code in (529, 503, 502): return True
       if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)): return True
       return False

   @retry(
       retry=retry_if_exception(_is_retryable),
       wait=wait_exponential(multiplier=2, min=4, max=120),
       stop=stop_after_attempt(5),
       before_sleep=lambda rs: logger.warning("Anthropic retry %s: %s", rs.attempt_number, rs.outcome.exception()),
   )
   def claude_messages(client: anthropic.Anthropic, **kwargs):
       """Drop-in wrapper around client.messages.create with retry."""
       return client.messages.create(**kwargs)

3. Find every call site that calls client.messages.create (or equivalent) across src/cortex/ and replace with claude_messages(client, ...) — keep all existing kwargs unchanged.
4. Do NOT retry on anthropic.AuthenticationError or anthropic.BadRequestError (these are permanent failures).

Edge cases:
- If a call site uses streaming (stream=True), wrap it separately with the same decorator but note in a TODO comment that streaming retry requires re-consuming the stream.
- Async call sites (if any use await client.messages.create): create a parallel async_claude_messages using tenacity's AsyncRetrying.

Verification:
1. uv run ruff check src/cortex/  should pass with no new errors.
2. Add tests/test_llm_client.py: mock anthropic.Anthropic, make it raise RateLimitError twice then succeed, assert claude_messages returns the success result and that the mock was called 3 times.
3. Run: uv run pytest tests/test_llm_client.py -v
```
