---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-25T03:01:49.346493-07:00
---

# Add a persistent knowledge-graph index to eliminate cold-start orientation cost

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note 'Knowledge Graphs as Codebase Memory' (Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md) documents that the primary bottleneck in agent sessions is orientation cost — tokens burned re-reading the repo before any useful action. Cortex already has a rich Markdown vault but no pre-computed graph layer, so every Claude Code session re-traverses the same files. Adding a lightweight adjacency index (node = vault note, edges = [[wikilinks]] + shared tags + embedding-cluster) stored as a single JSON/SQLite file would let agents jump directly to relevant subgraphs, cutting per-session token burn dramatically.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

First, read these files to understand the current vault structure and DB schema:
  - src/cortex/vault/  (all .py files)
  - sql/  (all .sql files)
  - knowledge/  (browse top-level structure only, do not read every note)
  - CLAUDE.md

Task: Create src/cortex/vault/graph_index.py that builds and maintains a persistent knowledge-graph index of the vault.

Requirements:
1. Node = each Markdown file under knowledge/. Attributes: path (relative), title (from frontmatter or H1), tags (frontmatter list), domain (frontmatter field if present).
2. Edges (three types):
   a. WIKILINK — parsed from [[...]] occurrences in note body.
   b. TAG_SHARED — two notes share ≥1 tag.
   c. EMBED_CLUSTER — notes whose existing embedding vectors (already stored in SQL per the schema) have cosine similarity ≥ 0.82.
3. Persist the graph as knowledge/_graph/index.json with schema:
   { "nodes": [{"id": "<relative_path>", "title": "", "tags": [], "domain": ""}],
     "edges": [{"src": "", "dst": "", "type": "WIKILINK|TAG_SHARED|EMBED_CLUSTER", "weight": 1.0}],
     "built_at": "<ISO timestamp LA tz>" }
4. Expose two public functions:
   - build_graph(vault_root, db_conn) -> nx.DiGraph  (use networkx)
   - get_neighborhood(graph, note_path, depth=2) -> list[str]  (returns list of related note paths)
5. Add a CLI entry point: uv run python -m cortex.vault.graph_index --rebuild
6. Wire the rebuild into the existing nightly lint/synth scheduler (find the scheduler file under src/cortex/ and add a nightly graph rebuild job after the synth job).

Edge cases:
- Broken wikilinks (target file doesn't exist) → log a warning, skip the edge, do NOT crash.
- Notes with no frontmatter → derive title from first H1 or filename stem.
- Empty vault → build_graph returns an empty graph without error.
- DB unavailable → skip EMBED_CLUSTER edges, build graph from wikilinks + tags only.

Verification:
1. uv run python -m cortex.vault.graph_index --rebuild  should complete without error and write knowledge/_graph/index.json.
2. Print node count and edge count by type to stdout.
3. Add knowledge/_graph/index.json to .gitignore (it is regeneratable).
4. Write a pytest test in tests/test_graph_index.py that creates a temp vault with 3 synthetic notes (two linked, one isolated) and asserts the graph has exactly 1 WIKILINK edge and 2 nodes with degree > 0.
```
