---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M
generated_at: 2026-06-04T03:01:21.721962-07:00
---

# Implement structured CRRS prompt templates for all agent system prompts

**Impact:** medium  ·  **Effort:** M

## Rationale

Vault note [5] (Structured Prompt Frameworks) argues that single-imperative prompts fail LLMs because they lack role, context, response-format, and safety constraints. The repo's commit history shows the brain prompt and repo-review prompts were added as flat Markdown docs (CORTEX_BRAIN_PROMPT.md, docs/brain-prompt). Refactoring these into a versioned CRRS schema (Context / Role / Response-format / Safety) stored in config/ would make prompt regressions detectable, enable A/B testing across model versions, and align with the multi-provider routing added in commit 4e0a862.

## Cited evidence

- Topics/most-devs-prompt-like-they-write-comments-just-the-instructi.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - docs/  (find CORTEX_BRAIN_PROMPT.md and any other prompt docs)
  - config/  (existing config files)
  - src/  (find where prompts are loaded and passed to the anthropic client)
  - CLAUDE.md

Task: Migrate agent system prompts to a versioned CRRS schema.

Step 1 — Define schema (config/prompts/schema.py or a YAML schema file):
  Each prompt template must have fields:
    version: str          # semver e.g. '1.0.0'
    role: str             # who the model is
    context: str          # what environment/data it operates in
    instructions: str     # the actual task steps
    response_format: str  # exact output shape (JSON schema, Markdown section names, etc.)
    safety_rules: list[str]  # hard constraints (never do X)
    model_affinity: list[str]  # which models this prompt is tuned for

Step 2 — Convert existing prompts:
  - docs/CORTEX_BRAIN_PROMPT.md -> config/prompts/brain_prompt_v1.yaml
  - Repo-review prompt (wherever it lives) -> config/prompts/repo_review_v1.yaml
  - Deep-research prompt -> config/prompts/deep_research_v1.yaml
  Fill all CRRS fields; do not change the semantic content, only restructure.

Step 3 — Loader (src/cortex/prompt_loader.py):
  - load_prompt(name: str, version: str = 'latest') -> dict
  - Renders the YAML fields into a final system-prompt string using a Jinja2-style template (or simple str.format).
  - Validates required fields with pydantic.

Step 4 — Wire into call sites:
  - Replace any hardcoded prompt strings or open(docs/...) calls with prompt_loader.load_prompt(...).

Step 5 — Version bump workflow:
  - Add a CHANGELOG entry in config/prompts/CHANGELOG.md whenever a prompt file changes.
  - Add a pytest test that loads each prompt and asserts all required CRRS fields are non-empty.

Edge cases:
  - If a prompt YAML is malformed, raise a clear ValidationError at startup, not at inference time.
  - Keep the old Markdown files in place but add a deprecation notice pointing to the YAML equivalents.

Verify:
  - `uv run pytest tests/test_prompt_loader.py -v` passes.
  - Run one repo-review job end-to-end and confirm the rendered system prompt contains all four CRRS sections.
```
