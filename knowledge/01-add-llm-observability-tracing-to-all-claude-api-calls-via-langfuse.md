---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-06T03:01:40.266571-07:00
---

# Add LLM observability tracing to all Claude API calls via Langfuse

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

The vault note on Langfuse (Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md) describes how tracing, prompt management, and scoring give engineers visibility into token spend, latency, and failure modes across agent pipelines. Cortex makes dozens of Claude calls per day (deep-research, repo-review, synth, lint) with no tracing layer, making it impossible to diagnose cost spikes, prompt regressions, or model-routing errors introduced in the 2026-05-24 multi-provider commit.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/cortex/llm/ (all files)
  - src/cortex/deep_research/ (all files)
  - src/cortex/repo_review/ (all files)
  - pyproject.toml
  - .env.example

Task: Instrument every Claude (and any other LLM provider) API call in Cortex with Langfuse tracing.

Steps:
1. Add `langfuse>=2.0` to pyproject.toml dependencies.
2. Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST to .env.example with placeholder values.
3. Create src/cortex/observability/tracer.py that:
   a. Reads the three env vars via pydantic-settings (fail gracefully / no-op if unset so local dev is unaffected).
   b. Exposes a get_langfuse_callback() helper that returns a LangfuseCallbackHandler (or None).
   c. Exposes a @trace_llm_call(name: str) decorator that wraps any function calling self._client.messages.create (or equivalent) and records: model name, input tokens, output tokens, latency, and a 'pipeline' tag derived from the calling module name.
4. Apply the decorator (or callback) to every site that calls the Anthropic client. Search for `.messages.create` and `client.messages` across src/.
5. For the multi-provider router added in commit 4e0a862, ensure each provider branch is tagged with provider='anthropic'|'openai'|etc.
6. Add a LANGFUSE_ENABLED=false default so CI never phones home.

Edge cases:
  - Async vs sync call sites — handle both.
  - Streaming responses — capture token counts from the final chunk's usage field.
  - If Langfuse host is unreachable, log a warning and continue; never let tracing crash the pipeline.

Verification:
  - Run `python -m pytest tests/ -x` — all existing tests must pass.
  - Manually run one deep-research job with LANGFUSE_ENABLED=true and confirm a trace appears in the Langfuse UI (or local Docker instance).
  - Run `ruff check src/` with zero new errors.
```
