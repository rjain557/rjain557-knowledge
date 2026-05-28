---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-28T03:02:17.091238-07:00
---

# Implement structured CLAUDE.md sub-agent skill cards following the Claude Code best-practices pattern

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

Vault note 'Github Repos You Should Know' (Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md) specifically calls out the 'Cloudcode Best Practices' reference repo and its pattern of YAML-front-matter skill cards for sub-agents and custom commands. The current CLAUDE.md (referenced in commits) is a single monolithic file. As Cortex has grown to include repo-review, deep-research, vault-lint, model-routing, and webhook agents, a single CLAUDE.md creates ambiguity about which instructions apply to which agent context. Splitting into per-workflow skill cards under `.claude/skills/` would let each agent load only its relevant context, reducing token overhead and improving reliability.

## Cited evidence

- Inbox/2026-05-16-github-repos-you-should-know-code-programming-coding-tech-ai.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - CLAUDE.md (read the entire file)
  - .claude/ (list all files; read any existing commands or settings)
  - docs/ (scan for any workflow specs)

Task: Refactor CLAUDE.md into modular skill cards.

1. Read CLAUDE.md in full. Identify distinct workflow sections (likely: repo-review, deep-research, vault-lint/synth, model-routing, webhook/ingestion, general coding standards).

2. Create `.claude/skills/` directory. For each identified workflow, create a Markdown file with YAML frontmatter:
```
---
name: repo-review
description: "Reviews sibling repos and commits improvement prompts to knowledge/"
triggers: ["repo review", "review repo", "cortex review"]
context_files:
  - knowledge/_graph.json
  - config/repo_review_allowlist.yaml
---
# Repo Review Skill
[move the relevant CLAUDE.md section here]
```
Files to create (adjust names to match actual CLAUDE.md sections):
  - `.claude/skills/repo-review.md`
  - `.claude/skills/deep-research.md`
  - `.claude/skills/vault-maintenance.md`
  - `.claude/skills/ingestion-pipeline.md`
  - `.claude/skills/model-routing.md`

3. Rewrite the root `CLAUDE.md` to be a concise index (max 80 lines):
   - Project overview (3-5 sentences)
   - Directory map (src/, scripts/, sql/, knowledge/, config/)
   - How to load a skill: 'For task-specific instructions, read `.claude/skills/<skill-name>.md` before starting work.'
   - Universal rules that apply to ALL agents (coding style, secret handling, commit format)

4. Do NOT delete any content — every sentence currently in CLAUDE.md must appear either in the new root or in one of the skill cards.

Edge cases:
  - If CLAUDE.md contains cross-cutting rules (e.g., 'always use structlog'), keep those ONLY in the root, not duplicated in skill cards.
  - Preserve any existing `.claude/` files (settings.json, commands/) — do not overwrite them.
  - If a section is ambiguous about which skill it belongs to, create a `.claude/skills/general.md` for overflow.

Verification:
  - `wc -l CLAUDE.md` should be ≤ 80 lines after the refactor.
  - `cat .claude/skills/*.md | wc -l` should be ≥ the original CLAUDE.md line count (no content lost).
  - Do a quick grep: `grep -r 'pyodbc' .claude/skills/` should return at least one hit (DB instructions preserved).
```
