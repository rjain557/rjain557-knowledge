---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S
generated_at: 2026-06-11T03:01:26.483504-07:00
---

# Implement idempotent deduplication guard for vault writer to prevent duplicate notes

**Impact:** medium  ·  **Effort:** S

## Rationale

The pipeline ingests articles via multiple extractors (trafilatura, feedparser, YouTube, arxiv) on a daily schedule. There is no evidence in the visible code or commit history of a content-hash or URL-based deduplication check before writing to the vault — only the SQL `record_link` UPSERT (fixed 2026-05-17) guards the DB layer. The vault note 'The AI Second Brain Stack' (Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md) explicitly calls out that production PKM systems require deduplication at the write layer, not just the DB layer, to prevent the vault from accumulating near-duplicate notes that degrade synthesis quality.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the vault writer module — look for python-frontmatter usage, slug generation, and any write_note / save_note functions)
  - sql/  (review schema to understand what columns record_link stores — especially url/slug)
  - knowledge/  (spot-check a few .md files to see frontmatter shape: url, slug, title fields)

Task:
Add a two-layer deduplication guard to the vault writer so a note is never written if an equivalent already exists.

1. URL-based check (fast path):
   In the vault writer's write function, before creating the file:
   a. Compute the expected slug from the source URL (same logic already used for filenames).
   b. Check if `knowledge/Inbox/{slug}.md` or `knowledge/Topics/{slug}.md` already exists.
   c. If it exists, log `structlog.info('vault.skip_duplicate', slug=slug, reason='file_exists')` and return early.

2. Content-hash check (slow path, catches URL variations):
   a. Compute `hashlib.sha256(body_text.encode()).hexdigest()[:16]` where body_text is the extracted article body before LLM processing.
   b. Maintain a lightweight manifest at `.cache/vault_hashes.json` mapping hash -> slug.
   c. On write: if hash already in manifest, skip and log. On successful write: add hash -> slug to manifest and persist.

3. Add a helper `cortex.vault.dedup.is_duplicate(url: str, body: str) -> tuple[bool, str]` that encapsulates both checks and returns (is_dup, reason).

Edge cases:
  - .cache/vault_hashes.json must be in .gitignore (add if absent).
  - Concurrent writes (APScheduler may fire overlapping jobs): use a file lock (fcntl or portalocker) around manifest read-modify-write.
  - If manifest is corrupt, rebuild it by scanning existing vault files' frontmatter for a `content_hash` field (add that field to frontmatter on new writes).

Verify:
  - Write a unit test in tests/ that calls write_note twice with the same URL; assert the second call returns early and the vault directory contains exactly one file.
  - Run `uv run pytest tests/ -k dedup -v` and confirm it passes.
```
