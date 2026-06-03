---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-03T03:01:25.023856-07:00
---

# Replace per-run context re-discovery with a pre-built repo knowledge graph for the repo-review agent

**Impact:** high  ·  **Effort:** M

## Rationale

Vault note Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md documents that agents burn 70x more tokens re-reading codebases each session versus querying a pre-computed knowledge graph. The commit history shows the repo-review workflow fires daily against multiple private repos; each run re-reads file trees and key files from scratch. Pre-indexing each target repo's structure into a lightweight JSON graph (nodes = files/classes/functions, edges = imports/calls) and caching it between runs would cut token spend and latency significantly.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the repo-review workflow file — likely scripts/ or src/cortex/repo_review*.py)
  - CLAUDE.md
  - .gitignore  (note that .claude/file-history/ is already gitignored)

Task: Add a lightweight, cached repo-knowledge-graph layer to the repo-review agent so it does not re-read every file on every daily run.

Steps:
1. Create src/cortex/repo_graph.py with a function `build_graph(repo_local_path: Path) -> dict` that:
   - Walks the repo, records every .py file as a node with keys: path (relative), size_bytes, last_modified_epoch.
   - For each .py file, uses the ast module (stdlib, no new deps) to extract: top-level class names, function names, and import targets.
   - Returns a dict {"generated_at": ISO timestamp, "nodes": [...], "edges": [...]} where edges are {"from": file_a, "to": file_b, "type": "imports"}.
2. Add `save_graph(graph: dict, cache_path: Path)` and `load_graph(cache_path: Path) -> dict | None` using json.dumps/loads.
3. In the repo-review workflow, before building the Claude prompt:
   a. Compute cache_path = .claude/repo-graphs/{repo_slug}.json (already gitignored via .claude/).
   b. Load existing graph; if generated_at is within 24 h, use it. Otherwise call build_graph() and save.
   c. Inject a compact summary of the graph (top 20 files by size, import edge count) into the system prompt instead of re-reading raw file contents.
4. Add a CLI entry point: `python -m cortex.repo_graph <path>` that prints the graph summary to stdout for manual inspection.

Edge cases:
  - Repos with syntax errors in .py files: wrap ast.parse in try/except and record {"parse_error": true} on the node instead of crashing.
  - Non-Python repos: if zero .py files found, return a minimal graph with a note so the review agent knows to fall back to raw file listing.
  - Cache invalidation: if the repo's HEAD commit SHA has changed since last graph build, force a rebuild regardless of age. Read HEAD via subprocess git rev-parse HEAD.

Verification:
  - `python -m cortex.repo_graph .` should complete in <5 s on this repo and print a readable summary.
  - Run the repo-review workflow twice back-to-back; second run should log 'using cached graph' and skip the build step.
  - `ruff check src/cortex/repo_graph.py` must pass clean.
```
