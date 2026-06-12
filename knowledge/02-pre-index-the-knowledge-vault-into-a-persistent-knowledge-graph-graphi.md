---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: L (>1 week)
generated_at: 2026-06-12T03:01:20.219071-07:00
---

# Pre-index the knowledge vault into a persistent knowledge graph (Graphify pattern)

**Impact:** high  ·  **Effort:** L (>1 week)

## Rationale

Three vault notes (Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md, Topics/graphify-x-claude-os.md, Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md) all converge on the same finding: the biggest cost in agent-orchestration systems is re-reading the corpus from scratch each session. The notes describe Graphify's approach — pre-computing a queryable graph of entities and relationships — as achieving 70× token reduction on large projects. Cortex's vault already has hundreds of notes and grows daily; without a graph index, every synthesis pass re-reads raw Markdown, burning tokens and missing cross-note links.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/graphify-x-claude-os.md
- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - knowledge/  (browse top-level structure — note categories and frontmatter schema)
  - src/  (find the synthesis and lint modules)
  - CLAUDE.md
  - docs/  (any existing architecture docs)

Task:
Build a lightweight knowledge-graph index over the vault that the synthesis agent can query instead of re-reading raw Markdown.

Phase 1 — Schema & extraction (this session):
1. Create src/cortex/graph/ package with:
   - models.py: Pydantic models for Node(id, type, title, path, tags, summary) and Edge(src, dst, relation).
   - extractor.py: reads every .md file in knowledge/, parses YAML frontmatter, extracts title/tags/categories, then calls Claude (claude-haiku for cost) with a short prompt to extract up to 5 named entities and 3 relationships per note. Writes results to a SQLite DB at data/cortex_graph.db (tables: nodes, edges).
2. Create scripts/build_graph.py that runs extractor.py over the full vault and prints a summary (node count, edge count).

Phase 2 — Query interface:
3. Add graph/query.py with:
   - `find_related(title: str, hops: int = 2) -> list[Node]`: BFS over edges table.
   - `search_by_tag(tag: str) -> list[Node]`.
4. Modify the synthesis module to call `find_related` to seed its context window instead of globbing all Markdown files.

Edge cases:
  - Notes with missing frontmatter must be handled gracefully (log warning, skip).
  - Incremental updates: extractor should only re-process notes whose file mtime > last_indexed timestamp stored in the DB.
  - data/cortex_graph.db must be added to .gitignore (it's regeneratable).

Verify:
  - `uv run python scripts/build_graph.py` completes without errors and prints >0 nodes.
  - `uv run python -c "from src.cortex.graph.query import find_related; print(find_related('agent-orchestration'))"` returns a non-empty list.
  - Synthesis script runs faster (measure wall time before/after with `time`).
```
