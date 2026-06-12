---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-12T03:01:20.219071-07:00
---

# Expose vault query as a proper MCP tool with structured input/output schema

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

The repo already depends on fastmcp>=0.4 (pyproject.toml) and the vault notes on Claude Code + Obsidian command center (Topics/claude-code-obsidian-commmand-center.md) and the five-levels-of-Claude-Code note both describe MCP tool exposure as the key step that elevates a knowledge system from passive storage to an active reasoning surface that other agents can call. Without a well-typed MCP tool schema, consumer repos calling into Cortex get unstructured text back and cannot compose results programmatically.

## Cited evidence

- Topics/claude-code-obsidian-commmand-center.md
- Topics/here-are-the-five-levels-of-claude-code-and-how-you-can-move.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find any existing MCP server file — likely src/cortex/mcp_server.py or similar)
  - knowledge/  (understand vault structure and frontmatter schema)
  - pyproject.toml  (fastmcp version)
  - CLAUDE.md

Task:
Define and register at least three typed MCP tools on the Cortex FastMCP server so consumer agents can query the vault programmatically.

Tools to implement:

1. `search_vault(query: str, top_k: int = 5) -> list[VaultNote]`
   - VaultNote: {path: str, title: str, summary: str, tags: list[str], url: str | None}
   - Implementation: full-text search over knowledge/ Markdown files using a simple TF-IDF index (use sklearn or a hand-rolled inverted index — no external vector DB required yet).

2. `get_note(path: str) -> VaultNote & {body: str}`
   - Returns full Markdown body + frontmatter fields.
   - Raises McpError with code NOT_FOUND if path doesn't exist.

3. `list_recent(days: int = 7, category: str | None = None) -> list[VaultNote]`
   - Returns notes whose frontmatter `date` field is within the last N days, optionally filtered by category.

Implementation requirements:
  - Use FastMCP's @mcp.tool() decorator with full Pydantic input/output models (not bare dicts).
  - Add a startup hook that builds the TF-IDF index from vault files and caches it in memory; rebuild if any .md file mtime changes.
  - Register the server entrypoint in pyproject.toml under [project.scripts]: `cortex-mcp = "cortex.mcp_server:run"`.

Edge cases:
  - Notes with malformed frontmatter must be skipped with a log warning, not crash the server.
  - search_vault with an empty query should return the top_k most recently added notes.
  - The MCP server must start cleanly even if the knowledge/ directory is empty.

Verify:
  - `uv run cortex-mcp` starts without errors.
  - Use the FastMCP test client or `curl` the MCP endpoint to call search_vault('agent orchestration') and confirm structured JSON is returned.
  - `uv run pytest tests/ -x` passes.
```
