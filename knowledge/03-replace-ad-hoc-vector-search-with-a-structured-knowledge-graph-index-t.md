---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: L (>1 week)
generated_at: 2026-06-05T03:01:49.857565-07:00
---

# Replace ad-hoc vector search with a structured knowledge-graph index to eliminate per-run context rediscovery

**Impact:** high  ·  **Effort:** L (>1 week)

## Rationale

Vault note [3] ('Your AI agent is rediscovering 85% of its context every run') argues that vector search alone cannot assemble what an agent needs before it starts acting — it finds semantically similar chunks but cannot traverse relationships. Vault note [9] ('Persistent-Memory AI Brains') and note [2] (Graphify/Claude Code knowledge graphs) both describe pre-computing a persistent relational graph so agents query typed relationships rather than raw embeddings. The .gitignore already excludes `*.vec` and `*.diskann` files, confirming a vector index exists but is regenerated each run — exactly the stateless cold-start problem these notes diagnose.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md
- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context to read first:
1. src/ — find the vector indexing code (look for *.vec, *.diskann references, embedding calls, similarity search)
2. sql/ — understand the existing SQL Server schema; look for any existing link or relationship tables
3. knowledge/ — sample 5 notes to understand frontmatter fields (especially tags, related, category)
4. CLAUDE.md — understand how the MCP server exposes vault search to agents

Task: Augment the existing vector search with a lightweight persistent knowledge graph stored in SQL Server, so agents can traverse typed relationships without re-embedding on every run.

Phase 1 — Schema (do this first, get it reviewed before Phase 2):
1. Create `sql/knowledge_graph.sql` with three tables:
   - `kg_nodes(id INT PK, note_slug NVARCHAR(500) UNIQUE, title NVARCHAR(1000), category NVARCHAR(200), last_updated DATETIME2)`
   - `kg_edges(id INT PK, from_slug NVARCHAR(500), to_slug NVARCHAR(500), edge_type NVARCHAR(100), weight FLOAT DEFAULT 1.0, created_at DATETIME2)` — edge_type values: 'wikilink', 'tag_cooccurrence', 'llm_inferred'
   - `kg_node_tags(note_slug NVARCHAR(500), tag NVARCHAR(200))` for fast tag-based traversal
2. Add appropriate indexes on (from_slug, edge_type) and (tag).

Phase 2 — Graph builder script:
1. Create `scripts/build_knowledge_graph.py`
2. Parse all `knowledge/**/*.md` files using `python-frontmatter`
3. For each note: upsert a `kg_nodes` row
4. Extract `[[wikilink]]` patterns from note body → insert `kg_edges` with edge_type='wikilink'
5. For notes sharing ≥2 tags → insert `kg_edges` with edge_type='tag_cooccurrence', weight = number of shared tags
6. Run incrementally: only process notes whose mtime is newer than their `kg_nodes.last_updated`

Phase 3 — MCP tool exposure:
1. Add a `graph_neighbors(slug: str, edge_types: list[str], depth: int = 1)` tool to the existing FastMCP server in src/
2. The tool should return a list of `{slug, title, edge_type, weight}` dicts for all nodes reachable within `depth` hops
3. Add a `graph_path(from_slug: str, to_slug: str)` tool that returns the shortest path between two notes

Edge cases:
- Wikilinks to non-existent notes should create a stub kg_nodes row with `category='stub'` rather than failing
- Circular links are valid; the traversal tools must handle cycles (use visited set)
- If SQL Server is unavailable, the MCP tools must return an error dict rather than raising an unhandled exception

Verification:
1. Run `python scripts/build_knowledge_graph.py` and confirm rows appear in kg_nodes and kg_edges
2. Call the `graph_neighbors` MCP tool for a note you know has wikilinks and confirm the linked notes are returned
3. Run the script twice and confirm the second run is faster (incremental) and row counts don't duplicate
```
