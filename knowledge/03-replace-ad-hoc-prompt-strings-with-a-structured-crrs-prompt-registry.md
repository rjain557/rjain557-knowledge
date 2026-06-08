---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M
generated_at: 2026-06-08T03:01:24.415428-07:00
---

# Replace ad-hoc prompt strings with a structured CRRS prompt registry

**Impact:** high  ·  **Effort:** M

## Rationale

The 'structured prompt frameworks' vault note argues that single-imperative prompts fail because they carry no role, context, or constraint slots — exactly the pattern likely present in Cortex's synthesis and repo-review prompts. With 30+ daily automated commits, even a small prompt regression silently degrades all downstream knowledge. A versioned YAML prompt registry with explicit Context/Role/Request/Schema slots makes prompts diffable, testable, and swappable without touching Python logic.

## Cited evidence

- Topics/most-devs-prompt-like-they-write-comments-just-the-instructi.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find all files containing multi-line prompt strings — search for triple-quoted strings or variables named *_prompt, *_system, *_instruction)
  - config/  (any existing prompt config)
  - CLAUDE.md

Task: Extract inline prompt strings into a versioned YAML registry and load them via a typed accessor.

Steps:
1. Create config/prompts.yaml. For each prompt you find in src/, add an entry with this shape:
   ```yaml
   repo_review_system:
     version: "1.0"
     role: "You are a senior staff engineer reviewing a private GitHub repository..."
     context: "Repository metadata, README, last 30 commits, and top-level file tree are provided as tool output."
     request: "Identify 3-5 concrete, high-leverage improvements traceable to the repo context."
     output_schema: "Return strict JSON: {improvements: [{title, rationale, impact, effort, prompt}]}"
     constraints:
       - "Do not propose improvements not traceable to the repo context."
       - "Each prompt field must be a complete, paste-ready Claude Code prompt."
   ```
   Adapt role/context/request/output_schema/constraints to match what each existing prompt actually does.
2. Create src/cortex/prompts.py with:
   - A Pydantic model `PromptTemplate(BaseModel)` with fields: version, role, context, request, output_schema, constraints (list[str]).
   - A `PromptRegistry` class that loads config/prompts.yaml on init and exposes `get(name: str) -> str` which renders the template into a single system-prompt string in the order: role → context → request → output_schema → constraints (bulleted).
   - A `reload()` method so prompts can be hot-swapped without restarting the process.
3. Replace each inline prompt string in src/ with `PromptRegistry().get("<key>")`. Keep the old string as a comment above the call for diff clarity.
4. Add a test in tests/ (create the file if absent): test_prompts.py that loads the registry, calls get() for each key, and asserts the returned string contains the role text and at least one constraint.

Edge cases:
  - If config/prompts.yaml is missing a key that code requests, raise a descriptive KeyError (not a silent empty string).
  - YAML special characters in prompt text (colons, quotes) must be properly escaped — use block scalars (|) for multi-line values.
  - The registry must be importable even if anthropic is not installed (no top-level LLM imports in prompts.py).

Verification:
  - `uv run python -c "from src.cortex.prompts import PromptRegistry; r = PromptRegistry(); print(r.get('repo_review_system')[:80])"` prints the first 80 chars of the rendered prompt.
  - `uv run pytest tests/test_prompts.py -v` passes.
  - `uv run ruff check src/cortex/prompts.py` passes.
```
