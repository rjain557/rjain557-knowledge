---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-24T07:12:31.038902-07:00
---

# Wire Claude Code hooks to auto-update CLAUDE.md memory when vault notes are written

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

Vault notes [7] and [8] ('From Vibe Coding to Agent Orchestration' and 'Claude Code Secrets') both describe CLAUDE.md auto-memory and hooks as the mechanism that makes context persist across sessions without manual upkeep. Cortex already has a CLAUDE.md and a vault writer, but the two are not connected: when a new synthesis note lands in the vault, CLAUDE.md is not updated, so the next Claude Code session doesn't know the new knowledge exists. Adding a post-write hook that appends a one-line summary + vault path to a CLAUDE.md 'Recent Knowledge' section closes this loop and implements the 'Level 2 multi-window context' pattern described in note [7].

## Cited evidence

- Topics/stop-vibecoding-and-start-orchestrating-agents-three-levels-.md
- Topics/claude-code-secrets-nobody-talks-about.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Files to read first:
  - CLAUDE.md  (understand current structure — find the section headings)
  - .claude/  (list all files; read settings.json or any hooks config)
  - src/cortex/vault/  (find the vault writer — the module that writes .md files to the vault)
  - docs/  (any spec mentioning hooks or CLAUDE.md auto-memory)

Task: Add a post-vault-write hook that keeps a 'Recent Knowledge' section in CLAUDE.md current.

Steps:
1. In src/cortex/vault/writer.py (or equivalent), after the file is successfully written to disk, call a new helper: update_claude_md_memory(vault_path, title, domain, one_line_summary)

2. Create src/cortex/vault/claude_md_memory.py:
   CLAUDE_MD = Path(__file__).parents[3] / 'CLAUDE.md'  # repo root
   SECTION_HEADER = '## Recent Knowledge'
   MAX_ENTRIES = 20  # keep last 20 lines to avoid unbounded growth

   def update_claude_md_memory(vault_path: str, title: str, domain: str, summary: str):
       text = CLAUDE_MD.read_text(encoding='utf-8')
       # Find or create the section
       if SECTION_HEADER not in text:
           text += f'\n\n{SECTION_HEADER}\n'
       # Build new entry line
       ts = datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d')
       entry = f'- {ts} [{domain}] **{title}** — {summary} (`{vault_path}`)'
       # Insert after header, keep only MAX_ENTRIES
       lines = text.splitlines()
       header_idx = next(i for i, l in enumerate(lines) if l.strip() == SECTION_HEADER)
       # Collect existing entries
       entry_lines = [l for l in lines[header_idx+1:] if l.startswith('- ')]
       entry_lines = [entry] + entry_lines  # newest first
       entry_lines = entry_lines[:MAX_ENTRIES]
       # Reconstruct
       before = lines[:header_idx+1]
       after_start = next((i for i in range(header_idx+1, len(lines)) if lines[i].startswith('## ') and i > header_idx), len(lines))
       after = lines[after_start:]
       new_text = '\n'.join(before + entry_lines + ([''] if after else []) + after)
       CLAUDE_MD.write_text(new_text, encoding='utf-8')

3. The one_line_summary should come from the vault writer — it already has the note content; pass the first non-empty sentence after frontmatter (slice [:200]).

4. Also register this as a Claude Code post-tool-use hook in .claude/settings.json if the project uses hooks (check existing hook config). If hooks are already configured, add a 'PostToolUse' entry that fires when the Bash tool writes to the vault directory.

Edge cases:
  - CLAUDE.md doesn't exist yet: create it with the section header
  - Concurrent writes (two vault writes in the same second): use a file lock (fcntl on Linux, msvcrt on Windows) or catch and retry once
  - summary contains newlines: strip and truncate to 200 chars
  - vault_path should be relative to repo root for portability

Verification:
  - Run a manual vault write (trigger the ingestion pipeline on one test URL)
  - cat CLAUDE.md and confirm a new '- YYYY-MM-DD [domain] ...' line appears under '## Recent Knowledge'
  - Run it 25 times with synthetic data; confirm the section never exceeds 20 entries
  - Confirm existing CLAUDE.md content above and below the section is unchanged
```
