---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-01T03:01:55.850017-07:00
---

# Add a persistent knowledge-graph index over the vault to eliminate per-run re-orientation cost

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note [1] (Graphify/structural pre-indexing) documents that AI coding agents burn 70x more tokens re-reading codebases each session versus querying a pre-computed graph. The commit history shows Cortex already runs nightly lint and cross-page synthesis (2026-05-20), but there is no graph layer — every agent run re-scans raw markdown files. Adding a lightweight SQLite-backed entity/link graph (nodes = vault pages, edges = [[wikilinks]] + semantic co-citations extracted once) would let the MCP server answer 'what do we know about X' in one indexed query instead of a full vault scan.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (scan for existing MCP server entry-point and vault-reader utilities)
  - knowledge/  (sample 5-10 .md files to understand frontmatter schema)
  - sql/  (existing schema files)
  - CLAUDE.md

Task: Implement a persistent knowledge-graph index for the vault.

1. Create src/cortex/graph/__init__.py and src/cortex/graph/builder.py.
   - On first run, walk every .md file under knowledge/ and Topics/ using python-frontmatter to parse frontmatter + body.
   - Extract: (a) all [[wikilink]] targets via regex `\[\[([^\]]+)\]\]`, (b) the `title` and `tags` frontmatter fields.
   - Persist to a SQLite DB at .cortex_graph.db (add to .gitignore) with two tables:
       CREATE TABLE IF NOT EXISTS nodes (path TEXT PRIMARY KEY, title TEXT, tags TEXT);
       CREATE TABLE IF NOT EXISTS edges (src TEXT, dst TEXT, kind TEXT, PRIMARY KEY(src,dst,kind));
   - On subsequent runs, only re-index files whose mtime > last_indexed timestamp stored in a metadata table.

2. Create src/cortex/graph/query.py with:
   - `neighbors(path, depth=1)` — returns all nodes reachable within N hops.
   - `search_by_tag(tag)` — returns all node paths with that tag.
   - `most_connected(n=20)` — returns top-N nodes by edge count (hub detection).

3. Wire the builder into the existing nightly lint/synth script (find it under scripts/ or src/) so the graph is rebuilt incrementally after each vault write.

4. Expose two new MCP tools in the FastMCP server (find entry-point in src/):
   - `graph_neighbors(path: str, depth: int = 1)` calling query.neighbors
   - `graph_hubs(n: int = 20)` calling query.most_connected

Edge cases:
  - Wikilinks that reference non-existent files should create a stub node with title=path and a 'dangling' flag.
  - Circular links must not cause infinite loops in neighbors().
  - Tags field may be a YAML list or a comma-separated string — handle both.

Verification:
  - Run `python -m cortex.graph.builder` and confirm .cortex_graph.db is created.
  - Run `python -c "from cortex.graph.query import most_connected; print(most_connected(5))"`.
  - Confirm the MCP server starts without error: `uvicorn cortex.mcp_server:app --port 8001 --dry-run` (or equivalent).
```
