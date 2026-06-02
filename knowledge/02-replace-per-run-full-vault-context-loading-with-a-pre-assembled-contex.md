---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-02T03:02:04.796423-07:00
---

# Replace per-run full-vault context loading with a pre-assembled context bundle (fix the 85% rediscovery problem)

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note [3] ('Your AI agent is rediscovering 85% of its context every run') specifically identifies that agents fail not because retrieval is wrong but because the retrieval system cannot assemble what the agent needs before it starts acting. The daily Cortex review commits show the agent runs fresh every day; without a pre-assembled context bundle (recent notes summary + active topics index), each run re-reads the entire vault. Adding a nightly `context_bundle.json` that pre-computes the top-N most-recently-updated notes, active topics, and pending inbox items would cut per-run token cost and latency.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the scheduler, the deep-research runner, and any vault-reader utilities)
  - CLAUDE.md  (understand what context the agent is given at session start)
  - .claude/  (any settings or system prompt files)
  - knowledge/  (sample directory listing only — do not read all files)

Goal: Create a nightly job that writes knowledge/_context_bundle.json, and update the agent's session-start prompt to load that file instead of scanning the vault.

Step 1 — Bundle builder (src/vault/build_context_bundle.py):
  Write `build_context_bundle(vault_dir: Path, out_path: Path, top_n: int = 40) -> None`:
    a. Walk vault_dir, collect all .md files with their mtime.
    b. Sort by mtime descending, take top_n.
    c. For each, parse frontmatter + first 300 chars of body.
    d. Also collect all files modified in the last 7 days regardless of rank.
    e. Deduplicate, then write out_path as JSON:
       {
         "generated_at": "<ISO UTC>",
         "recent_notes": [{"slug": ..., "title": ..., "domain": ..., "summary": ..., "tags": [...], "mtime": ...}],
         "active_topics": [<unique domain values with counts>],
         "inbox_pending": <count of files in knowledge/Inbox/ modified in last 24h>
       }

Step 2 — Schedule it:
  Find the APScheduler setup (likely in src/scheduler.py or scripts/).
  Add a nightly job (e.g., 02:00 America/Los_Angeles) that calls build_context_bundle.

Step 3 — Update session-start context:
  In CLAUDE.md (or wherever the agent's system prompt is assembled), replace any instruction that says 'read the knowledge/ directory' with:
    'Read knowledge/_context_bundle.json first. Use it to orient yourself. Only read individual note files when you need the full body of a specific note.'

Edge cases:
  - If _context_bundle.json does not exist yet (first run), the agent should fall back to listing knowledge/ directory.
  - The bundle must be regenerated atomically (write to a temp file, then rename) to avoid a half-written file being read mid-session.
  - Exclude _context_bundle.json itself from the vault_nodes graph index (it is a derived artifact).
  - Add _context_bundle.json to .gitignore so it is not committed on every nightly run.

Verification:
  1. Run `python -m src.vault.build_context_bundle` manually.
  2. Inspect knowledge/_context_bundle.json — confirm recent_notes has <=40 entries, all fields populated.
  3. Confirm the scheduler picks up the new job: check APScheduler job list in logs.
  4. Confirm _context_bundle.json appears in .gitignore.
```
