---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-05-26T03:02:07.112020-07:00
---

# Add a nightly vault lint + dead-link repair agent following the Karpathy LLM-Wiki pattern

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

Commit '2026-05-20 feat(synth+lint): implement Karpathy LLM-Wiki pattern (cross-page synth + nightly lint)' added synthesis but the lint half is unclear from the commit alone. Vault note 'The AI Second Brain Stack' (Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md) describes the Karpathy pattern explicitly: a background agent that periodically walks the wiki, identifies stale or broken cross-references, and either repairs them or flags them for human review. Without this, the vault accumulates orphaned notes and broken wikilinks as the ingestion pipeline grows, degrading retrieval quality over time.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md
- Topics/obsidian-x-claude-code.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Context files to read first:
  - src/  (find any existing lint or synth module added in commit 2a17649; read it fully)
  - knowledge/  (sample 5-10 notes to understand wikilink and frontmatter conventions)
  - scripts/  (find any scheduler or nightly job runner)
  - CLAUDE.md

Task: Implement a vault lint agent that runs nightly, detects broken wikilinks and orphaned notes, and either auto-repairs or writes a lint report.

Step 1 — Create src/cortex/vault/linter.py

  class VaultLintResult(BaseModel):
    broken_links: list[tuple[str, str]]   # (source_file, broken_target)
    orphaned_notes: list[str]             # files with no inbound links
    missing_frontmatter: list[str]        # files missing required fields
    report_path: Path

  async def run_lint(vault_root: Path, auto_repair: bool = False) -> VaultLintResult:
    1. Build a full link graph (reuse or call build_graph() from the knowledge-graph improvement if implemented, otherwise re-implement the walk inline).
    2. Broken links: edges where dst file does not exist on disk.
    3. Orphaned notes: nodes with in-degree == 0 AND not in a designated 'seed' directory (e.g., knowledge/seeds/ if it exists).
    4. Missing frontmatter: files lacking any of ['title', 'source_url', 'ingested_at'] in their YAML frontmatter.

  If auto_repair=True:
    - For each broken link [[Target]] in a file, attempt fuzzy match (difflib.get_close_matches) against all existing note titles. If a single match with score > 0.85 exists, rewrite the wikilink in place and log the repair.
    - For orphaned notes, add a frontmatter tag 'orphaned: true' so they surface in Obsidian queries.

  Always write a lint report to knowledge/_lint_report.md with:
    - Run timestamp
    - Counts of each issue type
    - Full lists (as markdown tables)
    - Auto-repairs applied (if any)

Step 2 — CLI entry point
  Add a script entry in pyproject.toml:
    [project.scripts]
    cortex-lint = "cortex.vault.linter:cli"

  cli() parses --vault-root (default: ./knowledge) and --auto-repair flag, calls run_lint(), prints summary to stdout.

Step 3 — Scheduler integration
  In the existing APScheduler setup (find it in src/ or scripts/), add:
    scheduler.add_job(run_lint, 'cron', hour=3, minute=0, kwargs={'vault_root': VAULT_ROOT, 'auto_repair': True})
  This runs at 3 AM local time (the repo already uses America/Los_Angeles tz from commit 72a0810).

Step 4 — Commit the lint report
  After run_lint() completes, if any issues were found or repaired, call the existing git-commit helper (or subprocess.run(['git', 'add', 'knowledge/_lint_report.md'], ...)) so the report is versioned.

Edge cases:
  - Fuzzy repair must never silently corrupt a note — log every repair at INFO and write the original line to a .bak sidecar before overwriting.
  - If the vault has >5000 files, the orphan detection (in-degree scan) must use a Counter, not a nested loop.
  - _lint_report.md itself must be excluded from the orphan check and from wikilink parsing.
  - The linter must be read-only by default (auto_repair=False) so it is safe to run in CI.

Verification:
  1. Run `cortex-lint --vault-root knowledge` from repo root; confirm _lint_report.md is created with correct counts.
  2. Manually introduce a broken wikilink in a test note; re-run with --auto-repair; confirm the link is repaired and the .bak file exists.
  3. Run `uv run pytest tests/` — add at least one unit test for run_lint() using a tmp_path fixture with synthetic vault files.
  4. Confirm the APScheduler job appears in the scheduler's job list at startup (log output).
```
