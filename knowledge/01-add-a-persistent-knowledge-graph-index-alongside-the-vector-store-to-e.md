---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: L (>1 week)
generated_at: 2026-05-31T03:02:02.165089-07:00
---

# Add a persistent knowledge-graph index alongside the vector store to eliminate per-run re-orientation cost

**Impact:** high  ·  **Effort:** L (>1 week)

## Rationale

Vault note 'Claude Code just got a huge upgrade' (Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md) documents that the dominant bottleneck in agent-orchestration systems is orientation cost — tokens burned re-reading the codebase before acting — and that pre-computing a queryable knowledge graph (e.g. via Graphify) cuts token consumption by 70× or more. Cortex currently relies solely on vector similarity search (*.vec / *.diskann files per .gitignore), which finds semantically close nodes but cannot traverse typed relationships (e.g. 'synthesized-from', 'contradicts', 'depends-on') that the nightly lint and cross-page synth pipeline already implies. Adding a lightweight graph layer (networkx persisted to JSON-LD, or a local SQLite adjacency table) would let the repo-review and deep-research agents load only the relevant subgraph rather than re-embedding the entire vault each run.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
1. src/ — scan all Python modules, especially anything touching the vault, embeddings, or deep-research pipeline
2. knowledge/ — look at 2-3 representative Markdown files to understand frontmatter schema (title, tags, url, date, related)
3. sql/ — review the DB schema to understand what link/source tables already exist
4. pyproject.toml — confirm available dependencies
5. .gitignore — note that *.vec and *.diskann are already excluded (vector index files)

Task: Implement a lightweight knowledge-graph layer that is built incrementally alongside the existing vector index.

Step 1 — Design the graph schema:
- Nodes: each vault note identified by its slug (derived from filename)
- Edge types: SYNTHESIZED_FROM (deep-research output → source Inbox notes), RELATED_TO (explicit frontmatter 'related:' links), CONTRADICTS (to be inferred later), TOPIC_OF (note → tag)
- Storage: a single SQLite table `kg_edges(src_slug TEXT, rel TEXT, dst_slug TEXT, weight REAL, updated_at TEXT)` — add this to sql/schema.sql or a new sql/kg_schema.sql

Step 2 — Write src/cortex/kg_builder.py:
- Function `build_graph_from_vault(vault_root: Path) -> None` that walks all .md files, parses frontmatter with python-frontmatter, extracts 'related', 'url', and 'tags' fields, and upserts edges into the SQLite kg_edges table
- Function `get_subgraph(slug: str, depth: int = 2) -> list[dict]` that returns all nodes within `depth` hops of `slug` — this is what agents will call instead of full vault scans
- Use only stdlib + python-frontmatter + pyodbc/sqlite3 (already in deps)

Step 3 — Wire into the nightly pipeline:
- Find the scheduler entry point (likely in src/ or scripts/) that runs the nightly lint/synth
- After the synth step completes, call `build_graph_from_vault()` to refresh the graph
- Log how many edges were added/updated using structlog

Step 4 — Expose via MCP:
- In the existing MCP server (fastmcp), add a tool `get_related_context(slug: str, depth: int = 2)` that calls `get_subgraph()` and returns a compact JSON list of {slug, title, rel, weight}
- This lets Claude Code agents call one tool instead of doing repeated vector searches

Edge cases:
- Vault notes with no frontmatter: skip gracefully, log a warning
- Circular references: the adjacency query must use a visited set
- Slugs with special characters: normalize using the existing slugify dependency
- The graph rebuild must be idempotent (DELETE + INSERT or UPSERT on src+rel+dst primary key)

Verification:
1. Run `python -m cortex.kg_builder` (or equivalent entry point) against the live knowledge/ directory
2. Query the SQLite DB: `SELECT rel, COUNT(*) FROM kg_edges GROUP BY rel;` — should show non-zero counts for RELATED_TO and TOPIC_OF
3. Call the MCP tool with a known slug and confirm it returns ≥1 related note
4. Run the full nightly pipeline end-to-end and confirm no regressions in existing vector search
```
