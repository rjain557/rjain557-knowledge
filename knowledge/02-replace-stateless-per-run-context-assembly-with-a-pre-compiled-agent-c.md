---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-01T03:01:55.850017-07:00
---

# Replace stateless per-run context assembly with a pre-compiled agent context artifact (RAG → compiled knowledge layer)

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note [3] ('Your AI agent is rediscovering 85% of its context every run') argues that agents fail in production not because retrieval is wrong but because the retrieval system cannot assemble what the agent needs before it starts acting. Vault note [6] (Pinecone Nexus / KnowQL) reinforces this: the winning pattern is pre-compiling domain knowledge into typed, cited artifacts rather than doing ad-hoc vector search at query time. Cortex's deep-research and repo-review agents currently re-fetch and re-summarize context on every run (evidenced by the daily 'Knowledge refresh' commits). A compiled 'agent briefing' artifact — regenerated nightly, cached as a single structured YAML/JSON file per domain — would cut LLM calls and latency on every downstream agent invocation.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md
- Topics/the-company-that-made-rag-mainstream-is-now-betting-against-.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the deep-research runner and repo-review agent — likely under src/cortex/deep_research/ or similar)
  - scripts/  (find nightly/scheduled scripts)
  - CLAUDE.md
  - config/  (any domain or topic config files)

Task: Implement a nightly 'compiled context' artifact generator.

1. Create src/cortex/compiler/context_compiler.py.
   - Accept a domain string (e.g. 'agent-orchestration', 'seo-agents', 'tech-support').
   - Query the vault (knowledge/ + Topics/) for all notes tagged with that domain, sorted by recency (use frontmatter `date` field).
   - For each of the top-30 notes by recency, extract: title, url (if present), a 2-sentence summary (use the first non-empty paragraph of the body), and tags.
   - Produce a structured dict and write it to config/compiled_context_{domain}.json, overwriting on each run.
   - Include a `compiled_at` ISO timestamp and a `note_count` field.

2. Modify the deep-research agent entry-point:
   - At startup, load config/compiled_context_{domain}.json if it exists and is < 25 hours old.
   - Prepend the compiled context as a system-prompt section: 'Recent knowledge on {domain}: {json_summary}' — keep it under 2000 tokens by truncating to top-15 notes if needed.
   - If the file is missing or stale, fall back to current behavior and log a warning via structlog.

3. Add a CLI entry-point in pyproject.toml:
   [project.scripts]
   compile-context = 'cortex.compiler.context_compiler:main'
   so it can be called from the nightly scheduler.

4. Add compile-context to the nightly scheduled script (find it in scripts/ or .claude/).

Edge cases:
  - Notes with missing `date` frontmatter should sort last.
  - If fewer than 5 notes exist for a domain, emit a structlog warning but still write the file.
  - JSON must be UTF-8 safe (strip non-BMP characters from summaries).

Verification:
  - Run `compile-context agent-orchestration` and inspect config/compiled_context_agent-orchestration.json.
  - Confirm note_count > 0 and compiled_at is recent.
  - Run the deep-research agent on a test topic and confirm the system prompt includes the compiled context section in the structlog output.
```
