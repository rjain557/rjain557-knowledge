---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-29T03:02:24.194580-07:00
---

# Replace ad-hoc model string literals with the new multi-provider router for all agent call sites

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Commit 4e0a862 ('feat: multi-provider model routing, model-refresh workflow, as-built spec') landed a router, but the commit message implies it was added as new infrastructure rather than retrofitted to existing call sites. Vault note 'Claude Code Maturity Levels' explicitly identifies that moving from level 2 to level 3 requires consistent model-selection abstraction across all agents — hardcoded model strings in individual agent files mean the new routing logic (cost tiers, fallback, refresh) is bypassed for older code paths, creating silent cost and reliability regressions.

## Cited evidence

- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (grep -r 'claude-' src/ and grep -r 'model=' src/ to find every hardcoded model string)
  - The module introduced in commit 4e0a862 — find it by running: git show 4e0a862 --stat, then read the new files
  - CLAUDE.md
  - pyproject.toml

Task: Audit every call site that passes a model name string directly to the Anthropic client and replace it with a call to the new multi-provider router.

Step-by-step:
1. Run this audit command from repo root and save output:
   grep -rn --include='*.py' -E '(model\s*=\s*["\x27]|claude-[0-9])' src/ > /tmp/model_audit.txt
   cat /tmp/model_audit.txt

2. Read the router module (from commit 4e0a862). Understand its public API: what function/class do callers use? What parameters does it accept (task_type, cost_tier, fallback_chain)?

3. For each hardcoded model string found in step 1:
   a. Identify the agent's task type (deep_research, repo_review, synthesis, lint, embedding, verification)
   b. Replace the literal string with a call to the router, e.g.:
      BEFORE: model='claude-3-5-sonnet-20241022'
      AFTER:  model=get_model(task='deep_research', tier='standard')
   c. Import the router at the top of each modified file

4. Ensure the router's model-refresh workflow (also from 4e0a862) is triggered: confirm there is a scheduled job or script that calls the refresh function. If not, add a weekly APScheduler job named 'model_refresh' that calls the router's refresh entrypoint.

5. Add a constant `ROUTER_VERSION` to the router module set to '1.0.0' so future audits can grep for it.

Edge cases:
  - Some call sites may pass model as a positional arg — catch those in the grep too: grep -rn 'messages=' src/ and look at the surrounding context
  - The Haiku verifier (commit 6264eef) likely has its own hardcoded model — make sure it uses tier='economy'
  - Do not change model strings inside test fixtures or mock objects
  - If the router raises an exception (provider unavailable), it must fall back gracefully — verify the router has a try/except with fallback, add one if missing

Verification:
  - Re-run the audit grep: grep -rn --include='*.py' -E '(model\s*=\s*["\x27]claude-)' src/ — output should be empty (zero hardcoded strings outside the router itself)
  - Run pytest tests/ and confirm no regressions
  - Start the scheduler in dry-run mode and confirm 'model_refresh' appears in the job list
```
