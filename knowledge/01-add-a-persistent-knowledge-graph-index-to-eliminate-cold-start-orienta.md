---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-28T03:02:17.091238-07:00
---

# Add a persistent knowledge-graph index to eliminate cold-start orientation cost

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note 'Knowledge Graphs as Codebase Memory' (Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md) documents that the dominant bottleneck in agentic systems is orientation cost — tokens burned re-reading the repo before useful work begins, with pre-computed graph indexes reducing token consumption by reported 70×. Cortex's own CLAUDE.md and repo-review workflow re-read the vault on every run with no persistent structural index, meaning every Claude Code session pays full orientation cost. Adding a lightweight adjacency/topic graph (JSON or SQLite) that maps vault note paths to topics, backlinks, and embedding clusters would let the repo-review agent and deep-research agent jump directly to relevant nodes.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - CLAUDE.md
  - src/ (scan all .py files for vault read/write paths)
  - knowledge/ (note the directory structure and any existing index files)
  - scripts/ (look for any existing indexing or lint scripts)

Task: Build a lightweight vault knowledge-graph index.

1. Create `src/cortex/vault_graph.py` with a `VaultGraph` class that:
   a. Walks `knowledge/` recursively, reads YAML frontmatter (python-frontmatter is already a dependency) from every .md file.
   b. Extracts: file path, `tags` list, `topic` field, all `[[wikilink]]` references found in the body via regex `r'\[\[([^\]]+)\]\]'`.
   c. Builds an in-memory dict: `{slug: {"path": str, "tags": list, "links_to": list[slug], "linked_from": list[slug]}}`.
   d. Persists to `knowledge/_graph.json` (pretty-printed, sorted keys) so it is human-readable and git-diffable.
   e. Exposes a `query(topic: str) -> list[str]` method that returns the 10 most relevant note paths by tag/topic substring match.

2. Add a CLI entry point in `scripts/build_graph.py`:
   ```python
   from cortex.vault_graph import VaultGraph
   VaultGraph().build().save()
   ```

3. Wire `build_graph.py` into the existing nightly/hourly scheduler (check `src/cortex/scheduler.py` or equivalent) so the graph rebuilds after every vault-write batch.

4. Update `CLAUDE.md` with a one-paragraph note: 'Before starting any repo-review or deep-research run, read `knowledge/_graph.json` to orient to existing vault structure rather than walking the full directory tree.'

Edge cases:
  - Notes with no frontmatter: skip gracefully, log a warning via structlog.
  - Circular wikilinks: the dict structure handles these naturally; no special handling needed.
  - Very large vaults (>5 000 notes): use `pathlib.Path.rglob` with a generator, don't load all content into memory at once.

Verification:
  - Run `python scripts/build_graph.py` and confirm `knowledge/_graph.json` is created.
  - Assert the JSON contains at least one entry with non-empty `links_to` or `linked_from`.
  - Run `python -c "from cortex.vault_graph import VaultGraph; print(VaultGraph().load().query('agent-orchestration'))"` and confirm it returns a non-empty list.
```
