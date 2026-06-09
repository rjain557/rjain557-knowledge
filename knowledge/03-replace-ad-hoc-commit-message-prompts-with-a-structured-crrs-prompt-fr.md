---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S
generated_at: 2026-06-09T03:01:24.645075-07:00
---

# Replace ad-hoc commit-message prompts with a structured CRRS prompt framework for all agent-generated commits

**Impact:** medium  ·  **Effort:** S

## Rationale

The structured-prompt vault note (Topics/most-devs-prompt-like-they-write-comments-just-the-instructi.md) argues that single-imperative prompts fail because they carry no role, context, or constraint slots. Looking at the last 30 commits, every automated 'Cortex Repo Review' commit message is identical boilerplate with no semantic content about what actually changed. Applying a CRRS (Context / Role / Request / Spec) template to the commit-generation prompt would produce diffs that are actually reviewable and would make the self-improvement loop auditable.

## Cited evidence

- Topics/most-devs-prompt-like-they-write-comments-just-the-instructi.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

Context files to read first:
  1. scripts/ — find the script responsible for auto-committing knowledge refreshes and repo-review results
  2. CLAUDE.md — find any existing commit-message instructions
  3. .claude/ — check for slash-command definitions that generate commits

Task: Replace the flat commit-message string in the auto-commit script with a structured CRRS prompt that asks the LLM to generate a meaningful commit message.

Steps:
  1. Locate the line(s) that produce the commit message string (currently something like 'Cortex Repo Review: [cortex] Knowledge refresh YYYY-MM-DD — N improvement prompts').
  2. Create a helper function `generate_commit_message(changed_files: list[str], pipeline_stage: str, summary_bullets: list[str]) -> str` in src/cortex/git_utils.py (create file if absent).
  3. Inside that function, build a CRRS-structured prompt:
       CONTEXT: "You are writing a git commit message for the Cortex knowledge system. The pipeline stage was {pipeline_stage}. The following files changed: {changed_files}."
       ROLE: "Act as a senior engineer who writes atomic, informative commit messages."
       REQUEST: "Write a single git commit message (subject line ≤72 chars + optional body) that describes WHAT changed and WHY, not just that a refresh ran."
       SPEC: "Subject must start with a conventional-commit prefix (feat/fix/chore/docs). Body bullets must reference specific vault notes added, updated, or deleted. Do not mention the date in the subject — it is already in the git timestamp."
  4. Call this function from the auto-commit script and pass its output to `git commit -m`.
  5. Add a unit test in tests/test_git_utils.py that mocks the LLM call and asserts the returned string starts with a valid conventional-commit prefix and is ≤72 chars on the first line.

Edge cases:
  - If changed_files is empty, return 'chore(cortex): no-op refresh — no vault files changed' without calling the LLM.
  - If the LLM returns a message >72 chars on line 1, truncate to 72 and append '…'.
  - The function must not raise if the anthropic call fails; fall back to the old static string and log a warning.

Verify: Trigger a manual knowledge refresh run and inspect `git log --oneline -3` to confirm the new message format is in use.
```
