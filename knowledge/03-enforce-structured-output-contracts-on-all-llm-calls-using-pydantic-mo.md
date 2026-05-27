---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M
generated_at: 2026-05-27T03:02:00.297634-07:00
---

# Enforce structured output contracts on all LLM calls using Pydantic models

**Impact:** medium  ·  **Effort:** M

## Rationale

The repo already depends on pydantic>=2.7 (pyproject.toml) but the recent multi-provider model routing commit (4e0a862) adds complexity where unvalidated LLM JSON responses from different providers could silently differ in shape. Vault note 'Claude Code Maturity Levels' (Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md) identifies structured output contracts as a key Level 3→4 maturity step for agent pipelines. Adding Pydantic response models for every LLM call site would catch provider-specific schema drift at parse time rather than downstream.

## Cited evidence

- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find every file that calls anthropic client or any other LLM provider — grep for 'client.messages.create', 'completion', 'model=' etc.)
  - CLAUDE.md
  - The commit 4e0a862 diff if accessible, otherwise read the multi-provider routing module directly.

Goal: Ensure every LLM call site parses the response into a typed Pydantic model rather than accessing raw dict keys.

Specific changes:
1. Create src/cortex/schemas.py (or add to existing schemas file if present) with Pydantic v2 models for each distinct LLM response shape currently used in the codebase. Common ones to look for:
   - DeepResearchResult(title: str, summary: str, key_points: list[str], sources: list[str])
   - RepoReviewImprovement(title: str, rationale: str, impact: Literal['low','medium','high'], effort: Literal['S','M','L'], prompt: str)
   - ExtractionResult(content: str, metadata: dict, confidence: float)
   - VaultEntry(slug: str, tags: list[str], body: str)
   Add model_config = ConfigDict(extra='forbid') to each so unexpected fields raise immediately.

2. For each LLM call site found in step 1:
   a. After receiving the raw response text, parse with ModelClass.model_validate_json(response_text) inside a try/except ValidationError block.
   b. On ValidationError: log the raw response at DEBUG level via structlog, raise a typed exception (class LLMResponseParseError(RuntimeError)) with the provider name and model name included.
   c. Return the typed model object, not the raw dict.

3. In the multi-provider router (commit 4e0a862 module): add a provider-specific response normalizer that maps each provider's envelope format to the shared schema before Pydantic validation, so the rest of the codebase is provider-agnostic.

Edge cases:
  - Some providers wrap content in choices[0].message.content (OpenAI-style) vs content[0].text (Anthropic-style) — the normalizer must handle both.
  - Streaming responses: skip Pydantic validation for streaming; only validate assembled final text.
  - Partial JSON from truncated responses: catch json.JSONDecodeError separately from ValidationError and log the truncated text.

Verification:
  1. Run existing tests: pytest tests/ -x
  2. Add a test in tests/test_schemas.py that feeds a malformed dict to each Pydantic model and asserts ValidationError is raised.
  3. Add a test that feeds a valid dict and asserts the typed object is returned with correct field values.
  4. Grep for any remaining raw dict key access on LLM responses (e.g. response['content'], result.get('title')) and confirm zero hits after the change.
```
