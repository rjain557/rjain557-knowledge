---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M
generated_at: 2026-06-08T03:01:24.415428-07:00
---

# Pre-compute a persistent repo knowledge graph to eliminate per-session re-indexing cost

**Impact:** medium  ·  **Effort:** M

## Rationale

The Graphify/knowledge-graph vault note reports 70× token reduction by pre-computing a queryable graph of the codebase rather than re-reading files each agent session. Cortex's daily repo-review workflow (30 commits of evidence) re-orients itself to the same src/ tree every run, burning tokens on orientation. A lightweight pre-computed JSON graph (modules → imports → exported symbols) stored in .claude/ would let the review agent jump straight to relevant nodes instead of grepping the whole tree.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (full tree — note module structure)
  - .claude/  (existing agent config)
  - CLAUDE.md
  - scripts/  (any existing indexing scripts)

Task: Build a lightweight static knowledge graph of the src/ package and wire it into the Claude Code agent context.

Steps:
1. Create scripts/build_repo_graph.py that:
   - Walks every .py file under src/ using ast.parse.
   - For each module, records: file path, top-level class names, top-level function names, and import targets (stdlib vs internal vs third-party).
   - Writes the result to .claude/repo_graph.json as a dict keyed by dotted module path.
   - Also writes .claude/repo_graph_summary.md — a human-readable table: module | classes | functions | key imports (max 3 per module).
   - Prints a summary line: "Graph built: N modules, M symbols" to stdout.
2. Add a `[build-repo-graph]` entry to pyproject.toml scripts (or a Makefile target) so it can be run with `uv run python scripts/build_repo_graph.py`.
3. Update CLAUDE.md to instruct the agent: "Before exploring src/, read .claude/repo_graph_summary.md to orient yourself. Use it to identify which module to open rather than grepping the whole tree."
4. Add .claude/repo_graph.json and .claude/repo_graph_summary.md to .gitignore (they are regeneratable artifacts).
5. Add a note in the daily review workflow (wherever it is scheduled) to run `python scripts/build_repo_graph.py` before the LLM review step so the graph is always fresh.

Edge cases:
  - Files with syntax errors should be caught per-file (try/except SyntaxError) and logged as warnings, not crash the whole script.
  - __init__.py files should be included but flagged as 'package init' in the graph.
  - The script must be idempotent: running it twice produces the same output.

Verification:
  - `uv run python scripts/build_repo_graph.py` completes without error and prints the summary line.
  - .claude/repo_graph_summary.md exists and contains at least one row per top-level package under src/.
  - `uv run ruff check scripts/build_repo_graph.py` passes.
```
