---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-24T07:12:31.038902-07:00
---

# Add a persistent knowledge-graph index to eliminate per-session re-orientation cost

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note [3] (Graphify/knowledge-graphs) explicitly identifies 'orientation cost — tokens burned every session re-reading a codebase before a single useful action' as the fundamental bottleneck in AI coding agents, reporting 70× token reductions with a pre-computed graph. Cortex already has a rich vault of interlinked Markdown notes but no structural pre-index; every Claude Code session re-reads raw files. Adding a lightweight graph index (nodes = vault files, edges = [[wikilinks]] + frontmatter tags) queryable via the existing MCP server would let downstream agents navigate the vault in one tool call instead of many file reads.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Files to read first:
  - src/  (full tree — understand existing MCP server surface and vault writer)
  - CLAUDE.md
  - pyproject.toml
  - docs/  (any spec files, especially the Phase 5.5 / SPEC §3.13 docs)

Task: Implement a vault knowledge-graph index and expose it through the existing MCP server.

Steps:
1. Create src/cortex/graph/builder.py
   - Walk the vault directory (config-driven path, same root used by vault writer)
   - For each .md file: parse frontmatter (python-frontmatter already in deps) to extract tags, domain, date
   - Extract all [[wikilink]] and [text](relative-path.md) references using a regex
   - Build a dict: { slug: { "path": str, "tags": list, "domain": str, "links_to": [slug,...], "linked_from": [slug,...] } }
   - Persist as JSON to a config-driven path (e.g. .cache/vault_graph.json); regenerate if any .md mtime is newer than the cache

2. Create src/cortex/graph/query.py with three functions:
   - get_neighbors(slug, depth=1) -> list[dict]  — BFS up to depth hops
   - search_by_tag(tag) -> list[dict]
   - find_path(slug_a, slug_b) -> list[str]  — shortest path via BFS

3. Register two new MCP tools in the existing FastMCP server (find the server entrypoint under src/):
   - vault_graph_neighbors(slug: str, depth: int = 1)
   - vault_graph_search(tag: str)
   Both should call builder.py to ensure cache is fresh before querying.

4. Add a CLI entry point in scripts/ (e.g. scripts/build_graph.py) that rebuilds the cache on demand.

Edge cases:
  - Circular links (BFS visited set)
  - Slugs with spaces or special chars (normalise to lowercase-hyphen)
  - Missing link targets (log warning, skip edge — don't crash)
  - Very large vaults: stream-parse rather than loading all files into memory at once

Verification:
  - Run scripts/build_graph.py and confirm .cache/vault_graph.json is created
  - From a Python REPL: from cortex.graph.query import get_neighbors; print(get_neighbors('some-existing-slug'))
  - Start the MCP server and call vault_graph_neighbors via the MCP inspector or a curl to confirm JSON response
  - Add a pytest test in tests/test_graph.py that builds a graph from a small synthetic vault (3 temp .md files with known links) and asserts neighbor counts
```
