---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-07T03:01:21.608196-07:00
---

# Add structured memory persistence so the repo-review agent accumulates cross-session context

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note [4] identifies statelessness as the core failure mode of agent memory systems: 'agents without memory start cold.' The commit history shows the repo-review workflow runs daily and generates improvement prompts, but each run starts from scratch with no memory of which improvements were already suggested, accepted, or rejected. This causes duplicate suggestions across sessions (visible in the uniform commit messages) and wastes tokens re-analyzing unchanged code.

## Cited evidence

- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge)

Files to read first:
  - src/ — find the repo-review module: `find src -name '*review*' -o -name '*repo*' | head -20`
  - knowledge/ — check if a review-memory file already exists: `find knowledge -name '*review*' -o -name '*memory*' | head -10`
  - sql/ — check for existing tables: `ls sql/`
  - .env.example

Task: Add a persistent memory layer to the repo-review workflow so it never re-suggests an improvement that was already committed.

Steps:
1. Create sql/review_memory.sql with a CREATE TABLE IF NOT EXISTS:
   ```sql
   CREATE TABLE IF NOT EXISTS review_memory (
     id            INT IDENTITY PRIMARY KEY,
     repo_name     NVARCHAR(200)  NOT NULL,
     improvement_title NVARCHAR(500) NOT NULL,
     suggested_at  DATETIME2      NOT NULL DEFAULT GETUTCDATE(),
     status        NVARCHAR(50)   NOT NULL DEFAULT 'suggested',  -- suggested | accepted | rejected | stale
     commit_sha    NVARCHAR(40)   NULL,
     notes         NVARCHAR(MAX)  NULL,
     CONSTRAINT uq_repo_title UNIQUE (repo_name, improvement_title)
   );
   ```
2. Create src/cortex/review_memory.py with:
   - `record_suggestion(repo: str, title: str, commit_sha: str | None) -> None` — UPSERT into review_memory.
   - `get_recent_suggestions(repo: str, days: int = 30) -> list[str]` — return list of improvement titles suggested in the last N days.
   - `mark_status(repo: str, title: str, status: str) -> None` — update status field.
3. In the repo-review module (identified above):
   a. Before generating the Claude prompt, call `get_recent_suggestions(repo_name, days=30)` and inject the result into the system prompt as: 'Do NOT re-suggest improvements with these titles (already suggested recently): {titles_list}. Focus on genuinely new issues.'
   b. After generating and committing improvements, call `record_suggestion(repo, title, commit_sha)` for each improvement in the output.
4. Add a weekly cleanup job (APScheduler, Sunday 03:00 LA time) that sets status='stale' for any suggestion older than 60 days with status='suggested' (meaning it was never acted on).

Edge cases:
  - If the DB is unavailable, log a warning and proceed without memory (degrade gracefully — do not crash the review).
  - Title matching should be case-insensitive and strip leading/trailing whitespace before the UNIQUE constraint comparison.
  - The UPSERT should use SQL Server MERGE syntax (not INSERT OR IGNORE — this is pyodbc/SQL Server).

Verify:
  - Run `python -c 'from cortex.review_memory import get_recent_suggestions; print(get_recent_suggestions("test-repo"))'` — should return [].
  - Run the repo-review workflow twice on the same repo and confirm the second run's commit does not contain titles from the first run.
```
