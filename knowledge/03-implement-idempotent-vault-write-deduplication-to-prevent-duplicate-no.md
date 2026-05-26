---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-26T03:02:07.112020-07:00
---

# Implement idempotent vault-write deduplication to prevent duplicate notes on re-runs

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

The commit '2026-05-17 fix(db): make record_link idempotent (UPSERT) so retried extractions don't crash' shows the team already hit idempotency bugs at the DB layer. Vault note 'The AI Second Brain Stack' (Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md) emphasizes that a production PKM system must treat the vault as an append-only log with deduplication — otherwise re-runs of the ingestion pipeline create duplicate markdown files that pollute search and synthesis. The vault writer likely uses slug-based filenames but has no content-hash check before writing.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
  - src/  (find the vault writer module — likely src/cortex/vault/ or similar — and any place that calls it)
  - knowledge/  (inspect a few existing notes to understand frontmatter shape, especially any 'source_url' or 'id' fields)

Task: Add content-hash deduplication to the vault writer so re-running ingestion never creates duplicate notes.

Step 1 — Locate the write_note() function (or equivalent) in the vault writer module.

Step 2 — Add a dedup index
  Create a helper load_vault_index(vault_root: Path) -> dict[str, Path] that:
    - Walks vault_root recursively for *.md files.
    - For each file, reads the YAML frontmatter and extracts the 'source_url' field (or 'id' if present).
    - Returns a dict mapping source_url -> file_path.
  Cache this index in a module-level dict so it is only built once per process run.

Step 3 — Guard in write_note()
  Before writing a new file:
    1. Compute a content hash: hashlib.sha256(body.encode()).hexdigest()[:16]
    2. Check if source_url already exists in the vault index.
    3. If it does, compare the stored file's content hash (stored in frontmatter as 'content_hash') with the new hash.
       - If hashes match → skip write, return existing path, log at DEBUG 'vault dedup: skipping unchanged note'.
       - If hashes differ → overwrite the existing file (update in place), log at INFO 'vault dedup: updating changed note'.
    4. If source_url is not in the index → write new file as before, add to in-memory index.

Step 4 — Frontmatter injection
  Ensure every note written by write_note() includes these frontmatter fields:
    content_hash: <sha256[:16]>
    ingested_at: <ISO8601 UTC timestamp>
  Use python-frontmatter (already a dep) to read/write frontmatter cleanly.

Step 5 — Backfill script
  Create scripts/backfill_content_hashes.py that walks the existing vault, computes content_hash for each note that lacks it, and writes it back into the frontmatter in place. This is a one-time migration.

Edge cases:
  - Notes without a source_url (e.g., manually created) → skip dedup check, always allow write.
  - Concurrent writes (two ingestion workers running simultaneously) → use a file lock (filelock package, add to deps) around the index update.
  - Very large vault → load_vault_index should be lazy and only scan once; invalidate if a write occurs.

Verification:
  1. Run the ingestion pipeline twice on the same email/URL; confirm only one vault note exists after the second run.
  2. Modify the source content slightly and re-run; confirm the existing note is updated (not duplicated).
  3. Run `uv run pytest` — no regressions.
  4. Run scripts/backfill_content_hashes.py; confirm all existing notes gain a content_hash frontmatter field.
```
