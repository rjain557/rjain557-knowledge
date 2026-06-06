---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: L (>1 week)
generated_at: 2026-06-06T03:01:40.266571-07:00
---

# Build a persistent knowledge-graph index over the vault to replace linear vector search

**Impact:** high  ·  **Effort:** L (>1 week)

## Rationale

Vault notes [1] (Graphify / structural pre-indexing) and [9] (persistent-memory AI brains with knowledge-graph retrieval) both document that flat vector similarity search burns tokens re-orienting the agent each session and misses multi-hop relationships. Cortex already has a vector index (*.vec / *.diskann in .gitignore) but no graph layer, so cross-note synthesis (added 2026-05-20) cannot follow entity links — it can only find nearest neighbours by embedding distance.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/cortex/vault/ (all files)
  - src/cortex/search/ or src/cortex/retrieval/ (all files, whichever exists)
  - knowledge/ (list top-level dirs only, do not read every note)
  - CLAUDE.md
  - docs/ (list files)

Task: Add a lightweight knowledge-graph layer on top of the existing vault so that cross-note synthesis and MCP queries can traverse entity relationships, not just cosine distance.

Design:
1. Create src/cortex/graph/builder.py:
   a. Walk every .md file in knowledge/.
   b. Extract: (i) the note's slug/title as a node, (ii) all [[wikilinks]] as directed edges, (iii) YAML front-matter tags as node labels.
   c. Persist the graph as a SQLite DB at .cortex_graph.db (add to .gitignore) using two tables: nodes(id TEXT PK, title TEXT, path TEXT, tags JSON) and edges(src TEXT, dst TEXT, rel TEXT).
2. Create src/cortex/graph/query.py with:
   a. neighbors(node_id, depth=2) -> list[Node]
   b. shortest_path(src_id, dst_id) -> list[Node]
   c. subgraph_for_query(query_text, seed_nodes: list[str]) -> list[Node]  — combine vector top-k seeds with 1-hop graph expansion.
3. Wire subgraph_for_query into the existing synthesis pipeline so that when a synthesis job runs for a topic, it receives both vector-similar notes AND their graph neighbours as context.
4. Add a CLI entry point: `python -m cortex.graph.builder --rebuild` that regenerates the DB from scratch (safe to re-run).
5. Expose a graph_neighbors MCP tool in the FastMCP server so Claude Code sessions can call it.

Edge cases:
  - Wikilinks that point to non-existent notes should create a stub node marked missing=true, not crash.
  - Circular links are valid; use visited-set in traversal.
  - The builder must be idempotent (UPSERT, not INSERT) so incremental vault writes don't require full rebuilds.

Verification:
  - `python -m cortex.graph.builder --rebuild` completes without error on the current knowledge/ directory.
  - `python -m pytest tests/graph/ -x` (create at least 2 unit tests: one for neighbor traversal, one for missing-link stub creation).
  - Run `ruff check src/cortex/graph/` with zero errors.
```
