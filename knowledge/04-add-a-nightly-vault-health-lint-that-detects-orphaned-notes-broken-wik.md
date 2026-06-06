---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-06-06T03:01:40.266571-07:00
---

# Add a nightly vault-health lint that detects orphaned notes, broken wikilinks, and duplicate slugs

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

The LLM-Wiki + nightly lint feature was added 2026-05-20 but the commit message only mentions 'cross-page synth + nightly lint' without evidence of broken-link or orphan detection. Vault note [2] (AI Second Brain Stack) explicitly identifies orphaned notes and disconnected links as the primary quality-decay mechanism in agent-maintained vaults, and note [4] (Neuromorphic Active Memory) warns that passive storage without active maintenance causes agents to retrieve stale or contradictory context. A lint job that surfaces these issues daily closes the feedback loop.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md
- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/cortex/vault/ (all files)
  - scripts/ (all files — look for any existing lint or health-check script)
  - src/cortex/scheduler.py or wherever APScheduler jobs are registered
  - knowledge/ (list top-level structure only)

Task: Implement a vault health-lint job that runs nightly and writes a structured report.

Steps:
1. Create src/cortex/vault/lint.py with a VaultLinter class that:
   a. Scans all .md files under knowledge/ and Inbox/.
   b. Detects ORPHANED NOTES: notes with no inbound [[wikilinks]] from any other note AND no outbound links (completely isolated).
   c. Detects BROKEN LINKS: [[wikilinks]] that reference a slug not present in the vault.
   d. Detects DUPLICATE SLUGS: two or more files that resolve to the same slug after python-slugify normalization.
   e. Detects MISSING FRONTMATTER: notes lacking required keys (title, date, categories — infer required keys from the majority of existing notes).
2. Output a lint report as knowledge/Meta/vault-health-<YYYY-MM-DD>.md with YAML frontmatter (date, counts) and a Markdown table per issue type.
3. If zero issues are found, write a brief 'All clear' note anyway (so the scheduler has a heartbeat artifact).
4. Register the linter as a nightly APScheduler job (run at 02:00 America/Los_Angeles) alongside existing scheduled jobs.
5. Add a CLI entry point: `python -m cortex.vault.lint --report-only` that prints the report to stdout without writing to disk (useful for CI).

Edge cases:
  - Wikilinks inside code fences (``` blocks) must be ignored.
  - Case-insensitive slug comparison (MyNote == mynote).
  - Symlinks in the vault directory should be followed once but not recursed infinitely.
  - The job must not crash the scheduler if knowledge/ is temporarily empty.

Verification:
  - `python -m cortex.vault.lint --report-only` exits 0 and prints a valid Markdown table.
  - Manually create a note with a broken [[NonExistentNote]] link; re-run and confirm it appears in the broken-links section.
  - `python -m pytest tests/vault/test_lint.py -x` with at least 3 unit tests (orphan detection, broken link, duplicate slug).
  - `ruff check src/cortex/vault/lint.py` with zero errors.
```
