---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-05-27T03:02:00.297634-07:00
---

# Add a persistent knowledge-graph index to eliminate cold-start orientation cost

**Impact:** high  ·  **Effort:** M

## Rationale

Vault note 'Knowledge Graphs as Codebase Memory' (Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md) documents that the dominant bottleneck in agent-orchestration systems is orientation cost — tokens burned re-reading the repo before useful work begins, with pre-computed graph indexes reducing token consumption 70x. Cortex's repo-review and deep-research agents currently re-scan the vault from scratch on every run. Adding a lightweight adjacency/entity graph (e.g. a JSON or SQLite file updated by the nightly lint pass) would let agents jump directly to relevant nodes instead of full-vault traversal.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - CLAUDE.md
  - src/  (scan all .py files, note vault-read and synthesis entry points)
  - knowledge/  (sample 5-10 .md files to understand frontmatter schema)
  - scripts/  (identify nightly lint / synth scripts)

Goal: Implement a lightweight persistent knowledge graph that is (a) built/updated by the existing nightly lint pass and (b) queryable by the repo-review and deep-research agents so they can skip full-vault scans.

Specific changes:
1. Create src/cortex/graph.py with:
   - build_graph(vault_dir: Path) -> dict  — walks all .md files, extracts frontmatter tags + [[wikilinks]] + explicit 'related:' fields, returns adjacency dict {slug: {title, tags, links_to: [], linked_from: []}}
   - save_graph(graph: dict, path: Path)  — writes to knowledge/.graph_index.json (add this file to .gitignore since it's regeneratable)
   - load_graph(path: Path) -> dict
   - query_neighbors(graph, slug, depth=2) -> list[str]  — BFS up to depth hops, returns list of slugs

2. Wire build_graph() into the nightly lint script (scripts/ — find the file that runs the lint/synth pass) so the index is refreshed after every vault write.

3. In the repo-review agent entry point (find in src/), before the full vault scan, call load_graph() and use query_neighbors() to pre-filter relevant notes by topic tags, passing only those slugs to the LLM context window.

Edge cases:
  - First run: if .graph_index.json doesn't exist, fall back to full scan and build it.
  - Circular wikilinks: BFS with a visited set.
  - Files with no frontmatter: include them with empty tags/links.
  - The graph file must NOT be committed (add knowledge/.graph_index.json to .gitignore).

Verification:
  1. Run: python -c "from src.cortex.graph import build_graph, save_graph; from pathlib import Path; g = build_graph(Path('knowledge')); save_graph(g, Path('knowledge/.graph_index.json')); print(len(g), 'nodes')"
  2. Confirm .graph_index.json is created and contains expected slugs.
  3. Run the nightly lint script end-to-end and confirm the graph file is refreshed.
  4. Add a pytest test in tests/ that builds a graph from a 3-file fixture vault and asserts correct adjacency.
```
