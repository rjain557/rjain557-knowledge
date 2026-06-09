---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-09T03:01:24.645075-07:00
---

# Wire Claude Code hooks (pre-tool-use / post-tool-use) to enforce vault write safety invariants

**Impact:** high  ·  **Effort:** M

## Rationale

The Claude Code maturity levels note (Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md) identifies hooks as the Level 4 capability that separates power users from casual ones, and the GitHub repos note (Inbox/2026-05-16-github-repos-you-should-know) specifically calls out the 'Cloudcode Best Practice' repo for lifecycle hooks. Cortex's automated agents write directly to the knowledge/ vault on every run; there is currently no hook that validates frontmatter schema, prevents duplicate slugs, or blocks writes to protected notes before they land. A pre-tool-use hook on Write/Edit file operations would catch these issues before they corrupt the vault.

## Cited evidence

- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md
- Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

Context files to read first:
  1. .claude/ — list all files; read any existing hooks configuration
  2. CLAUDE.md — understand current agent instructions and vault write rules
  3. knowledge/ — read 5 sample notes to understand required frontmatter fields
  4. src/cortex/ — find any existing vault-write utilities

Task: Add Claude Code pre-tool-use and post-tool-use hooks that enforce vault write safety.

Steps:
  1. Create scripts/hooks/pre_tool_use.py. This script receives a JSON payload on stdin (Claude Code hook protocol). When tool_name is 'Write' or 'Edit' and the target path starts with 'knowledge/':
       a. Parse the file content from the payload.
       b. Validate frontmatter using python-frontmatter: required fields are title, date, categories (list), and at least one of [url, source].
       c. Check that the slug (filename without .md) does not already exist in knowledge/ with different content (duplicate detection).
       d. If validation fails, print a JSON response `{"decision": "block", "reason": "<human-readable message>"}` to stdout and exit 1.
       e. If validation passes, print `{"decision": "approve"}` and exit 0.
  2. Create scripts/hooks/post_tool_use.py. After any approved Write to knowledge/, append a one-line entry to logs/vault_writes.log: `ISO8601_timestamp | tool | path | frontmatter_title`.
  3. Register both hooks in .claude/settings.json (or the appropriate Claude Code hooks config file — check existing .claude/ structure):
       hooks:
         pre_tool_use: python scripts/hooks/pre_tool_use.py
         post_tool_use: python scripts/hooks/post_tool_use.py
  4. Add tests/test_hooks.py with:
       - A test that feeds a valid vault note payload and asserts decision == 'approve'.
       - A test that feeds a note missing 'title' and asserts decision == 'block'.
       - A test that feeds a path outside knowledge/ and asserts decision == 'approve' (hook is a no-op).

Edge cases:
  - The hook must complete in <2 seconds or Claude Code will time out; do not make network calls.
  - If python-frontmatter fails to parse (malformed YAML), block the write with a clear error.
  - The hook must be executable without activating the full venv — use `#!/usr/bin/env python3` and only stdlib + python-frontmatter.
  - logs/vault_writes.log must be in .gitignore (add it if absent).

Verify:
  1. `uv run pytest tests/test_hooks.py -v` passes.
  2. Manually invoke `echo '{...valid payload...}' | python scripts/hooks/pre_tool_use.py` and confirm exit code 0.
  3. Manually invoke with a missing-title payload and confirm exit code 1 with a readable reason.
```
