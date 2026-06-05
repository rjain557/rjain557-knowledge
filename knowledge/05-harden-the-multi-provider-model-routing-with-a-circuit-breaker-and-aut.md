---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-06-05T03:01:49.857565-07:00
---

# Harden the multi-provider model routing with a circuit-breaker and automatic fallback logging

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

The multi-provider model routing commit (2026-05-24) introduced complexity across providers, but the commit message gives no indication of fallback behavior when a provider is rate-limited or unavailable. Vault note [3] on agent architecture specifically calls out that production agents fail not because retrieval is wrong but because the orchestration layer lacks resilience contracts. With daily automated commits depending on this routing layer, a silent provider failure would cause the entire daily refresh to produce empty or partial output with no alerting.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context to read first:
1. src/ — find the multi-provider model routing module added in commit 4e0a862 (search for files modified around 2026-05-24 or containing 'provider', 'router', 'model_routing')
2. CLAUDE.md — understand which models are used for which pipeline stages
3. .env.example — see which provider API keys are declared

Task: Add a circuit-breaker with automatic provider fallback and structured failure logging to the model router.

Steps:
1. In the model routing module, create a `ProviderCircuitBreaker` class with:
   - `failure_threshold: int = 3` — number of consecutive failures before opening the circuit
   - `recovery_timeout: int = 300` — seconds before attempting to close (half-open state)
   - State stored in a module-level dict keyed by provider name (in-process, no external state needed)
   - Methods: `record_success(provider)`, `record_failure(provider)`, `is_available(provider) -> bool`
2. Wrap every provider API call in the router with try/except that:
   a. On `anthropic.RateLimitError` or `anthropic.APIStatusError` (status >= 500): calls `record_failure(provider)`, logs `{"event": "provider_failure", "provider": ..., "error": ..., "circuit_state": ...}` via structlog
   b. On success: calls `record_success(provider)`
3. In the routing selection logic, before choosing a provider, call `is_available(provider)` and skip unavailable providers. If ALL providers for a given model tier are unavailable, raise a `NoAvailableProviderError` with a clear message listing which providers are in open-circuit state and when they will retry.
4. Add a `scripts/check_provider_health.py` script that instantiates the router, makes a minimal test call (1-token completion) to each configured provider, and prints a health table: provider | status | latency_ms. Exit code 1 if any provider fails.
5. Log every fallback event (primary provider skipped, secondary used) to `logs/provider_fallback.log` in JSON-lines format with fields: timestamp, intended_provider, actual_provider, reason.

Edge cases:
- The circuit breaker state is in-process only; it resets on process restart (this is intentional for a single-process scheduler)
- `NoAvailableProviderError` must NOT be silently swallowed anywhere — let it propagate to the top-level scheduler so the daily run is marked failed rather than silently producing empty output
- The health check script must work with only the env vars present (skip providers whose keys are not set)

Verification:
1. Temporarily set a provider's API key to an invalid value, run one pipeline stage, and confirm the fallback log entry appears
2. Set the `failure_threshold` to 1 in a test, call `record_failure` once, and assert `is_available` returns False
3. Run `python scripts/check_provider_health.py` with valid keys and confirm exit code 0 and a printed table
4. Run `ruff check src/` and fix any new lint issues
```
