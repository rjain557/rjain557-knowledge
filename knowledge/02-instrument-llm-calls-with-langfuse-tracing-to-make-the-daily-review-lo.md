---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-07T03:01:21.608196-07:00
---

# Instrument LLM calls with Langfuse tracing to make the daily review loop observable

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note [7] details a complete Langfuse pipeline for tracing, prompt management, and scoring LLM calls. Cortex runs Claude API calls daily across deep-research, synthesis, lint, and repo-review workflows, but there is no observability layer — failures are silent and prompt drift is invisible. Adding Langfuse traces would expose which prompts are expensive, which extractions fail silently, and whether synthesis quality is degrading over time.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Files to read first:
  - src/ — find the module(s) that call anthropic.Anthropic() or anthropic.AsyncAnthropic() (`grep -r 'anthropic' src/ --include='*.py' -l`)
  - pyproject.toml (dependencies section)
  - .env.example

Task: Add Langfuse tracing to every Anthropic API call in the codebase.

Steps:
1. Add `langfuse>=2.0` to pyproject.toml dependencies (under the Core section).
2. Add these keys to .env.example:
   LANGFUSE_PUBLIC_KEY=
   LANGFUSE_SECRET_KEY=
   LANGFUSE_HOST=https://cloud.langfuse.com
3. Create src/cortex/observability.py with:
   - A `get_langfuse()` singleton that reads the three env vars and returns a Langfuse client (or a no-op stub if vars are absent, so the system still works without Langfuse configured).
   - A context manager `trace_llm_call(name: str, input: dict, metadata: dict = {})` that opens a Langfuse generation span, yields, and closes it with the response and token counts.
4. In every file identified in step 1, wrap each `client.messages.create(...)` call with `trace_llm_call(name='<workflow_name>', input={'model': model, 'prompt': prompt[:500]}, metadata={'workflow': '<module_name>'})`. Capture `usage.input_tokens` and `usage.output_tokens` from the response and record them on the span.
5. For the repo-review workflow specifically, also log the repo name as a metadata tag so you can filter by repo in the Langfuse dashboard.

Edge cases:
  - If LANGFUSE_* vars are missing, the stub must not raise — use a try/except in get_langfuse() and return None, then guard all span calls with `if langfuse_client`.
  - Do not log full prompt text (may contain secrets); truncate to 500 chars.
  - Async callers: use langfuse's async client variant if the calling code is async.

Verify:
  - `uv run python -c 'from cortex.observability import get_langfuse; print(get_langfuse())'` should not raise.
  - Run one extraction manually and confirm a trace appears in the Langfuse dashboard (or confirm the no-op path works when keys are absent).
```
