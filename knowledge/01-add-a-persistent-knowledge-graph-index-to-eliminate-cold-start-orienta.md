---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: L (>1 week)
generated_at: 2026-05-26T03:02:07.112020-07:00
---

# Add a persistent knowledge-graph index to eliminate cold-start orientation cost

**Impact:** high  ·  **Effort:** L (>1 week)

## Rationale

Vault note 'Knowledge Graphs as Codebase Memory' (Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md) documents that the dominant bottleneck in agent orchestration is orientation cost — tokens burned re-reading the repo before any useful action. Cortex already has a vector store for semantic search, but the commit history shows every repo-review run re-reads the same source files from scratch. A pre-computed, persisted graph of vault nodes + code modules (entities, relationships, file-to-file links) would let the MCP server answer structural queries in one hop instead of scanning hundreds of markdown files.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
  - src/  (full tree — understand current MCP server, vault writer, and vector-search modules)
  - knowledge/  (sample vault notes to understand node shape)
  - pyproject.toml  (available deps)
  - CLAUDE.md

Task: Implement a lightweight persistent knowledge graph that indexes the vault and is queryable by the MCP server.

Step 1 — Schema design
  Create src/cortex/graph/schema.py defining two dataclasses:
    Node(id: str, type: Literal['vault_note','source','topic','code_module'], path: str, title: str, tags: list[str])
    Edge(src: str, dst: str, rel: Literal['links_to','synthesized_from','cites','related_to'])

Step 2 — Builder
  Create src/cortex/graph/builder.py with build_graph(vault_root: Path) -> tuple[list[Node], list[Edge]].
  - Parse every .md file's YAML frontmatter (python-frontmatter is already a dep) to extract title, tags, and [[wikilinks]].
  - Emit a Node per file and an Edge for every [[wikilink]] that resolves to another vault file.
  - Persist the result as two JSON-lines files: .cortex_graph/nodes.jsonl and .cortex_graph/edges.jsonl (add both to .gitignore).

Step 3 — Incremental refresh
  Add a refresh_graph() function that only re-processes files whose mtime is newer than the last build timestamp stored in .cortex_graph/meta.json.

Step 4 — MCP tool
  In the existing MCP server (find it under src/), register a new tool graph_neighbors(node_id: str, depth: int = 1) -> list[Node] that loads the persisted graph and returns BFS neighbors. Also add graph_search(query: str) -> list[Node] that filters nodes by title/tag substring.

Step 5 — Wire into repo-review
  In the repo-review script (scripts/ or src/), call refresh_graph() once at startup, then use graph_neighbors() to pre-load relevant vault context before calling Claude, instead of globbing all .md files.

Edge cases:
  - Broken wikilinks (target file doesn't exist) → log a warning, skip the edge, don't crash.
  - Circular links → BFS visited-set prevents infinite loops.
  - Very large vaults (>10k files) → builder should stream JSONL, not hold everything in RAM.

Verification:
  1. Run `python -m cortex.graph.builder` from repo root; confirm .cortex_graph/nodes.jsonl and edges.jsonl are created.
  2. Start the MCP server and call graph_neighbors with a known vault note ID; confirm it returns linked notes.
  3. Run the repo-review script end-to-end; confirm it completes without reading every .md file via glob.
```
