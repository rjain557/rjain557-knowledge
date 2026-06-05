---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-05T03:01:49.857565-07:00
---

# Instrument LLM calls with Langfuse tracing to make the daily review loop observable

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

The vault note on Langfuse (Inbox/2026-05-23) describes a complete pipeline for tracing, prompt management, scoring, and experiments — exactly what the Cortex daily review loop needs. Currently the commit history shows daily 'Knowledge refresh' commits but there is no observability into which prompts fired, what models were used, latency, or token cost. The multi-provider model routing commit (2026-05-24) added complexity that is invisible without tracing, making it impossible to know if the Haiku verifier or Sonnet swap is actually improving output quality.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context to read first:
1. src/ — find all files that instantiate `anthropic.Anthropic()` or make LLM API calls; note the call sites
2. pyproject.toml — check current dependencies
3. .env.example — understand what env vars are already declared
4. CLAUDE.md — understand the agent loop stages (ingestion, deep research, repo review, synth)

Task: Add Langfuse tracing to all LLM call sites in the Cortex pipeline.

Steps:
1. Add `langfuse>=2.0` to `pyproject.toml` dependencies.
2. Add these keys to `.env.example` (with placeholder values):
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
3. Create `src/cortex/observability.py` with a singleton `get_langfuse()` function that returns a configured `Langfuse` client (lazy-init, returns a no-op stub if env vars are missing so existing workflows don't break).
4. Wrap every `client.messages.create()` call site with a Langfuse generation span. Each span must record:
   - `name`: the logical step name (e.g. "deep_research_synthesis", "haiku_verifier", "repo_review")
   - `model`: the model string actually used
   - `input`: the messages list (truncated to 2000 chars for the prompt field)
   - `output`: the response text
   - `usage`: input_tokens and output_tokens from the response
   - `metadata`: dict with at minimum `{"source_url": ..., "run_date": ...}` where available
5. Group all spans within a single pipeline run (e.g. one daily refresh) under a single Langfuse `trace` with a `session_id` of `f"cortex-{date.today().isoformat()}"`.

Edge cases:
- If `LANGFUSE_PUBLIC_KEY` is not set, the stub must silently no-op — do not raise, do not log warnings on every call
- Async call sites (if any) need async span context managers
- Do not log raw `.env` secrets into span metadata

Verification:
1. Set real Langfuse keys in `.env` and run one ingestion pass manually
2. Open Langfuse dashboard and confirm a trace appears with correct model names and token counts
3. Run with keys unset and confirm the pipeline completes without errors
4. Run `ruff check src/cortex/observability.py` and fix any lint issues
```
