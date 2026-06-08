---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-08T03:01:24.415428-07:00
---

# Add LLM observability tracing to the deep-research and extraction pipelines

**Impact:** high  ·  **Effort:** M

## Rationale

The repo runs multi-step LLM pipelines (extraction → synthesis → repo-review) with no tracing layer. The Langfuse vault note describes exactly this gap: without trace IDs, prompt versioning, and per-step scoring, debugging regressions in the daily knowledge refresh commits is guesswork. Adding Langfuse (open-source, self-hostable) would give span-level visibility into which extractor or synthesis prompt is degrading quality, directly enabling the self-improvement loop the system is designed for.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - pyproject.toml  (see current deps)
  - src/  (scan for LLM call sites — look for anthropic.Anthropic() or client.messages.create calls)
  - CLAUDE.md
  - config/  (any settings files)

Task: Instrument the two highest-value LLM call sites with Langfuse tracing.

Steps:
1. Add `langfuse>=2.0` to pyproject.toml dependencies.
2. Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST to .env.example (with placeholder values and a comment pointing to https://cloud.langfuse.com or self-hosted).
3. Create src/cortex/observability.py that:
   - Initialises a Langfuse client from env vars (fail-open: if keys are absent, return a no-op context manager so the pipeline still runs).
   - Exposes a `trace_llm_call(name: str, input: dict, model: str)` context manager that creates a Langfuse generation span, captures output and token counts on exit, and logs any exception as an error event.
4. Wrap the deep-research synthesis LLM call and the repo-review LLM call with `trace_llm_call`. Pass the prompt text as `input`, the model name (e.g. claude-sonnet-4-5) as `model`, and the returned text as output inside the context manager.
5. In each wrapped call site, add a `session_id` equal to today's ISO date so all spans from one daily run are grouped.

Edge cases:
  - If LANGFUSE_* env vars are missing, the pipeline must not crash — use the fail-open no-op wrapper.
  - Do not log raw API keys or secret env values into spans.
  - Async call sites: use Langfuse's async client or wrap with asyncio.run_in_executor.

Verification:
  - `uv run python -c "from src.cortex.observability import trace_llm_call; print('ok')"` should print ok.
  - Run one extraction manually and confirm a trace appears in the Langfuse UI (or that no exception is raised when keys are absent).
  - `uv run ruff check src/cortex/observability.py` should pass clean.
```
