---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: L
generated_at: 2026-06-09T03:01:24.645075-07:00
---

# Pre-compute a persistent knowledge graph index to eliminate per-session vault re-reads

**Impact:** high  ·  **Effort:** L

## Rationale

The Graphify/knowledge-graph vault note (Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md) reports 70× token reduction by pre-indexing a repo into a queryable graph instead of re-reading files every agent session. Cortex already has a large and growing knowledge/ vault; every repo-review and synthesis agent currently re-scans it cold. Building a lightweight graph index (nodes = vault notes, edges = wikilinks + topic tags) would let MCP tools answer 'what do we know about X' with a single graph query instead of a full vault scan.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/quantmind-turns-quant-finance-into-a-queryable-knowledge-gra.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

Context files to read first:
  1. src/ — find the MCP server module and any vault-reading utilities
  2. knowledge/ — sample 10 random .md files to understand frontmatter schema
  3. sql/ — check if a graph table already exists
  4. pyproject.toml — note networkx is NOT yet a dependency

Task: Build a vault knowledge graph that is rebuilt nightly and exposed as an MCP tool.

Steps:
  1. Add `networkx>=3.3` and `rapidfuzz>=3.0` to pyproject.toml dependencies.
  2. Create src/cortex/vault_graph.py:
       - `build_graph(vault_root: Path) -> nx.DiGraph`
         * Walk all .md files, parse frontmatter (python-frontmatter already in deps).
         * Each file = a node with attrs: path, title, tags, date, domain.
         * Parse [[wikilink]] patterns in body text; add directed edges.
         * Parse `tags:` frontmatter list; add tag-cluster edges.
       - `save_graph(g, path: Path)` — serialize with nx.write_graphml.
       - `load_graph(path: Path) -> nx.DiGraph` — deserialize.
       - `query_neighbors(g, slug: str, depth: int = 2) -> list[dict]` — BFS up to depth, return node attr dicts.
  3. Add a nightly APScheduler job (or cron script in scripts/) that calls `build_graph` and saves to `.vault_graph.graphml` (add to .gitignore).
  4. Expose an MCP tool `vault_neighbors(slug, depth)` in the existing MCP server that loads the cached graph and returns the neighbor list as JSON.
  5. Add a CLI entry point: `uv run python -m cortex.vault_graph --rebuild` that prints node/edge counts on completion.

Edge cases:
  - Wikilink targets that don't match any file should be added as 'stub' nodes, not raise errors.
  - The graph file must be rebuilt atomically (write to .vault_graph.graphml.tmp, then rename) so a mid-write crash doesn't corrupt the cache.
  - If the graph file is older than 25 hours, `load_graph` should log a structlog warning.

Verify:
  1. `uv run python -m cortex.vault_graph --rebuild` completes without errors and prints >0 nodes and edges.
  2. Call the MCP tool from Claude Code with a known vault slug and confirm neighbors are returned.
```
