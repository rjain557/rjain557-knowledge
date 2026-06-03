---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-03T03:01:25.024397-07:00
---

# Add a persistent cross-session memory index so agents stop rediscovering vault context every run

**Impact:** high  ·  **Effort:** M

## Rationale

Vault note Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md states that agents failing in production are doing so because the retrieval system cannot assemble what the agent needs before it starts acting — not because the model is weak. Cortex's nightly refresh commits new knowledge/ files but the agents that consume them (repo-review, synthesis) have no lightweight index to query; they re-read the vault directory listing each run. A simple SQLite FTS5 index over vault frontmatter + first-paragraph would let agents do targeted retrieval in <100 ms instead of scanning hundreds of files.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find vault reader/writer modules, likely src/cortex/vault*.py)
  - sql/  (review any existing schema files)
  - knowledge/  (sample 3-5 .md files to understand frontmatter structure)
  - .gitignore  (confirm *.vec and *.diskann are already ignored)

Task: Build a SQLite FTS5 index over the knowledge vault so agents can retrieve relevant notes by keyword in a single query instead of scanning the filesystem.

Steps:
1. Create sql/vault_fts_schema.sql with:
   CREATE TABLE IF NOT EXISTS vault_notes (
       id INTEGER PRIMARY KEY,
       rel_path TEXT UNIQUE NOT NULL,
       title TEXT,
       tags TEXT,          -- space-separated for FTS tokenisation
       domain TEXT,
       date_added TEXT,
       body_excerpt TEXT   -- first 500 chars of body after frontmatter
   );
   CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
       title, tags, domain, body_excerpt,
       content=vault_notes, content_rowid=id
   );

2. Create src/cortex/vault_index.py with:
   - index_vault(vault_dir: Path, db_path: Path) -> int  — walks vault_dir, parses frontmatter with python-frontmatter (already a dep), upserts into vault_notes, rebuilds FTS triggers. Returns count of notes indexed.
   - search_vault(query: str, db_path: Path, limit: int = 10) -> list[dict]  — runs FTS5 MATCH query, returns list of {rel_path, title, domain, snippet} dicts.
   - A __main__ block: `python -m cortex.vault_index [--reindex] [--search "query"]`

3. Wire index_vault() into the nightly refresh scheduler: after vault writes complete, call index_vault() so the index is always fresh.

4. In the repo-review and synthesis agents, replace the 'read all vault files' step with a search_vault() call using the repo's domain tag as the query, then inject only the top-10 results into the prompt context.

Edge cases:
  - vault_dir may contain non-.md files (images, etc.); skip silently.
  - Frontmatter may be missing or malformed; catch exceptions per file and log a warning, do not abort the full index run.
  - db_path should default to .claude/vault_index.db (already gitignored via .claude/ pattern — verify, add if missing).
  - FTS5 content tables require manual trigger maintenance on UPDATE/DELETE; include the standard fts5 rebuild trigger SQL in the schema file.

Verification:
  - `python -m cortex.vault_index --reindex` should complete without errors and print 'Indexed N notes'.
  - `python -m cortex.vault_index --search 'agent orchestration'` should return ≥3 results with non-empty snippets.
  - Run the repo-review workflow and confirm the log shows 'vault search returned N notes' rather than 'reading vault directory'.
  - `ruff check src/cortex/vault_index.py` must pass clean.
```
