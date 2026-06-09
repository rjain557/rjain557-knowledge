---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-09T03:01:24.645075-07:00
---

# Add LLM observability tracing via Langfuse to all agent pipeline calls

**Impact:** high  ·  **Effort:** M

## Rationale

The repo makes daily automated LLM calls (deep research, repo review, synthesis, lint) but has no tracing, scoring, or prompt-management layer. The Langfuse vault note (Inbox/2026-05-23) describes exactly this gap: without trace IDs, latency metrics, and per-run scores, debugging why a knowledge refresh produced low-quality output is guesswork. Adding Langfuse now, while the pipeline is still small, avoids retrofitting instrumentation across dozens of call sites later.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

Context files to read first:
  1. src/ — scan all Python files to find every place anthropic.Anthropic() or the model router is called
  2. pyproject.toml — confirm langfuse is NOT yet a dependency
  3. .env.example — note existing env-var patterns
  4. CLAUDE.md — understand pipeline entry points

Task: Instrument every LLM call in the Cortex pipeline with Langfuse tracing.

Steps:
  1. Add `langfuse>=2.0` to pyproject.toml [project.dependencies].
  2. Add to .env.example:
       LANGFUSE_PUBLIC_KEY=
       LANGFUSE_SECRET_KEY=
       LANGFUSE_HOST=https://cloud.langfuse.com
  3. Create src/cortex/observability.py with:
       - A singleton `get_langfuse()` that reads the three env vars and returns a Langfuse client (or a no-op stub when vars are absent, so local dev never breaks).
       - A context-manager `trace_llm_call(name, input, metadata)` that opens a Langfuse trace, yields a span object, and flushes on exit.
  4. Wrap every anthropic client call (and any other model-router call) with `trace_llm_call`. Pass the pipeline stage name (e.g. 'deep_research', 'repo_review', 'synthesis', 'lint') as `name` and the prompt text as `input`.
  5. After each call, log `span.score(name='output_length', value=len(response_text))` as a cheap quality proxy.
  6. Add a pytest in tests/test_observability.py that monkeypatches the Langfuse client and asserts `trace_llm_call` calls flush() exactly once per context-manager exit.

Edge cases:
  - If LANGFUSE_PUBLIC_KEY is missing, the stub must not raise — just log a structlog warning once at startup.
  - Async call sites need an async-compatible version of the context manager.
  - Do not log raw API keys or secret env vars inside trace metadata.

Verify: Run `uv run pytest tests/test_observability.py -v` and confirm it passes. Then run one pipeline stage manually and check the Langfuse dashboard for a new trace.
```
