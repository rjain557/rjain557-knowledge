---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-11T03:01:26.483504-07:00
---

# Add Langfuse tracing to all LLM calls in the pipeline

**Impact:** high  ·  **Effort:** M

## Rationale

Every daily 'Knowledge refresh' commit is an automated LLM pipeline run, but there is zero observability into which prompts fired, what latency/cost each step incurred, or why a synthesis pass produced a poor result. The vault note 'Build a Complete Langfuse Observability and Evaluation Pipeline' (Inbox/2026-05-23) describes exactly this gap and shows how a single decorator/context-manager wrapping each Anthropic call captures traces, prompt versions, and scores with minimal code change. Without this, debugging regressions in the nightly lint or repo-review quality is pure guesswork.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (scan all .py files to find where anthropic.Anthropic() or AsyncAnthropic() clients are instantiated and where .messages.create() / .messages.stream() calls are made)
  - pyproject.toml  (confirm anthropic>=0.49.0 is present; add langfuse>=2.0 to dependencies)
  - .env.example  (see what env vars already exist)
  - CLAUDE.md  (understand pipeline stages)

Task:
1. Add `langfuse>=2.0` to the [project] dependencies list in pyproject.toml.
2. Add three new env vars to .env.example (with placeholder values):
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
3. Create src/cortex/observability.py that:
   a. Reads the three env vars via pydantic-settings or python-dotenv.
   b. Initialises a module-level `langfuse` client (lazy: only if keys are set, otherwise returns a no-op stub so the pipeline still works without keys).
   c. Exposes a context manager `trace_llm(name: str, input: dict) -> Generator` that opens a Langfuse generation span, yields, then records output + token usage on exit.
4. Wrap every existing anthropic .messages.create() call site with `with trace_llm(name=<stage_name>, input={"prompt": ...}) as span: ...` and set `span.output = response.content` and `span.usage = response.usage`.
5. In the repo-review workflow (wherever improvement prompts are generated), add a Langfuse score call after each commit: `langfuse.score(name='prompts_generated', value=len(improvements))`.

Edge cases:
  - If LANGFUSE_PUBLIC_KEY is absent, the stub must be a no-op (don't raise at import time).
  - Async call sites need the async Langfuse client; check for both sync and async patterns.
  - Do not log raw .env values anywhere.

Verify:
  - `uv run python -c 'from cortex.observability import trace_llm; print("ok")'` succeeds.
  - Run one extraction manually and confirm a trace appears in the Langfuse UI (or that no exception is raised when keys are absent).
```
