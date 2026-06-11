---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S
generated_at: 2026-06-11T03:01:26.483504-07:00
---

# Wire Claude Code hooks (pre-tool-use / post-tool-use) to enforce vault lint before every commit

**Impact:** medium  ·  **Effort:** S

## Rationale

The nightly lint pass was added 2026-05-20 as a scheduled job, but the 30-day commit log shows daily automated commits that bypass it — lint only runs on schedule, not at commit time. Vault note 'Github Repos You Should Know' (Inbox/2026-05-16) specifically highlights the 'Cloudcode Best Practice' reference repo's use of built-in hooks for lifecycle events to enforce quality gates. The .claude directory already exists in this repo, making this a near-zero-infrastructure change.

## Cited evidence

- Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - .claude/  (list all files; read settings.json or any existing hooks config)
  - CLAUDE.md  (understand what lint checks exist and where the lint script lives)
  - scripts/  (find the vault lint script — likely lint_vault.py or nightly_lint.py)
  - pyproject.toml  (confirm entry points or script names)

Task:
Add a Claude Code PostToolUse hook that runs the vault linter after any Write or Edit tool call that touches the knowledge/ directory, and a pre-commit shell hook that does the same.

1. Claude Code hook (.claude/settings.json):
   Add a `hooks` key following the Claude Code hooks spec:
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Write|Edit",
           "hooks": [
             {
               "type": "command",
               "command": "bash -c 'echo \"$CLAUDE_TOOL_INPUT\" | python -c \"import sys,json; p=json.load(sys.stdin).get(\\\"path\\\",\\\"\\\"); exit(0 if not p.startswith(\\\"knowledge/\\\") else 0)\"' && uv run python scripts/lint_vault.py --fast"
             }
           ]
         }
       ]
     }
   }
   Simplify: use a wrapper shell script scripts/hooks/post_write_lint.sh that checks if the written path starts with 'knowledge/' and if so runs `uv run python scripts/lint_vault.py --fast --path "$1"`. Wire that script as the hook command.

2. Git pre-commit hook (.git/hooks/pre-commit):
   Create an executable script:
   #!/usr/bin/env bash
   set -e
   STAGED=$(git diff --cached --name-only | grep '^knowledge/' || true)
   if [ -n "$STAGED" ]; then
     echo '[cortex] Running vault lint on staged knowledge/ files...'
     uv run python scripts/lint_vault.py --fast --files $STAGED
   fi
   Make it executable: chmod +x .git/hooks/pre-commit.

3. Add a --fast flag to the lint script (if not present) that only checks files passed via --files or --path rather than scanning the entire vault, so the hook completes in <5 seconds.

Edge cases:
  - .git/hooks/ is not committed; document the setup step in CLAUDE.md under 'Local setup'.
  - If lint_vault.py does not exist by that name, find the actual script name first and adjust.
  - The hook must exit 0 on lint warnings (non-blocking) and exit 1 only on errors (missing required frontmatter fields like title/url/date).

Verify:
  - Manually edit a knowledge/Inbox/ file to remove its `title:` frontmatter field, then run `git commit`; confirm the pre-commit hook fires and blocks the commit with a clear error message.
  - Restore the file and confirm commit succeeds.
```
