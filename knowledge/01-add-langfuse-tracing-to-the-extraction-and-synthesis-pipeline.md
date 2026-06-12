---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-12T03:01:20.219071-07:00
---

# Add Langfuse tracing to the extraction and synthesis pipeline

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

The repo runs daily LLM calls for extraction, synthesis, lint, and repo-review but has zero observability — there is no way to see which prompts are slow, expensive, or producing low-quality vault notes. The Langfuse vault note (Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md) describes an open-source, self-hostable tracing layer that captures prompt versions, token counts, latency, and scoring in one pipeline. Adding it now, while the pipeline is still small, avoids retrofitting across dozens of call sites later.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - pyproject.toml  (current deps)
  - src/  (scan all .py files to find every place anthropic client is called — look for client.messages.create or similar)
  - CLAUDE.md  (understand pipeline stages)

Task:
Integrate Langfuse tracing into the Cortex LLM pipeline.

Steps:
1. Add `langfuse>=2.0` to pyproject.toml dependencies.
2. Create src/cortex/observability.py with:
   - A singleton `get_langfuse()` that reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env (default host = https://cloud.langfuse.com).
   - A context-manager `trace_llm_call(name: str, input: dict, metadata: dict)` that opens a Langfuse trace + generation span, yields, then records output tokens and latency on exit.
3. Wrap every anthropic client call site found in step 1 with `trace_llm_call`, passing the pipeline stage name (e.g. 'extraction', 'synthesis', 'repo-review') as `name`.
4. Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST to .env.example with placeholder values.
5. In the nightly lint/synthesis script, after each run emit a Langfuse score (0-1) based on whether the vault write succeeded.

Edge cases:
  - If Langfuse env vars are absent, observability.py must no-op silently (don't break the pipeline in dev).
  - Async call sites need an async-compatible span context manager.
  - Do NOT log raw API keys or vault content in trace metadata.

Verify:
  - `uv run python -c 'from src.cortex.observability import get_langfuse; print(get_langfuse())'` prints a Langfuse client or None.
  - Run one extraction manually and confirm a trace appears in the Langfuse UI (or local docker instance).
  - `uv run pytest tests/ -x` still passes.
```
