---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-05-27T03:02:00.297634-07:00
---

# Replace fire-and-forget agent commits with idempotent run-state checkpointing

**Impact:** high  ·  **Effort:** M

## Rationale

The commit history shows multiple fix commits (e.g. 'make record_link idempotent', 'fix poll: finish mailbox cleanup on already-processed emails') indicating the pipeline has been bitten repeatedly by partial-run failures leaving inconsistent state. Vault note 'Neuromorphic & Active Memory' (Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md) identifies statelessness as the core failure mode of agent pipelines. A lightweight run-state file (JSON checkpoint per pipeline stage) would let any stage resume from the last successful step rather than re-processing or crashing on duplicates.

## Cited evidence

- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md
- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (read all pipeline/orchestration entry points — poll, extract, deep_research, repo_review)
  - sql/  (understand what's already persisted in DB)
  - CLAUDE.md

Goal: Add a simple JSON checkpoint layer so every multi-step pipeline stage can resume from the last completed step after a crash or partial run.

Specific changes:
1. Create src/cortex/checkpoint.py:
   - CHECKPOINT_DIR = Path('.claude/checkpoints')  (already gitignored via .claude/)
   - class Checkpoint:
       def __init__(self, run_id: str)  — run_id = pipeline name + date, e.g. 'poll_2026-05-26'
       def get(self, step: str) -> dict | None
       def set(self, step: str, data: dict)  — atomically writes step result to {run_id}.json
       def is_done(self, step: str) -> bool
       def clear(self, run_id: str)  — call at successful pipeline completion
   - Use atomic write: write to .tmp then os.replace() to avoid corrupt JSON on crash.

2. Wrap the three most crash-prone stages identified in the commit history:
   a. Mail poll loop: checkpoint each message_id after successful DB insert + move-to-processed.
   b. Extractor loop: checkpoint each source_id after successful extraction.
   c. Deep-research: checkpoint after each of: fetch, extract, synthesize, vault-write.

3. At the start of each pipeline run, load the checkpoint for today's run_id. Skip any step whose is_done() returns True. Log a structlog warning when a step is skipped via checkpoint.

Edge cases:
  - Checkpoint dir may not exist: create it on first use.
  - Stale checkpoints from previous days: clear() is called on success; on failure the file persists for the same run_id (same date), enabling resume. Files older than 7 days can be pruned at startup.
  - The .claude/checkpoints/ path is already covered by .gitignore (.claude/scheduled_tasks.lock pattern) — confirm and add explicit entry if needed.

Verification:
  1. Unit test: create a Checkpoint, set two steps, assert is_done() returns True for both, simulate crash by not calling clear(), re-instantiate Checkpoint with same run_id, assert steps still present.
  2. Integration: run the mail poll script against a test mailbox with 3 messages, kill it after message 1, re-run, confirm messages 2-3 are processed and message 1 is skipped (check DB + structlog output).
```
