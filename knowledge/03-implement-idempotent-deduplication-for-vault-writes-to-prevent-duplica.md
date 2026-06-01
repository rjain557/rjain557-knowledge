---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-06-01T03:01:55.850017-07:00
---

# Implement idempotent deduplication for vault writes to prevent duplicate knowledge notes accumulating

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

The commit log shows daily 'Knowledge refresh' commits every single day (2026-05-24 through 2026-05-31), each adding improvement prompts. Vault note [4] (LLM Wiki / AI Second Brain stack) specifically warns that without a deduplication layer, the vault becomes a filing cabinet of redundant entries rather than a compounding knowledge surface. Currently there is no evidence of content-hash or URL-based deduplication before writing new notes — the nightly lint (added 2026-05-20) catches structural issues but not semantic duplicates. Adding a SHA-256 content hash stored in frontmatter and checked before write would prevent the vault from bloating with near-identical daily refresh notes.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md
- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the vault writer — likely src/cortex/vault/ or src/cortex/writer.py)
  - knowledge/  (inspect 3-5 recent .md files to see current frontmatter fields)
  - sql/  (check if there is a links/sources table that could store hashes)

Task: Add content-hash deduplication to the vault writer.

1. Find the function/class responsible for writing new .md notes to the vault (search for `python-frontmatter` usage or `open(..., 'w')` calls that write to knowledge/ or Topics/).

2. In that writer, before writing a new note:
   a. Compute SHA-256 of the note body (exclude frontmatter from the hash so metadata updates don't count as new content):
      import hashlib
      body_hash = hashlib.sha256(body_text.encode('utf-8')).hexdigest()[:16]
   b. Add `content_hash: {body_hash}` to the frontmatter dict.
   c. Before writing, scan existing notes in the target directory for any file whose frontmatter `content_hash` matches. Use python-frontmatter to load each file lazily (check frontmatter only, not full body).
   d. If a match is found, log via structlog at WARNING level: 'Skipping duplicate note: {new_title} matches {existing_path}' and return without writing.
   e. Also check for URL-based duplicates: if frontmatter contains a `url` field, skip if any existing note has the same `url`.

3. To avoid scanning the entire vault on every write, maintain a lightweight in-memory dict (populated once at startup from a single pass) mapping content_hash -> path and url -> path. Persist this index to config/vault_index.json and update it on each successful write.

4. Add a CLI command `cortex-reindex` that rebuilds config/vault_index.json from scratch by scanning all vault files — useful after manual edits.

Edge cases:
  - Notes with no body (only frontmatter) should use hash of empty string.
  - If config/vault_index.json is corrupted/missing, fall back to full scan and rebuild.
  - Thread safety: if multiple writers run concurrently, use a file lock (use `fcntl` on Linux or a .lock file) around the index update.

Verification:
  - Write a test note, then attempt to write an identical note body. Confirm the second write is skipped and logged.
  - Confirm config/vault_index.json exists and contains the correct hash after the first write.
  - Run `cortex-reindex` and confirm the index matches the actual vault contents.
```
