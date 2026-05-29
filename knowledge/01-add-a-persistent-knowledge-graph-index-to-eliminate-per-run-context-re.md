---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-29T03:02:24.194580-07:00
---

# Add a persistent knowledge-graph index to eliminate per-run context rediscovery

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note 'Your AI agent is rediscovering 85% of its context every run' explicitly identifies that agents fail in production because the retrieval system cannot assemble what the agent needs before it starts acting — not because the retrieval method is wrong. The Cortex repo currently relies on vector search alone (*.vec / *.diskann files in .gitignore) with no relational graph layer. Adding a lightweight graph index (e.g. a SQLite adjacency table keyed on vault note slugs + topic tags) would let the deep-research and repo-review agents load only the relevant subgraph rather than re-embedding the entire vault each run, directly addressing the 85% rediscovery problem.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (scan all Python modules, note where embeddings are generated and where vault notes are queried)
  - sql/  (read all .sql files to understand current schema)
  - knowledge/  (sample 5-10 .md files to understand frontmatter structure: title, tags, topic, path)
  - CLAUDE.md
  - pyproject.toml

Task: Implement a lightweight knowledge-graph adjacency layer on top of the existing SQL Server schema.

Specific changes:
1. In sql/, create a new migration file `004_knowledge_graph.sql` that adds two tables:
   - `kg_nodes (node_id INT PK, vault_path NVARCHAR(500) UNIQUE, slug NVARCHAR(200), title NVARCHAR(500), domain NVARCHAR(100), inserted_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET())`
   - `kg_edges (edge_id INT PK, src_node_id INT FK->kg_nodes, dst_node_id INT FK->kg_nodes, edge_type NVARCHAR(50), weight FLOAT DEFAULT 1.0, created_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(), UNIQUE(src_node_id, dst_node_id, edge_type))`
   Edge types to support: 'cites', 'same_topic', 'synthesized_from', 'related_embedding' (top-k cosine neighbours stored at write time).

2. In src/, create `src/cortex/graph/builder.py` with:
   - `upsert_node(conn, vault_path, slug, title, domain) -> int`  — idempotent MERGE on vault_path
   - `upsert_edge(conn, src_path, dst_path, edge_type, weight=1.0)` — idempotent MERGE on (src, dst, type)
   - `build_same_topic_edges(conn)` — reads all kg_nodes, groups by domain, writes same_topic edges for nodes sharing a domain tag
   - `build_embedding_edges(conn, top_k=5)` — reads existing embedding vectors from whatever table currently stores them, computes cosine similarity, writes top_k 'related_embedding' edges per node

3. In src/, create `src/cortex/graph/query.py` with:
   - `get_subgraph(conn, seed_paths: list[str], hops: int = 2) -> list[dict]`  — BFS from seed nodes up to `hops` edges, returns list of {vault_path, title, domain, edge_type, weight}
   - `get_top_neighbours(conn, vault_path: str, edge_type: str = None, limit: int = 10) -> list[dict]`

4. Wire `build_same_topic_edges` and `build_embedding_edges` into the existing nightly lint / synthesis scheduler (find the APScheduler job in src/ that runs nightly and add a `rebuild_graph` step after vault lint completes).

Edge cases to handle:
  - vault_path may contain Unicode (NVARCHAR, not VARCHAR)
  - Nodes may be deleted from the vault; add a `prune_orphan_nodes(conn)` function that DELETEs kg_nodes whose vault_path no longer exists on disk
  - If the embeddings table doesn't yet have vectors for a note, skip that note in build_embedding_edges without crashing
  - All DB calls must use the existing connection/pool pattern already in src/ (do not introduce a new connection library)

Verification:
  - Run `python -m pytest tests/ -k graph` after adding at least two unit tests in `tests/test_graph.py`:
    * test that upsert_node is idempotent (call twice, assert row count = 1)
    * test that get_subgraph returns seed node itself when hops=0
  - Manually run `python -c "from cortex.graph.builder import build_same_topic_edges; ..."` against a local DB and confirm kg_edges is populated
  - Check that the nightly scheduler job list printed at startup includes 'rebuild_graph'
```
