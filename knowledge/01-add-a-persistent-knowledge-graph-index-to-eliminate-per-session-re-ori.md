---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-30T03:01:42.047974-07:00
---

# Add a persistent knowledge-graph index to eliminate per-session re-orientation cost

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note [1] (Graphify/structural pre-indexing) reports 70x token reduction by pre-computing a queryable knowledge graph instead of re-reading the codebase each session. The commit history shows daily 'knowledge refresh' runs that each re-scan the vault from scratch. Pre-building a graph of vault nodes + edges (topic links, source→synthesis relationships) and exposing it via the existing MCP server would let Claude Code orient in one tool call instead of reading dozens of files.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - CLAUDE.md
  - src/ (list all .py files, then read the MCP server module and the vault-writer module)
  - knowledge/ (sample 5 markdown files to understand frontmatter schema)
  - config/ (all YAML files)

Task: Implement a lightweight persistent knowledge-graph index for the vault.

Step 1 – Graph builder script
Create src/cortex/graph/build_graph.py that:
  a) Walks every .md file under knowledge/ using python-frontmatter to parse frontmatter.
  b) Extracts: slug (filename stem), title, tags (list), domain, date, and all [[WikiLink]] or markdown hyperlink targets found in the body.
  c) Writes a single JSON file at .cache/vault_graph.json with shape:
     { "nodes": [{"id": slug, "title": ..., "tags": [...], "domain": ...}],
       "edges": [{"src": slug, "dst": slug, "rel": "links_to"}] }
  d) Is idempotent – re-running overwrites the file atomically (write to .cache/vault_graph.tmp then rename).

Step 2 – MCP tool
In the existing MCP server (find it under src/), add a tool called query_graph(domain: str | None, tag: str | None, limit: int = 20) that:
  a) Loads .cache/vault_graph.json (cache in memory with a 5-minute TTL using a module-level dict + timestamp).
  b) Filters nodes by domain and/or tag.
  c) Returns the top `limit` nodes with their direct neighbors (1-hop).
  d) Returns a plain dict (FastMCP will serialize it).

Step 3 – Hook into refresh workflow
Find the nightly/daily refresh script (likely in scripts/). After the vault-write step, call build_graph.py so the graph is always fresh.

Edge cases:
  - Broken [[WikiLinks]] that don't resolve to a real file: log a warning, skip the edge, don't crash.
  - knowledge/ subdirectories: walk recursively.
  - Files with no frontmatter: use filename as title, empty tags.

Verification:
  1. Run: python -m cortex.graph.build_graph and confirm .cache/vault_graph.json is created with >0 nodes and edges.
  2. Start the MCP server and call query_graph(domain='agent-orchestration', tag=None, limit=5) – confirm it returns nodes.
  3. Run the builder twice and confirm the file mtime updates but content is stable (idempotent).
  4. Add .cache/ to .gitignore if not already present.
```
