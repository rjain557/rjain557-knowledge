---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S
generated_at: 2026-06-10T03:01:20.668814-07:00
---

# Add Claude Code hooks for pre-commit vault validation and post-commit knowledge-graph rebuild

**Impact:** medium  ·  **Effort:** S

## Rationale

The vault note on Claude Code best practices (Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md) specifically calls out lifecycle hooks as the key pattern for advanced Claude Code configuration — pre/post hooks prevent bad state from entering the repo. Cortex commits knowledge/ files directly to main (commit 2026-05-20: 'commit knowledge/ directly to default branch') with no visible pre-commit validation. A malformed frontmatter note or a broken JSON graph silently corrupts downstream MCP queries.

## Cited evidence

- Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

Files to read first:
  1. .claude/  — list all files; read any existing settings.json or hooks config
  2. CLAUDE.md  — understand current Claude Code configuration
  3. knowledge/  — inspect 2-3 note files to confirm frontmatter schema (title, date, categories, etc.)
  4. scripts/  — check if a validate or lint script already exists

Change to make:
  1. Create scripts/validate_vault.py:
       - Accepts an optional list of file paths as argv (for pre-commit use) or defaults to all knowledge/**/*.md
       - For each file: parse frontmatter with python-frontmatter; assert required keys ['title', 'date'] are present and non-empty; assert `date` parses as ISO-8601.
       - Exit code 1 with a clear error message if any file fails; exit 0 on success.

  2. Create or update .claude/settings.json to add hooks:
       {
         "hooks": {
           "PreToolUse": [
             {
               "matcher": "Bash",
               "hooks": [
                 {
                   "type": "command",
                   "command": "python scripts/validate_vault.py"
                 }
               ]
             }
           ],
           "PostToolUse": [
             {
               "matcher": "Bash",
               "hooks": [
                 {
                   "type": "command",
                   "command": "python scripts/build_repo_graph.py 2>/dev/null || true"
                 }
               ]
             }
           ]
         }
       }
     (Adjust matcher patterns to only fire on git-commit-related Bash calls if the hooks API supports glob matching — check .claude docs.)

  3. Add a note to CLAUDE.md under a '## Hooks' section explaining what each hook does.

Edge cases:
  - validate_vault.py must not crash on binary files accidentally placed in knowledge/ — skip non-.md files silently.
  - The PostToolUse graph rebuild must not block the commit if build_repo_graph.py fails (hence `|| true`).
  - .claude/settings.local.json is gitignored — make sure changes go into settings.json (the tracked file).

How to verify:
  1. `python scripts/validate_vault.py` exits 0 on the current knowledge/ directory.
  2. Manually create knowledge/test_bad.md with missing `title` frontmatter; confirm `python scripts/validate_vault.py knowledge/test_bad.md` exits 1 with a readable error; delete the test file.
  3. Confirm .claude/settings.json is valid JSON: `python -c "import json; json.load(open('.claude/settings.json'))"`
```
