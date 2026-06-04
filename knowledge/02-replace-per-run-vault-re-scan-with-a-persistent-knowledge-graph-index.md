---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: L
generated_at: 2026-06-04T03:01:21.721962-07:00
---

# Replace per-run vault re-scan with a persistent knowledge-graph index

**Impact:** high  ·  **Effort:** L

## Rationale

Vault notes [1] (Graphify/structural pre-indexing) and [4] (85% context rediscovery) both identify the same root cause: agents re-read and re-embed the entire knowledge base every session, burning tokens on orientation rather than reasoning. The commit history shows daily knowledge refreshes committing directly to main, meaning the vault grows continuously. Without a pre-computed graph index, every Claude Code session that touches the vault pays full re-scan cost. Building a lightweight SQLite-backed entity/link graph (nodes = vault notes, edges = wikilinks + semantic similarity) and exposing it via the existing MCP server would cut per-session token cost dramatically.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the MCP server module and any existing vector/embedding code)
  - sql/  (existing schema files)
  - knowledge/  (sample vault notes to understand frontmatter structure)
  - pyproject.toml

Task: Build a persistent knowledge-graph index over the vault and expose it through the MCP server.

Phase 1 — Schema (sql/knowledge_graph.sql):
  CREATE TABLE kg_nodes (
    id TEXT PRIMARY KEY,          -- slug from frontmatter
    title TEXT,
    domain TEXT,
    path TEXT,
    embedding_sha TEXT,           -- sha256 of content, for change detection
    updated_at DATETIME
  );
  CREATE TABLE kg_edges (
    src TEXT, dst TEXT, edge_type TEXT,  -- 'wikilink' | 'semantic'
    weight REAL,
    PRIMARY KEY (src, dst, edge_type)
  );

Phase 2 — Indexer (src/cortex/kg_indexer.py):
  - Walk knowledge/ recursively, parse frontmatter with python-frontmatter.
  - For each note: upsert kg_nodes; skip if embedding_sha unchanged.
  - Extract [[wikilinks]] via regex; insert kg_edges with edge_type='wikilink'.
  - For semantic edges: embed changed notes (reuse existing embedding client), find top-5 cosine neighbours above 0.75, insert kg_edges with edge_type='semantic'.
  - Expose a CLI entry point: `uv run python -m cortex.kg_indexer --vault knowledge/`.

Phase 3 — MCP tool:
  - In the existing MCP server file, add tool `graph_neighbors(node_id: str, depth: int = 1) -> list[dict]`.
  - Returns nodes reachable within `depth` hops, sorted by edge weight descending.
  - Add tool `graph_search(query: str, top_k: int = 10) -> list[dict]` that does embedding lookup against kg_nodes.

Edge cases:
  - Vault notes with missing frontmatter slug: fall back to filename stem.
  - Circular wikilinks must not cause infinite loops in BFS.
  - Index must be safe to run concurrently with vault writes (use WAL mode on SQLite).

Verify:
  - `uv run python -m cortex.kg_indexer --vault knowledge/` completes without error on current vault.
  - `uv run pytest tests/test_kg_indexer.py -v` covers: node upsert, wikilink extraction, semantic edge insertion, MCP tool response shape.
```
