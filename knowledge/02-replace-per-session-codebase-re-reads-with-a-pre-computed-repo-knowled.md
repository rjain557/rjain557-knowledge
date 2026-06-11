---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-11T03:01:26.483504-07:00
---

# Replace per-session codebase re-reads with a pre-computed repo knowledge graph (Graphify pattern)

**Impact:** high  ·  **Effort:** M

## Rationale

The repo-review workflow (feat added 2026-05-17) re-reads each target repo's file tree and key files from scratch on every daily run. Vault note 'Claude Code just got a huge upgrade — Graphify' (Topics/claude-code-just-got-a-huge-upgrade) reports 70× token reduction by pre-computing a persistent knowledge graph of a repository and querying it instead of re-reading raw files. The daily commit cadence (30 consecutive 'Knowledge refresh' commits) means this orientation cost compounds every single day across every reviewed repo.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - scripts/  (find the repo-review script, likely repo_review.py or similar)
  - src/  (find any module that reads remote repo file trees — look for GitHub API calls, PyGithub usage, or file-tree assembly)
  - knowledge/  (understand the output format)
  - CLAUDE.md

Task:
Implement a lightweight repo-snapshot cache so the review workflow does not re-fetch the full file tree + config files on every run when nothing has changed.

1. Create src/cortex/repo_cache.py with a class RepoSnapshot:
   - Fields: repo_full_name (str), last_commit_sha (str), captured_at (datetime), file_tree (list[str]), key_file_contents (dict[str, str]).
   - Serialises to/from JSON at .cache/repo_snapshots/{slug}.json (create dir if absent; add .cache/ to .gitignore).
   - Method `is_stale(current_sha: str) -> bool` returns True if last_commit_sha differs.

2. In the repo-review workflow:
   a. Before fetching file tree, call GitHub API for the repo's latest commit SHA on default branch (already available via PyGithub — use repo.get_branch(repo.default_branch).commit.sha).
   b. Load cached snapshot if it exists and `not snapshot.is_stale(current_sha)` — skip re-fetching file tree and key files, reuse cached data.
   c. If stale or absent, fetch as today, then save a new RepoSnapshot.

3. Add a CLI flag `--force-refresh` to the review script that bypasses the cache.

Edge cases:
  - Cache dir must be in .gitignore (add `.cache/` if not already present).
  - If the cache JSON is corrupt (JSONDecodeError), log a warning and fall back to full fetch.
  - Private repos: the cache stores file contents — ensure .cache/ is in .gitignore before writing.

Verify:
  - Run the review script twice against the same repo with no intervening commits; second run should log 'Using cached snapshot for <repo>' and make zero GitHub file-content API calls.
  - Run with `--force-refresh`; confirm full fetch occurs.
```
