---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-10T03:01:20.668814-07:00
---

# Implement active cross-note linking in the vault writer to replace passive file storage

**Impact:** high  ·  **Effort:** M

## Rationale

The vault notes on neuromorphic/active memory (Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md) and the LLM wiki pattern (Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md) both emphasize that a vault without automatic cross-linking is just a filing cabinet — agents start cold every session. Cortex's commit history shows a Karpathy LLM-Wiki pattern was added (2026-05-20) but the nightly lint step likely only checks frontmatter, not semantic backlinks. Adding an auto-linker that injects `[[wikilinks]]` based on shared entities would turn the vault into an active reasoning surface.

## Cited evidence

- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md
- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

Files to read first:
  1. src/  — find the vault writer module (look for *vault*, *writer*, *note*)
  2. scripts/  — find the nightly lint script
  3. knowledge/  — inspect 3-5 existing note files to understand frontmatter schema and whether [[wikilinks]] are already present
  4. CLAUDE.md  — understand the synthesis/lint pipeline

Change to make:
  Create src/cortex/vault_linker.py with a function `inject_backlinks(vault_dir: Path) -> dict[str, int]`:
  1. Load all .md files under vault_dir into memory, extracting:
       - The note's slug (filename without .md)
       - Its frontmatter `title` and `categories` fields
       - Its full body text
  2. Build an entity index: for each note, collect noun phrases that appear as titles or slugs of OTHER notes (simple substring match is fine for v1; no NLP dependency needed).
  3. For each note body, find the first occurrence of each entity string that is NOT already inside a [[...]] link and replace it with [[slug|entity_text]].
  4. Write the modified file back only if changes were made; return a dict of {filepath: num_links_added}.
  5. Never modify frontmatter — only the body below the second `---`.

  Wire it into the nightly lint script:
  6. After existing lint checks, call inject_backlinks(Path('knowledge')) and log the summary dict via structlog.

Edge cases:
  - A note must not link to itself.
  - Only inject a link on the FIRST occurrence per note to avoid over-linking.
  - If a slug contains special regex characters, escape them before matching.
  - Dry-run mode: accept a `--dry-run` flag that prints changes without writing.

How to verify:
  1. `python -m cortex.vault_linker --dry-run knowledge/` prints at least one proposed link injection without modifying any file.
  2. Run without --dry-run on a test copy of two notes where one mentions the other's title; confirm [[wikilink]] appears in the output file.
  3. `uv run pytest tests/ -x` still passes.
```
