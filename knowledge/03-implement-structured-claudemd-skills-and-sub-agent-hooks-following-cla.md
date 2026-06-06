---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-06-06T03:01:40.266571-07:00
---

# Implement structured CLAUDE.md skills and sub-agent hooks following Claude Code best-practice patterns

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

Vault note [8] (Github Repos You Should Know) specifically calls out the 'Cloudcode Best Practice' reference repo for orchestration patterns, built-in hooks for lifecycle events, and custom YAML-front-matter commands — exactly the patterns Cortex needs since it already uses Claude Code as its runtime (CLAUDE.md exists, .claude/ dir present). The current CLAUDE.md is likely a flat prose document; converting it to structured skills/subagents/hooks would reduce per-session orientation cost and make the daily self-improvement loop (added 2026-05-21) more reliable.

## Cited evidence

- Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - CLAUDE.md
  - .claude/ (list all files and read each one)
  - docs/ (list files, read any architecture or agent-design docs)
  - scripts/ (list all .py and .sh files)

Task: Refactor CLAUDE.md and the .claude/ directory to follow the Claude Code best-practice pattern (skills, sub-agents, YAML-front-matter commands, lifecycle hooks).

Steps:
1. Read the current CLAUDE.md in full. Identify every recurring workflow described in prose (e.g., 'to run deep research do X', 'to refresh knowledge do Y', 'to review a repo do Z').
2. For each workflow, create a corresponding slash-command file under .claude/commands/<workflow-name>.md with YAML front matter:
   ---
   description: one-line summary
   allowed-tools: [Bash, Read, Write, ...]
   ---
   followed by the step-by-step instructions currently buried in CLAUDE.md prose.
3. Create .claude/skills/cortex-vault.md — a preloaded skill that describes vault structure, naming conventions, and frontmatter schema so every session starts with this context without re-reading all of CLAUDE.md.
4. Add a PostToolUse hook in .claude/settings.json (or the appropriate config file) that:
   a. After any Write to knowledge/ or Inbox/, appends the file path + timestamp to .claude/file-history/vault_writes.log.
   b. This replaces any ad-hoc logging currently done in Python scripts.
5. Rewrite CLAUDE.md to be a concise index (< 100 lines) that points to the commands and skills rather than duplicating instructions.
6. Do NOT change any Python source files in this PR.

Edge cases:
  - Preserve any environment-variable or secret references currently in CLAUDE.md — move them to .claude/skills/env-reference.md.
  - If .claude/settings.json already has hooks, merge rather than overwrite.

Verification:
  - Open a fresh Claude Code session, type /deep-research and confirm the command file is offered as autocomplete.
  - Run `python -m pytest tests/ -x` to confirm no Python tests broke.
  - Manually verify .claude/file-history/vault_writes.log is written after a test Write to knowledge/.
```
