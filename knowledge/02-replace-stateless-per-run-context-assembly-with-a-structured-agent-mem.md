---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-31T03:02:02.165089-07:00
---

# Replace stateless per-run context assembly with a structured agent-memory contract (warm-start file)

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note 'Your AI agent is rediscovering 85% of its context every run' (Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md) identifies that agents failing in production do so because the retrieval system cannot assemble what the agent needs *before* it starts acting — not because the retrieval method is wrong. The Cortex repo-review agent (commit 2026-05-17) and deep-research agent both appear to re-read CLAUDE.md and re-query the vault from scratch each invocation. A warm-start JSON file written at the end of each successful run (capturing: last processed source IDs, active topic list, recent synthesis slugs, model routing state) would let the next run skip re-discovery and start acting immediately.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md
- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
1. src/ — find the main entry points for the repo-review agent, deep-research agent, and the hourly poll/scheduler
2. CLAUDE.md — understand what context is currently loaded at agent startup
3. sql/ — identify tables that track processed source IDs and topic state
4. config/ — check for any existing state/checkpoint config

Task: Implement a warm-start state file so agents skip re-discovery on subsequent runs.

Step 1 — Define the warm-start schema in src/cortex/agent_state.py:
```python
from pydantic import BaseModel
from datetime import datetime

class AgentWarmState(BaseModel):
    written_at: datetime
    last_processed_source_ids: list[int]  # DB IDs of last N sources ingested
    active_topics: list[str]             # topic slugs currently in rotation
    recent_synthesis_slugs: list[str]    # last 10 deep-research output slugs
    model_routing_snapshot: dict         # copy of current model routing config
    pending_review_repos: list[str]      # repos queued for next review cycle
```

Step 2 — Write `save_warm_state(state: AgentWarmState, path: Path)` and `load_warm_state(path: Path) -> AgentWarmState | None` functions:
- Save to `.cortex_state.json` in the repo root (add to .gitignore)
- load_warm_state returns None if file missing or schema version mismatch (handle gracefully)
- Use pydantic model_dump(mode='json') for serialization

Step 3 — Wire into each agent entry point:
- At startup: call `load_warm_state()`, if not None skip the DB queries that re-fetch already-processed source IDs and already-known topics; log 'warm start: skipping N sources already processed'
- At successful completion: call `save_warm_state()` with updated state
- On failure/exception: do NOT overwrite the state file (preserve last good state)

Step 4 — Add `.cortex_state.json` to .gitignore (it contains runtime state, not source).

Step 5 — Update CLAUDE.md to document the warm-start contract so future agents know to check for it.

Edge cases:
- First run (no state file): agent must fall back to full DB scan — this is the existing behavior, so no regression
- State file from a different schema version: detect via a `schema_version: int` field, discard and rebuild if mismatch
- Concurrent runs (two agents writing simultaneously): use a `.lock` file pattern already established in `.claude/scheduled_tasks.lock`
- The `last_processed_source_ids` list should be capped at 500 to prevent unbounded growth

Verification:
1. Delete `.cortex_state.json`, run the pipeline — confirm it completes and writes the state file
2. Run the pipeline again immediately — confirm log output shows 'warm start' and the run completes faster (measure wall time)
3. Corrupt the state file manually, run again — confirm it falls back to full scan without crashing
4. Check that `.cortex_state.json` does not appear in `git status` (gitignore working)
```
