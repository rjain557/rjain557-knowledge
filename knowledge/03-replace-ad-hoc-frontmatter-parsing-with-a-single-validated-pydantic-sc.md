---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-05-25T03:01:49.346493-07:00
---

# Replace ad-hoc frontmatter parsing with a single validated Pydantic schema for vault notes

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

The repo uses python-frontmatter for vault writes and reads across multiple pipeline stages (ingestion, synth, lint, repo-review). The vault notes in the knowledge brain show inconsistent field presence (some have 'domain', some have 'tags', some have neither), which is a symptom of no enforced schema. The 'LLM Wiki + Obsidian' vault note (Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md) specifically identifies schema consistency as what separates a 'filing cabinet' vault from an 'active reasoning surface'. Without a Pydantic model, any agent writing a note can silently omit required fields, breaking downstream graph indexing, vector embedding, and MCP queries.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md
- Topics/claude-obsidian-might-be-the-most-powerful-free-ai-setup-rig.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root (rjain557/rjain557-knowledge).

First, read:
  - src/cortex/vault/  (all .py files)
  - knowledge/  (read 5 representative notes — pick one from Topics/, one from Inbox/, one from any synthesis folder — to observe actual frontmatter fields in use)
  - CLAUDE.md

Task: Define a canonical Pydantic v2 model for vault note frontmatter and enforce it at every write point.

Steps:
1. Create src/cortex/vault/schema.py:

   from pydantic import BaseModel, Field, field_validator
   from typing import Literal, Optional
   from datetime import date

   DOMAINS = Literal["agent-orchestration", "seo-agents", "tech-support-agents", "office-ops", "general"]

   class NoteMetadata(BaseModel):
       title: str
       date: date
       domain: DOMAINS = "general"
       tags: list[str] = Field(default_factory=list)
       source_url: Optional[str] = None
       source_type: Optional[str] = None   # email | feed | github | youtube | pdf | arxiv | manual
       status: Literal["inbox", "processed", "synthesized", "archived"] = "inbox"
       # Allow extra fields so existing notes with bonus keys don't break
       model_config = {"extra": "allow"}

       @field_validator("tags", mode="before")
       @classmethod
       def coerce_tags(cls, v):
           if v is None: return []
           if isinstance(v, str): return [t.strip() for t in v.split(",") if t.strip()]
           return v

2. In the existing vault writer module (find the file that calls frontmatter.dumps or post.metadata), import NoteMetadata and validate before writing:
   meta = NoteMetadata(**raw_meta_dict)
   post.metadata = meta.model_dump(exclude_none=True)

3. Add a vault lint function in src/cortex/vault/schema.py:
   def lint_note(path: Path) -> list[str]:
       """Return list of validation error strings, empty if valid."""

4. Wire lint_note into the existing nightly lint pass (find the lint scheduler/script) so it logs a structured warning for each invalid note but does NOT abort the run.

Edge cases:
- Notes written before this change may have date as a string like '2026-05-16' or a datetime — the field_validator should coerce both.
- Notes with no frontmatter at all → lint_note returns ["missing frontmatter"], writer raises ValueError.
- The 'extra=allow' policy means no existing note fields are silently dropped.

Verification:
1. uv run python -c "from cortex.vault.schema import NoteMetadata; m = NoteMetadata(title='Test', date='2026-05-24'); print(m.model_dump())"
2. uv run ruff check src/cortex/vault/schema.py
3. Add tests/test_vault_schema.py with at least: valid note passes, missing title raises, bad domain raises, string date coerces, string tags coerce.
```
