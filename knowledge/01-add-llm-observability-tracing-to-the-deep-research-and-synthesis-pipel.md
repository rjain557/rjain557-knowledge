---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-04T03:01:21.721962-07:00
---

# Add LLM observability tracing to the deep-research and synthesis pipelines

**Impact:** high  ·  **Effort:** M

## Rationale

The repo runs multi-step LLM pipelines (deep-research, nightly synthesis, repo-review) with no tracing or scoring layer. Vault note [7] (Langfuse Observability) documents exactly how to wire open-source Langfuse tracing into LLM pipelines to capture token costs, latency, and output quality scores per run. Without this, regressions in synthesis quality or runaway token spend are invisible until they show up as bad vault notes or a surprise bill.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the deep-research runner and synthesis/lint scripts)
  - pyproject.toml  (current deps)
  - CLAUDE.md
  - .env.example

Task: Instrument the Cortex LLM pipelines with Langfuse tracing.

Steps:
1. Add `langfuse>=2.0` to pyproject.toml [project.dependencies].
2. Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST to .env.example with placeholder values.
3. Create src/cortex/observability.py that:
   a. Reads the three env vars via pydantic-settings (reuse existing Settings pattern if one exists).
   b. Exposes a get_langfuse() singleton and a @trace_llm(name, metadata) decorator.
   c. The decorator wraps any function that calls anthropic client, captures: input tokens, output tokens, model name, latency_ms, and an optional quality_score kwarg.
   d. If LANGFUSE_PUBLIC_KEY is absent, the decorator is a no-op so local dev is unaffected.
4. Apply @trace_llm to:
   a. The deep-research LLM call site(s).
   b. The nightly synthesis step.
   c. The repo-review prompt submission.
5. In each call site, pass metadata={'pipeline': '<name>', 'run_date': today_iso}.
6. Add a pytest test in tests/ that mocks the Langfuse client and asserts the decorator fires with correct metadata keys.

Edge cases:
  - If the anthropic call raises, the decorator must still flush the trace with error=True before re-raising.
  - Do not import langfuse at module level in files that run in environments where it may not be installed; guard with try/except ImportError.

Verify:
  - `uv run pytest tests/test_observability.py -v` passes.
  - Run one deep-research job locally and confirm a trace appears in the Langfuse UI (or stdout if host=localhost).
```
