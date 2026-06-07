---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-07T03:01:21.608196-07:00
---

# Add a persistent codebase index (CLAUDE.md knowledge graph) to eliminate cold-start token waste

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault notes [1] and [10] both document that AI coding agents burn 70-94% of their token budget re-reading source files on every session. Cortex's own daily review loop (30 commits of 'Knowledge refresh' commits) means Claude Code re-orients to the same repo structure every single day. Pre-computing a structured CLAUDE.md index of modules, entry-points, and data-flow edges would let each session skip the orientation phase entirely.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/this-tool-just-cut-ai-coding-token-costs-by-94-code-context-.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Files to read first:
  - CLAUDE.md
  - pyproject.toml
  - src/ (list all .py files recursively: `find src -name '*.py' | head -60`)
  - scripts/ (list all files: `ls scripts/`)
  - config/ (list all files: `ls config/`)

Task: Extend CLAUDE.md with a structured 'Codebase Map' section that acts as a persistent knowledge graph for Claude Code sessions.

The section should include:
1. **Module inventory** — for each top-level package under src/, one line: package name | purpose (≤12 words) | primary entry-point file.
2. **Data-flow diagram** (ASCII) — show how an article URL flows from ingestion → extraction → vault write → embedding → MCP exposure. Derive this from actual imports and function calls in the source.
3. **Key config knobs** — list every env var in .env.example with a one-line description of what breaks if it is missing.
4. **Scheduled job registry** — list every APScheduler or cron job defined in src/ or scripts/, with its interval and the function it calls.
5. **SQL schema summary** — list every table referenced in sql/ with its primary key and purpose.

Edge cases:
  - If a module has no clear entry-point, note 'library only'.
  - Do not duplicate content already in CLAUDE.md; append the new section after existing content under a heading '## Codebase Map (auto-maintained)'.
  - Add a comment at the top of the section: '<!-- Regenerate with: scripts/gen_codebase_map.py -->' (you will create this script).

Also create scripts/gen_codebase_map.py that:
  - Walks src/ and scripts/ using ast.parse to extract module docstrings and top-level function names.
  - Reads sql/*.sql files to extract CREATE TABLE statements.
  - Reads .env.example line by line.
  - Outputs the Markdown section to stdout so it can be piped into CLAUDE.md.

Verify: Run `python scripts/gen_codebase_map.py` and confirm it produces valid Markdown with no import errors. Then manually paste the output into CLAUDE.md and commit.
```
