---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-03T03:01:25.023856-07:00
---

# Add Langfuse tracing to deep-research and extraction pipeline runs

**Impact:** high  ·  **Effort:** M

## Rationale

The vault note on Langfuse (Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md) details a complete open-source tracing + scoring pipeline for LLM calls. Cortex currently fires multi-step Claude calls (deep-research, synthesis, repo-review) with no structured observability — failures surface only in raw log files that are gitignored. Adding Langfuse traces would give per-run latency, token cost, and quality scores, enabling the self-improvement loop to actually measure whether nightly refreshes are getting better.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (scan all Python files, note every place anthropic client.messages.create or similar is called)
  - pyproject.toml  (confirm langfuse is NOT yet a dependency)
  - CLAUDE.md
  - .env.example

Task: Instrument the Cortex LLM pipeline with Langfuse tracing.

Steps:
1. Add `langfuse>=2.0` to the [dependencies] list in pyproject.toml.
2. Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST to .env.example with placeholder values and a comment explaining they are optional (default host = https://cloud.langfuse.com).
3. Create src/cortex/observability.py with:
   - A get_langfuse() factory that returns a Langfuse client if env vars are set, else a no-op stub so the rest of the code never needs to branch.
   - A context-manager `trace_run(name, metadata)` that opens a Langfuse trace and yields a span helper.
4. Wrap the three highest-value call sites (deep-research Claude call, synthesis Claude call, repo-review Claude call — find exact file paths by scanning src/) with `trace_run`. Capture: model name, input token count, output token count, wall-clock duration, and a 'success' boolean.
5. At the end of each trace, call span.score(name='vault_notes_written', value=N) where N is the count of markdown files written in that run.

Edge cases:
  - If LANGFUSE_PUBLIC_KEY is absent, the stub must be a true no-op — no exceptions, no warnings.
  - Do not import langfuse at module level in hot-path files; import inside get_langfuse() to keep startup fast when disabled.
  - Langfuse flushes async; add a langfuse.flush() call in the scheduler shutdown hook so traces aren't lost on clean exit.

Verification:
  - Set dummy env vars and run `python -m cortex.observability` — it should print 'Langfuse connected' or 'Langfuse disabled (no keys)'.
  - Run one deep-research job locally and confirm a trace appears in the Langfuse UI (or in the stub's in-memory log if keys absent).
  - `ruff check src/cortex/observability.py` must pass clean.
```
