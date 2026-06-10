---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-10T03:01:20.668814-07:00
---

# Pre-compute a persistent repo knowledge graph to eliminate per-session re-indexing cost

**Impact:** high  ·  **Effort:** M

## Rationale

The vault note on Graphify (Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md) reports 70x token savings by pre-computing a queryable knowledge graph instead of re-reading the codebase each agent session. Cortex's daily repo-review workflow (commits show it runs every day) re-orients Claude Code from scratch each run, burning tokens on orientation. Adding a Graphify-style pre-index step — even a lightweight JSON dependency graph — would let the review agent jump straight to diffs rather than re-reading all source files.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

Files to read first:
  1. scripts/  — find the repo-review script (likely named *repo_review* or *review*)
  2. .claude/  — read any CLAUDE.md or settings files that configure the daily review agent
  3. CLAUDE.md  — understand how the review agent is invoked
  4. src/  — look for any existing graph or index utilities

Change to make:
  Create scripts/build_repo_graph.py that:
  1. Walks src/ recursively, collecting every .py file.
  2. For each file, uses Python's ast module to extract:
       - Module-level imports (edges: this_module -> imported_module)
       - Top-level class and function names (node metadata)
  3. Writes the result to .claude/repo_graph.json with schema:
       { "nodes": [{"id": "src/cortex/foo.py", "symbols": ["ClassName", "fn_name"]}],
         "edges": [{"from": "src/cortex/foo.py", "to": "src/cortex/bar.py"}] }
  4. Also writes .claude/repo_graph_summary.md — a human-readable table of modules + their exported symbols, max 200 lines.

  Then update the repo-review script to:
  5. Run `python scripts/build_repo_graph.py` as the first step (fast, <5 s).
  6. Prepend the contents of .claude/repo_graph_summary.md to the context block it sends to Claude, replacing any step that reads all src/ files individually.

  Add .claude/repo_graph.json and .claude/repo_graph_summary.md to .gitignore (they are regeneratable artifacts).

Edge cases:
  - Syntax errors in a .py file must not crash the graph builder — catch ast.parse exceptions, log a warning, and continue.
  - Circular imports are fine; the graph is a directed multigraph, not a DAG.
  - If src/ doesn't exist (fresh clone), the script should exit 0 with an empty graph.

How to verify:
  1. `python scripts/build_repo_graph.py` completes without error.
  2. .claude/repo_graph.json is valid JSON: `python -c "import json; json.load(open('.claude/repo_graph.json'))"`
  3. .claude/repo_graph_summary.md is ≤200 lines.
  4. Run the repo-review script end-to-end and confirm it no longer reads every src/ file individually in its context-building phase.
```
