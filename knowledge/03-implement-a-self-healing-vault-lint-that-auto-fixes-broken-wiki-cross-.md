---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-06-07T03:01:21.608196-07:00
---

# Implement a self-healing vault lint that auto-fixes broken wiki cross-links nightly

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

Vault note [2] describes the LLM Wiki pattern where cross-page synthesis links are the primary value driver of the second-brain stack. The commit history shows a 'synth+lint' feature was added (2026-05-20) but the .gitignore excludes *.log files, meaning lint failures are invisible in CI. A nightly job that detects and auto-repairs broken [[wikilinks]] and orphaned notes would prevent the vault from silently degrading as new notes are added daily.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Files to read first:
  - src/ — find the existing lint module: `find src -name '*lint*' -o -name '*synth*' | head -20`
  - knowledge/ — understand vault structure: `find knowledge -name '*.md' | head -30`
  - scripts/ — look for any existing nightly scripts
  - .claude/ — check for scheduled task definitions

Task: Create scripts/vault_lint.py — a self-healing vault linter that runs nightly and auto-fixes broken cross-links.

The script must:
1. **Discover all notes**: Walk knowledge/ recursively, collect every .md file path and its slug (filename without extension).
2. **Extract all wikilinks**: For each note, regex-match `[[target]]` and `[[target|alias]]` patterns. Build a set of referenced slugs.
3. **Detect broken links**: A link is broken if its target slug does not match any discovered note filename (case-insensitive).
4. **Auto-fix strategy**:
   a. Try fuzzy match (difflib.get_close_matches, cutoff=0.85) against all known slugs.
   b. If a single confident match exists, rewrite the link in-place and log the fix.
   c. If no match or ambiguous, write the broken link to knowledge/_lint_report.md (create/overwrite) with: note path, broken link text, candidates if any.
5. **Detect orphaned notes**: A note is orphaned if no other note links to it AND it has no frontmatter tag `pinned: true`. Append orphans to _lint_report.md.
6. **Exit code**: Exit 1 if _lint_report.md has any unresolved issues (so CI/scheduler can alert), exit 0 if all issues were auto-fixed.

Edge cases:
  - Skip _lint_report.md itself and any note in knowledge/Inbox/ (those are transient).
  - Preserve frontmatter exactly — only rewrite the body portion of each file.
  - If a note has CRLF line endings, preserve them.
  - Do not rewrite a file if no changes were made (avoid spurious git diffs).

Also: add an entry to the existing APScheduler setup (find it with `grep -r 'APScheduler\|add_job\|scheduler' src/ --include='*.py' -l`) that calls `subprocess.run(['python', 'scripts/vault_lint.py'])` nightly at 02:00 America/Los_Angeles.

Verify:
  - `python scripts/vault_lint.py` runs without error on the current vault.
  - Introduce a deliberate broken link in a test note, re-run, confirm it is either fixed or appears in _lint_report.md.
  - `echo $?` returns 0 when no unresolved issues remain.
```
