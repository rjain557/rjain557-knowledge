---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-10T03:01:20.668814-07:00
---

# Add LLM observability tracing to extraction and deep-research pipelines

**Impact:** high  ·  **Effort:** M

## Rationale

The vault note on Langfuse (Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md) details how tracing, prompt management, and scoring catch silent failures in multi-step LLM pipelines. Cortex runs daily extraction + deep-research + synthesis loops with no visible tracing layer (no langfuse/opentelemetry import in pyproject.toml, no mention in CLAUDE.md). Without traces, regressions in extraction quality or model-routing decisions are invisible until vault content degrades.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

Files to read first:
  1. pyproject.toml  — confirm langfuse is absent from dependencies
  2. src/  — list all Python modules; identify the deep-research runner and the extraction pipeline entry points (look for files named *extract*, *deep_research*, *pipeline*, *runner*)
  3. CLAUDE.md  — understand current workflow hooks
  4. .env.example  — see what env vars are already declared

Change to make:
  1. Add `langfuse>=2.0` to the [project] dependencies in pyproject.toml.
  2. In .env.example add:
       LANGFUSE_PUBLIC_KEY=
       LANGFUSE_SECRET_KEY=
       LANGFUSE_HOST=https://cloud.langfuse.com
  3. Create src/cortex/observability.py with a thin wrapper:
       - A `get_langfuse()` factory that reads the three env vars and returns a Langfuse client (or a no-op stub when vars are absent, so local runs don't break).
       - A context-manager `trace_run(name, input_data)` that opens a Langfuse trace, yields a `span` helper, and flushes on exit.
  4. In the deep-research runner (whichever file orchestrates the multi-step LLM calls), wrap the top-level run function with `trace_run('deep_research', {'url': url})` and add a child span around each LLM call, recording model name, prompt token count, and completion token count.
  5. In the extraction pipeline entry point, wrap each article extraction attempt with `trace_run('extraction', {'source': source_id})`.

Edge cases:
  - If LANGFUSE_PUBLIC_KEY is empty, the stub must not raise — extraction must still succeed.
  - Async pipelines: use Langfuse's async flush or call `langfuse.flush()` in a finally block.
  - Don't log raw article text as trace input (PII / size); log only URL + metadata.

How to verify:
  1. `uv run pytest tests/ -x` — existing tests must still pass.
  2. Set the three LANGFUSE env vars pointing at a free Langfuse Cloud project, run one extraction manually, and confirm a trace appears in the Langfuse UI with correct span nesting.
```
