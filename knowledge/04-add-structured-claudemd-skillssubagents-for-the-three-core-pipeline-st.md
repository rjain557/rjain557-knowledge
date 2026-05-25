---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-25T03:01:49.346493-07:00
---

# Add structured CLAUDE.md skills/subagents for the three core pipeline stages

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

Vault notes 'Github Repos You Should Know' (Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md) and 'Repo of the day: skills' (Inbox/2026-05-16-repo-of-the-day-skills-opensource-github-skills.md) both highlight that the highest-leverage Claude Code pattern is pre-loading proven skills into CLAUDE.md so agents don't re-derive orchestration logic each session. The current CLAUDE.md (referenced in commits) exists but the commit history shows no skills/subagent YAML definitions. Cortex has three well-defined pipeline stages (ingest → extract → deep-research/synth) that are perfect candidates for reusable skill definitions, which would also make the dogfooding repo-review loop more reliable.

## Cited evidence

- Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md
- Inbox/2026-05-16-repo-of-the-day-skills-opensource-github-skills.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

First, read:
  - CLAUDE.md  (full file)
  - .claude/  (list all files, read any settings or commands files)
  - src/cortex/  (list all .py files to understand module names)
  - scripts/  (list all files)

Task: Add three Claude Code skill definitions to CLAUDE.md (or as separate .claude/commands/ YAML files if that pattern is already established) covering the three core pipeline stages.

For each skill, follow the pattern: name, description, trigger phrase, pre-conditions, exact shell command(s) to run, expected output, and failure handling.

Skill 1 — ingest-mail:
  trigger: 'run ingest'
  command: uv run python -m cortex.mail.poll  (adjust module path to match actual)
  pre-conditions: .env present, MSAL cert configured
  expected: structured log lines showing emails processed, moved to Inbox/Processed
  on-failure: check logs/ for MSAL auth errors; re-run with --dry-run flag if available

Skill 2 — run-deep-research:
  trigger: 'deep research on <topic>'
  command: uv run python -m cortex.research.deep_research --topic "<topic>"
  pre-conditions: ANTHROPIC_API_KEY set, DB reachable
  expected: new Markdown file written to knowledge/ with status: synthesized
  on-failure: check for rate-limit errors; retry after 60s; if DB unreachable, write to _inbox_staging/

Skill 3 — nightly-synth:
  trigger: 'run synth' or 'run nightly'
  command: uv run python -m cortex.vault.synth  (adjust to actual module)
  pre-conditions: knowledge graph index exists (run graph rebuild first if not)
  expected: cross-page synthesis notes updated, lint warnings printed
  on-failure: check for embedding API errors; synth is idempotent, safe to re-run

Format requirements:
- If .claude/commands/ directory exists or CLAUDE.md already uses YAML front-matter skill blocks, match that exact format.
- If CLAUDE.md is free-form prose, add a '## Skills' section with a subsection per skill using consistent Markdown headers.
- Each skill must include the exact module path (verify against actual src/ structure before writing).
- Add a '## Pipeline Overview' ASCII diagram at the top of the Skills section showing: Mail/Feed/GitHub → Ingest → Extract → Deep Research → Synth → Vault → MCP/Webhook.

Verification:
1. Read back CLAUDE.md and confirm all three skills are present with correct module paths.
2. Run: uv run python -m cortex.mail.poll --help  (or equivalent) to confirm the module path resolves.
3. No existing CLAUDE.md content should be removed — only additions.
```
