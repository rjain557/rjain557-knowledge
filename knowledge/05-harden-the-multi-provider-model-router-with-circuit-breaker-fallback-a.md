---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-06T03:01:40.266571-07:00
---

# Harden the multi-provider model router with circuit-breaker fallback and cost-cap guardrails

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Commit 4e0a862 (2026-05-24) introduced multi-provider model routing but the diff description gives no indication of fallback logic or spend limits. Vault note [5] (Claude Code Maturity Levels) identifies provider-level resilience and cost governance as the distinguishing traits of Level 4-5 multi-agent deployments. Without a circuit breaker, a single provider outage will silently fail entire pipeline runs; without a cost cap, the hourly GitHub-trending scanner (added 2026-05-17) and auto-deep-research can generate unbounded API spend overnight.

## Cited evidence

- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/cortex/llm/ (all files — especially the model router added in commit 4e0a862)
  - src/cortex/scheduler.py (or wherever hourly jobs are registered)
  - .env.example
  - config/ (all YAML/TOML files)

Task: Add a circuit-breaker pattern and daily cost-cap guardrail to the multi-provider model router.

Steps:
1. In src/cortex/llm/router.py (or equivalent), implement a CircuitBreaker per provider:
   a. State machine: CLOSED -> OPEN (after N consecutive failures) -> HALF_OPEN (after cooldown_seconds) -> CLOSED.
   b. Configurable: failure_threshold=3, cooldown_seconds=300 — read from config/llm.yaml (create if absent).
   c. When a provider is OPEN, the router must skip it and try the next provider in priority order.
   d. Log state transitions at WARNING level using structlog.
2. Add a DailyCostAccumulator:
   a. Persists today's token spend per provider in a SQLite table llm_cost_log(date TEXT, provider TEXT, model TEXT, input_tokens INT, output_tokens INT) — reuse the existing DB connection pattern.
   b. Before each API call, check if today's total estimated cost (use published per-token prices stored in config/llm.yaml) exceeds DAILY_LLM_BUDGET_USD (add to .env.example, default 5.0).
   c. If over budget: log CRITICAL, skip the call, and raise a BudgetExceededError (do NOT silently swallow).
   d. The hourly GitHub-trending scanner and auto-deep-research jobs must catch BudgetExceededError and write a vault note knowledge/Meta/budget-alert-<date>.md instead of crashing the scheduler.
3. Add `python -m cortex.llm.status` CLI that prints current circuit-breaker states and today's spend vs budget.

Edge cases:
  - Clock rollover at midnight must reset the daily accumulator atomically (use date string as partition key, not a counter).
  - If the cost DB is locked (concurrent jobs), retry 3x with 100ms backoff before raising.
  - Unit tests must not make real API calls — mock the provider clients.

Verification:
  - `python -m pytest tests/llm/test_circuit_breaker.py tests/llm/test_cost_cap.py -x` — all pass.
  - Simulate a provider failure by monkey-patching the client to raise an exception 3 times; assert the circuit opens and the next provider is used.
  - Set DAILY_LLM_BUDGET_USD=0.0001 and run one deep-research job; confirm BudgetExceededError is raised and a budget-alert note is written.
  - `ruff check src/cortex/llm/` with zero errors.
```
