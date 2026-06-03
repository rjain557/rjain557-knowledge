---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M
generated_at: 2026-06-03T03:01:25.023856-07:00
---

# Implement a structured CRRS prompt template for all Claude agent calls

**Impact:** medium  ·  **Effort:** M

## Rationale

Vault note Topics/most-devs-prompt-like-they-write-comments-just-the-instructi.md explains that single-imperative prompts fail because LLMs lack shared context, and that decomposing into Context / Role / Requirements / Schema (CRRS) slots dramatically reduces ambiguity and output variance. The commit history shows prompts being added ad-hoc across deep-research, synthesis, and repo-review modules. Centralising on a typed PromptTemplate dataclass would make every agent call auditable, testable, and consistent.

## Cited evidence

- Topics/most-devs-prompt-like-they-write-comments-just-the-instructi.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find every file that constructs a system_prompt or user_prompt string passed to the Anthropic client)
  - CLAUDE.md
  - pyproject.toml

Task: Introduce a typed PromptTemplate abstraction using the CRRS framework and migrate the three main agent call sites to use it.

Steps:
1. Create src/cortex/prompt_template.py with a Pydantic BaseModel:

   class CRRSPrompt(BaseModel):
       role: str           # who the model should be
       context: str        # background facts / repo state injected at runtime
       requirements: list[str]  # ordered list of must-do instructions
       output_schema: str  # description or JSON schema of expected output
       negative_constraints: list[str] = []  # must-NOT-do list

       def to_system_message(self) -> str:
           """Render to a single system-prompt string."""
           ...

       def to_user_message(self, task: str) -> str:
           """Render the user turn with the concrete task injected."""
           ...

2. Implement to_system_message() to render sections with clear H2 headers (## Role, ## Context, ## Requirements, ## Output Schema, ## Constraints) so the model can parse structure.

3. Migrate the following call sites (find exact paths by scanning src/):
   a. Deep-research system prompt
   b. Synthesis/LLM-wiki compilation prompt
   c. Repo-review improvement-generation prompt
   Each migration: extract the existing string into a CRRSPrompt instance stored as a module-level constant, then call .to_system_message() where the string was used.

4. Add a unit test in tests/test_prompt_template.py that:
   - Instantiates a CRRSPrompt with all fields.
   - Calls to_system_message() and asserts all five section headers are present.
   - Calls to_user_message('do X') and asserts 'do X' appears in the output.

Edge cases:
  - context field may be large (full file tree injected at runtime); ensure to_system_message() places context AFTER role so the model sees its identity first.
  - negative_constraints being empty should produce no ## Constraints section (avoid confusing the model with an empty list).
  - Do not change the actual prompt content during migration — only restructure the delivery format.

Verification:
  - `pytest tests/test_prompt_template.py -v` must pass.
  - Run one deep-research job and confirm the Claude API call's system field contains '## Role' and '## Requirements'.
  - `ruff check src/cortex/prompt_template.py tests/test_prompt_template.py` must pass clean.
```
