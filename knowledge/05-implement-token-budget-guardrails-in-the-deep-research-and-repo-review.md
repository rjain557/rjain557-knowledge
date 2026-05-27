---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S
generated_at: 2026-05-27T03:02:00.297634-07:00
---

# Implement token-budget guardrails in the deep-research and repo-review agents

**Impact:** medium  ·  **Effort:** S

## Rationale

The repo has multi-provider model routing (commit 4e0a862) and runs automated deep-research + repo-review on a schedule, meaning runaway context windows directly translate to cost spikes. Vault note 'Zero-Cost Agentic Research Pipelines' (Topics/free-research-beast-no-api-needed.md) specifically calls out token budget management as a first-class concern in always-on agentic pipelines. Neither the pyproject.toml nor the commit history shows any max_tokens enforcement or cost-tracking instrumentation beyond what the Anthropic SDK provides by default.

## Cited evidence

- Topics/free-research-beast-no-api-needed.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the deep_research and repo_review agent entry points; find the multi-provider router from commit 4e0a862)
  - config/  (look for any model config YAML/JSON)
  - .env.example  (check for any existing token/cost config vars)

Goal: Add per-call token budget enforcement and a lightweight cost accumulator so runaway LLM calls are caught before they drain API credits.

Specific changes:
1. In the multi-provider router module, add a TokenBudget dataclass:
   @dataclass
   class TokenBudget:
       max_input_tokens: int
       max_output_tokens: int
       warn_threshold_usd: float  # log warning if estimated cost exceeds this
       hard_limit_usd: float      # raise BudgetExceededError if exceeded

2. Add a COST_PER_1K_TOKENS dict mapping model names to (input_cost, output_cost) in USD, sourced from current Anthropic/OpenAI pricing. Include at minimum: claude-3-5-sonnet, claude-3-haiku, claude-3-5-haiku, gpt-4o, gpt-4o-mini.

3. After every LLM call, read usage.input_tokens and usage.output_tokens from the response, compute estimated cost, accumulate into a run-level counter (a simple module-level dict keyed by run_id), and:
   - Log at INFO level: model, input_tokens, output_tokens, estimated_usd.
   - If cumulative run cost > warn_threshold_usd: log WARNING.
   - If cumulative run cost > hard_limit_usd: raise BudgetExceededError (define in src/cortex/exceptions.py) BEFORE the next LLM call in the same run.

4. Add config vars to .env.example:
   CORTEX_WARN_BUDGET_USD=0.50
   CORTEX_HARD_BUDGET_USD=2.00
   CORTEX_MAX_OUTPUT_TOKENS=4096
   Load these via pydantic-settings (already a dependency) in the existing settings module.

5. In the deep_research and repo_review entry points, pass the budget to the router and catch BudgetExceededError — log it and exit gracefully (write a partial result to vault rather than crashing with no output).

Edge cases:
  - Models not in COST_PER_1K_TOKENS dict: log a WARNING and skip cost tracking for that call rather than crashing.
  - Streaming responses: accumulate tokens from stream usage events if the provider surfaces them; otherwise estimate from character count as a fallback.
  - The hard limit should apply per-run, not globally, so parallel runs don't interfere.

Verification:
  1. Unit test: mock an LLM call returning usage(input_tokens=10000, output_tokens=2000) with a model priced at $0.003/$0.015 per 1k. Assert the cost accumulator reaches the warn threshold after N calls and raises BudgetExceededError after M calls.
  2. Set CORTEX_HARD_BUDGET_USD=0.001 in a test .env, run the repo_review agent against a single small repo, confirm BudgetExceededError is raised and a partial vault entry is written.
  3. Restore CORTEX_HARD_BUDGET_USD to a sane value after testing.
```
