---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-29T03:02:24.196603-07:00
---

# Pre-index CLAUDE.md and key src/ modules into a repo-level knowledge graph node at startup to cut agent orientation cost

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

Vault note 'Knowledge Graphs as Codebase Memory' (Graphify) reports 70x token reduction by pre-computing a persistent queryable knowledge graph of the repository and wiring it into the agent's tool-call lifecycle. Cortex's own repo-review agent (commit 2e72bbc) reads sibling repos cold each run — and now dogfoods itself (commit 35dd35f). Pre-indexing CLAUDE.md, pyproject.toml, and the top-level src/ module map into a structured JSON context file at startup would let the agent skip re-reading these files on every invocation, directly applying the Graphify pattern to Cortex's own codebase.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - CLAUDE.md
  - pyproject.toml
  - src/  (list all Python files with: find src/ -name '*.py' | head -60)
  - .claude/  (read any existing settings or memory files)
  - The repo-review runner in src/ (find the module that handles the daily Cortex self-review)

Task: Create a startup pre-indexer that writes a compact repo-context JSON file, and update the repo-review agent to load it instead of re-reading source files.

Step 1 — Create src/cortex/repo_index.py:

Implement `build_repo_index(repo_root: str) -> dict` that returns:
{
  'generated_at': '<ISO timestamp>',
  'repo_root': '<abs path>',
  'claude_md_summary': '<first 2000 chars of CLAUDE.md>',
  'pyproject_deps': ['<list of top-level dependency names from pyproject.toml>'],
  'module_map': [
    {'module': 'cortex.ingest', 'path': 'src/cortex/ingest.py', 'public_functions': ['...'], 'docstring': '...'},
    ...  # one entry per .py file in src/
  ],
  'recent_commits': ['<last 10 commit one-liners from git log --oneline -10>'],
  'scheduler_jobs': ['<list of APScheduler job IDs found by grepping src/ for add_job>'],
  'open_todos': ['<lines matching TODO|FIXME|HACK in src/, max 20>']
}

For public_functions: use ast.parse() to extract top-level function and class names without importing the module.
For docstring: use ast.get_docstring() on the module node.

Implement `write_repo_index(repo_root: str, output_path: str = '.claude/repo_index.json')` that calls build_repo_index and writes the result as pretty-printed JSON. This file is already gitignored via .claude/settings.local.json pattern — confirm .gitignore covers .claude/ or add `.claude/repo_index.json` to .gitignore.

Step 2 — Call at startup:
In the main scheduler entrypoint (find it in src/ — likely the file that initialises APScheduler), add as the very first action before any jobs are scheduled:
  from cortex.repo_index import write_repo_index
  write_repo_index(repo_root=str(Path(__file__).parents[2]))

Step 3 — Load in repo-review agent:
In the repo-review module, at the top of the function that builds the prompt for Cortex self-review:
  index_path = Path('.claude/repo_index.json')
  if index_path.exists():
      repo_context = json.loads(index_path.read_text())
  else:
      repo_context = {}
Inject repo_context['claude_md_summary'], repo_context['module_map'] (names only, not full source), and repo_context['scheduler_jobs'] into the system prompt. Remove any existing code that re-reads CLAUDE.md or scans src/ for the same information.

Edge cases:
  - ast.parse() may fail on files with syntax errors — catch SyntaxError per file and set public_functions=[] docstring='<parse error>'
  - git log subprocess call must have a timeout=10 and handle CalledProcessError gracefully (return [] if git unavailable)
  - The output file must be written atomically: write to .claude/repo_index.json.tmp then os.replace() to avoid partial reads
  - If .claude/ directory doesn't exist, create it with os.makedirs(exist_ok=True)

Verification:
  - Run: python -c "from cortex.repo_index import write_repo_index; write_repo_index('.')" and inspect .claude/repo_index.json
  - Confirm module_map has one entry per .py file in src/
  - Confirm the file is listed in .gitignore (grep .gitignore for repo_index)
  - Run pytest tests/ -k repo_index after adding tests/test_repo_index.py with: test_build_repo_index_has_required_keys, test_build_repo_index_handles_syntax_error_gracefully
```
