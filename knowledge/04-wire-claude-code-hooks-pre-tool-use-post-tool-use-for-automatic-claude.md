---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-26T03:02:07.112020-07:00
---

# Wire Claude Code hooks (pre-tool-use / post-tool-use) for automatic CLAUDE.md context injection

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

Vault note 'Github Repos You Should Know' (Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md) specifically calls out the 'Cloudcode Best Practice' repo pattern: using built-in hooks for lifecycle events and configuring agents with preloaded skills. The repo already has a .claude/ directory and CLAUDE.md, but the commit history shows no hook configuration — meaning every Claude Code session in this repo re-discovers context that could be pre-loaded automatically, wasting tokens and risking inconsistent behavior across the repo-review, deep-research, and vault-write agents.

## Cited evidence

- Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
  - .claude/  (list all files; read any existing settings.json or hooks config)
  - CLAUDE.md  (understand what context is currently documented)
  - scripts/  (understand what scripts are invoked by Claude Code agents)

Task: Configure Claude Code lifecycle hooks so that key context is automatically injected and post-run summaries are logged.

Step 1 — Create .claude/settings.json (if it doesn't exist, or extend it)
  Add a hooks section following the Claude Code hooks spec:
  {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "Bash",
          "hooks": [
            {
              "type": "command",
              "command": "python scripts/hooks/pre_bash.py"
            }
          ]
        }
      ],
      "PostToolUse": [
        {
          "matcher": "Write",
          "hooks": [
            {
              "type": "command",
              "command": "python scripts/hooks/post_write.py"
            }
          ]
        }
      ],
      "Stop": [
        {
          "hooks": [
            {
              "type": "command",
              "command": "python scripts/hooks/on_stop.py"
            }
          ]
        }
      ]
    }
  }

Step 2 — Create scripts/hooks/pre_bash.py
  Reads stdin (Claude Code passes tool-input JSON on stdin).
  If the bash command touches src/ or scripts/, print to stdout a one-line reminder of the project's coding conventions (pulled from CLAUDE.md §conventions if that section exists, otherwise a hardcoded string).
  Exit 0 always (never block execution).

Step 3 — Create scripts/hooks/post_write.py
  Reads stdin (tool-result JSON with the file path written).
  If the written file is under knowledge/ or src/cortex/vault/, call the vault index invalidation function (import and call cortex.vault.writer.invalidate_index() if it exists after the dedup improvement, otherwise just touch .cortex_graph/.dirty).
  Log the write event to logs/hook_writes.log with timestamp + path.
  Exit 0 always.

Step 4 — Create scripts/hooks/on_stop.py
  Appends a one-line session summary to logs/session_log.jsonl:
    {"ts": "<ISO8601>", "session_end": true, "note": "Claude Code session ended"}
  This gives a lightweight audit trail of when automated agents ran.

Step 5 — Update .gitignore
  Add logs/hook_writes.log and logs/session_log.jsonl to .gitignore (they are local runtime artifacts).

Edge cases:
  - Hook scripts must never crash Claude Code — wrap all logic in try/except and exit 0 on any exception, logging the error to stderr.
  - Hook scripts must complete in <2 seconds to avoid blocking the agent; no network calls, no heavy imports.
  - If .claude/settings.json already has a hooks key, merge rather than overwrite.

Verification:
  1. Open Claude Code in this repo and run a simple Bash tool call (e.g., `ls src/`); confirm pre_bash.py fires (check stderr or a debug log).
  2. Have Claude Code write a file under knowledge/; confirm post_write.py logs the event to logs/hook_writes.log.
  3. End the session; confirm logs/session_log.jsonl has a new entry.
  4. Confirm `uv run pytest` still passes.
```
