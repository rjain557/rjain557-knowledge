---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-08T03:01:24.415428-07:00
---

# Implement active memory linking: auto-tag new vault notes with related existing notes at write time

**Impact:** high  ·  **Effort:** M

## Rationale

The 'AI Second Brain Stack' and 'Neuromorphic Active Memory' vault notes both identify the same failure mode: vaults accumulate notes that never get linked, so the knowledge graph stays sparse and retrieval degrades over time. Cortex already writes notes daily but the .gitignore shows no link-maintenance artifact. Adding a post-write hook that embeds the new note, finds the top-5 nearest existing notes by cosine similarity, and injects a 'Related:' frontmatter list would turn the vault from a filing cabinet into the active reasoning surface the system is designed to be.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md
- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the vault writer module — look for files that call python-frontmatter or write .md files to knowledge/)
  - knowledge/  (sample 3-5 existing notes to understand frontmatter schema)
  - pyproject.toml  (confirm sentence-transformers or similar is available; if not, we'll use the Anthropic embeddings API)

Task: Add an auto-linker that runs immediately after any new note is written to the vault.

Steps:
1. Create src/cortex/vault_linker.py:
   - Function `embed_text(text: str) -> list[float]`: calls the Anthropic embeddings endpoint (model: `voyage-3`) or falls back to a local sentence-transformers model if the key is absent. Cache embeddings in a simple shelve DB at .claude/vault_embeddings.db keyed by note slug + mtime.
   - Function `find_related(new_note_path: str, vault_dir: str, top_k: int = 5) -> list[str]`: embeds the new note's title + first 500 chars of body, computes cosine similarity against all cached embeddings, returns top_k note slugs (excluding self).
   - Function `inject_related_links(note_path: str, related_slugs: list[str]) -> None`: opens the note with python-frontmatter, adds/updates a `related` key in frontmatter as a list of wiki-link strings (`[[slug]]`), writes back. If `related` already exists, merge (deduplicate) rather than overwrite.
2. In the existing vault writer (wherever notes are saved to disk), call `inject_related_links` immediately after the file is written. Import lazily so the vault writer still works if vault_linker deps are missing.
3. Add a CLI entry point in scripts/relink_vault.py that iterates all existing notes and back-fills related links (for the existing corpus). This is a one-time migration + can be re-run safely.
4. Add VOYAGE_API_KEY (or ANTHROPIC_API_KEY note) to .env.example with a comment.

Edge cases:
  - New vault with zero existing notes: find_related should return [] gracefully.
  - Notes with no body text (just frontmatter): embed the title only.
  - The shelve cache must be invalidated when a note's mtime changes (re-embed on change).
  - inject_related_links must be idempotent: running twice on the same note produces the same frontmatter.
  - Do not add self-links.

Verification:
  - `uv run python scripts/relink_vault.py --dry-run` prints proposed links without writing.
  - `uv run python scripts/relink_vault.py` completes and at least one existing note in knowledge/ gains a `related:` frontmatter key.
  - `uv run python -c "from src.cortex.vault_linker import find_related; print(find_related('knowledge/some_note.md', 'knowledge', top_k=3))"` returns a list of 3 slugs.
  - `uv run ruff check src/cortex/vault_linker.py scripts/relink_vault.py` passes.
```
