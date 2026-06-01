---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: S (<1 day)
generated_at: 2026-06-01T03:01:55.850017-07:00
---

# Enforce a token-budget guard on deep-research prompts to prevent runaway API spend

**Impact:** high  ·  **Effort:** S (<1 day)

## Rationale

The 2026-05-17 commit added hourly GitHub-trending scanner + Sonnet swap for auto-DR, and 2026-05-16 added server-side embeddings + auto-Deep-Research. Vault note [7] (DeepSeek Reasonix caching trap) specifically documents how low-cost agents that skip cache-hit accounting quietly accumulate large bills at scale — the 99.82% cache hit rate in controlled demos evaporates under real workloads. Cortex now runs deep research automatically on trending topics hourly with no visible token-budget cap in the commit history. Adding a per-run token estimator (input tokens = prompt length / 4) with a hard ceiling and a daily spend tracker in SQL would prevent runaway costs.

## Cited evidence

- Topics/why-deepseek-reasonix-deepseek-native-coding-agent-with-high.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find deep_research runner and any Anthropic client wrapper — search for `anthropic.Anthropic` or `client.messages.create`)
  - config/  (any model config or limits config)
  - sql/  (existing schema)
  - .env.example  (check for any existing budget env vars)

Task: Add a token-budget guard and daily spend tracker to the deep-research pipeline.

1. Add to .env.example (and document in CLAUDE.md):
   DR_MAX_INPUT_TOKENS_PER_RUN=80000   # hard cap per single DR invocation
   DR_MAX_DAILY_TOKENS=500000          # daily ceiling across all DR runs
   DR_COST_PER_1K_INPUT=0.003          # USD, update per model
   DR_COST_PER_1K_OUTPUT=0.015

2. Create src/cortex/budget/token_guard.py:
   - `estimate_tokens(text: str) -> int`: returns len(text) // 4 (conservative estimate).
   - `check_run_budget(prompt: str) -> None`: raises BudgetExceededError if estimate_tokens(prompt) > DR_MAX_INPUT_TOKENS_PER_RUN.
   - `record_usage(input_tokens: int, output_tokens: int, model: str) -> None`: writes a row to a new SQL table `token_usage` (see step 3).
   - `check_daily_budget() -> None`: queries token_usage for today's total input tokens; raises BudgetExceededError if > DR_MAX_DAILY_TOKENS.

3. Create sql/add_token_usage.sql:
   CREATE TABLE IF NOT EXISTS token_usage (
       id             INT IDENTITY PRIMARY KEY,
       run_at         DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
       model          NVARCHAR(128),
       input_tokens   INT NOT NULL,
       output_tokens  INT NOT NULL,
       estimated_cost_usd DECIMAL(10,6),
       pipeline       NVARCHAR(128)   -- 'deep_research', 'repo_review', etc.
   );

4. In the deep-research runner, before calling the Anthropic API:
   a. Call check_daily_budget() — if exceeded, log CRITICAL and skip the run entirely.
   b. Call check_run_budget(assembled_prompt) — if exceeded, truncate the prompt to fit and log WARNING.
   c. After the API call, read `response.usage.input_tokens` and `response.usage.output_tokens` from the Anthropic response object and call record_usage().

5. Add a structlog summary line after each DR run: 'token_usage input={n} output={m} est_cost_usd={x:.4f} daily_total_input={d}'.

6. Add CLI command `cortex-spend-report` that queries token_usage for the last 7 days and prints a table: date | pipeline | input_tokens | output_tokens | est_cost_usd.

Edge cases:
  - If the Anthropic response does not include usage (older SDK versions), fall back to estimate_tokens on both prompt and response text.
  - BudgetExceededError must NOT crash the scheduler — catch it at the scheduler level and log CRITICAL, then continue with next scheduled task.
  - Daily budget resets at midnight America/Los_Angeles (consistent with the tz commit 2026-05-16).

Verification:
  - Set DR_MAX_INPUT_TOKENS_PER_RUN=100 in .env, run a DR job, confirm it logs a WARNING about truncation.
  - Set DR_MAX_DAILY_TOKENS=1 in .env, run two DR jobs, confirm the second is skipped with CRITICAL log.
  - Run `cortex-spend-report` and confirm rows appear in the output.
```
