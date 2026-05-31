---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-31T03:02:02.165089-07:00
---

# Implement Claude Code hooks for lifecycle-aware vault writes (pre-write dedup + post-write graph refresh)

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

Vault note 'Github Repos You Should Know' (Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md) specifically calls out the 'Cloudcode Best Practice' repo pattern of using built-in hooks for lifecycle events. The Cortex repo already has a .claude/ directory but the .gitignore excludes settings.local.json and scheduled_tasks.lock — suggesting hooks are not yet configured. Adding a pre-tool-use hook that checks for duplicate slugs before any vault write, and a post-tool-use hook that triggers an incremental graph refresh after a write, would prevent the duplicate-note accumulation that plagues long-running ingestion pipelines and keep the graph index fresh without a full nightly rebuild.

## Cited evidence

- Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md
- Topics/claude-code-obsidian-commmand-center.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
1. .claude/ — list all files present (ls -la .claude/); read any existing settings.json or hooks config
2. CLAUDE.md — understand current agent instructions
3. src/ — find the vault writer module (likely src/cortex/vault.py or similar) to understand how notes are written
4. knowledge/ — check a few filenames to understand the slug/filename convention

Task: Configure Claude Code hooks to enforce dedup before vault writes and trigger incremental graph refresh after.

Step 1 — Create .claude/settings.json (if it doesn't exist) with the following hook configuration:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python scripts/hooks/pre_vault_write.py '$CLAUDE_TOOL_INPUT_PATH'"
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
            "command": "python scripts/hooks/post_vault_write.py '$CLAUDE_TOOL_INPUT_PATH'"
          }
        ]
      }
    ]
  }
}
```

Step 2 — Create scripts/hooks/pre_vault_write.py:
- Accept the target file path as sys.argv[1]
- If the path is inside the knowledge/ or Inbox/ directory:
  - Parse the slug from the filename
  - Check if a file with that slug already exists anywhere in knowledge/ (recursive glob)
  - If duplicate found: print a JSON block `{"decision": "block", "reason": "duplicate slug: <existing_path>"}` to stdout and exit 1
  - If not duplicate: exit 0 (allow)
- If path is outside vault directories: exit 0 (allow unconditionally)

Step 3 — Create scripts/hooks/post_vault_write.py:
- Accept the written file path as sys.argv[1]
- If the path is inside knowledge/ or Inbox/:
  - Run an incremental graph update: parse only the newly written file's frontmatter and upsert its edges into the kg_edges table (or call `kg_builder.update_single_note(path)` if that function exists from Improvement #1)
  - Log: `structlog.get_logger().info('post_write_hook', path=path, edges_upserted=N)`
- Exit 0 always (post hooks should not block)

Step 4 — Add scripts/hooks/__init__.py (empty) so the directory is a proper package.

Edge cases:
- Hook scripts must handle the case where kg_edges table doesn't exist yet (graph layer not yet built) — catch the exception and log a warning, do not fail
- The pre-write hook must NOT block writes to src/, scripts/, config/, sql/ — only vault directories
- Hook scripts must complete in <2 seconds to avoid blocking the agent; if the DB query takes longer, add a 1.5s timeout and allow on timeout
- Test that settings.local.json (gitignored) does not override settings.json hooks

Verification:
1. Run `claude` in the repo root and attempt to write a duplicate note — confirm the hook blocks it and prints the reason
2. Write a new unique note — confirm it succeeds and the post-hook logs edge upserts
3. Write a file to src/ — confirm neither hook fires (check logs)
4. Run `python scripts/hooks/pre_vault_write.py knowledge/some-existing-note.md` directly and confirm it exits 1 with the duplicate message
```
