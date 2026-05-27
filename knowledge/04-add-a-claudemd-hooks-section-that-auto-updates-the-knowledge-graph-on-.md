---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S
generated_at: 2026-05-27T03:02:00.297634-07:00
---

# Add a CLAUDE.md hooks section that auto-updates the knowledge graph on every vault write

**Impact:** medium  ·  **Effort:** S

## Rationale

Vault notes 'Claude Code + Obsidian as Agent Command Center' and 'Obsidian × Claude Code' (Topics/claude-code-obsidian-commmand-center.md, Topics/obsidian-x-claude-code.md) both describe lifecycle hooks as the mechanism that turns a passive vault into an active agent layer — specifically, post-write hooks that trigger re-indexing so the graph stays current without manual intervention. The current CLAUDE.md (commit 87d2b5e) points Layer 2 auto-memory at the vault junction but there is no evidence of a PostToolUse hook that fires graph/index refresh after any Write or Edit tool call on knowledge/.

## Cited evidence

- Topics/claude-code-obsidian-commmand-center.md
- Topics/obsidian-x-claude-code.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - CLAUDE.md  (read entire file)
  - .claude/  (list all files; read settings.json or any hooks config)
  - scripts/  (find the lint/synth/graph-build scripts)

Goal: Wire a PostToolUse Claude Code hook so that any Write or Edit tool call targeting a file under knowledge/ automatically triggers a fast incremental graph index update.

Specific changes:
1. In .claude/settings.json (create if absent), add a hooks section following the Claude Code hooks schema:
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Write|Edit",
           "hooks": [
             {
               "type": "command",
               "command": "python scripts/refresh_graph.py --incremental"
             }
           ]
         }
       ]
     }
   }
   The matcher should only fire when the tool's file argument starts with 'knowledge/' — check Claude Code hook docs for path-filter syntax; if path filtering isn't supported in the matcher, add a guard at the top of refresh_graph.py that exits 0 immediately if sys.argv contains a path outside knowledge/.

2. Create scripts/refresh_graph.py:
   - Accepts --incremental flag (for hook calls) and --full flag (for nightly lint).
   - --incremental: reads knowledge/.graph_index.json if it exists, walks only files with mtime newer than the index file's mtime, merges updated nodes into the existing graph, saves.
   - --full: calls build_graph() from src/cortex/graph.py (from improvement #1) on the entire vault.
   - Exits 0 on success, 1 on error (so Claude Code can surface hook failures).
   - Runs in <2 seconds for incremental mode on a vault of <10k files.

3. Add a one-line entry to CLAUDE.md under a new '## Hooks' section documenting what the hook does and why, so future agents reading CLAUDE.md understand the side-effect.

Edge cases:
  - Hook fires during bulk import (many files written in a loop): the incremental script must be idempotent and safe to run concurrently — use a file lock (fcntl or msvcrt) around the graph write.
  - If src/cortex/graph.py doesn't exist yet (improvement #1 not merged): make refresh_graph.py degrade gracefully with a logged warning rather than crashing the hook.
  - Windows workstation (workstation.md present): use a cross-platform lock approach.

Verification:
  1. Manually trigger: echo 'test' >> knowledge/test_hook.md && cat knowledge/.graph_index.json | python -c "import sys,json; g=json.load(sys.stdin); print('test_hook' in str(g))"
  2. Confirm the hook fires by checking structlog output or a timestamp on .graph_index.json.
  3. Run: python scripts/refresh_graph.py --full and confirm it completes without error.
  4. Delete knowledge/test_hook.md after verification.
```
