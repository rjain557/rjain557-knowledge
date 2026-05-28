---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-28T03:02:17.091238-07:00
---

# Expose vault query as an MCP tool so external Claude Code sessions can retrieve relevant notes without full vault reads

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault notes 'Claude + Obsidian as Agent-Orchestration Infrastructure' (Topics/claude-obsidian-might-be-the-most-powerful-free-ai-setup-rig.md) and 'Obsidian × Claude Code' (Topics/obsidian-x-claude-code.md) both identify MCP as the canonical bridge for giving external agents structured access to a vault without requiring them to walk the filesystem. Cortex already has fastmcp as a dependency (pyproject.toml) and a webhook server (FastAPI), but the MCP server surface is not visible in the commit history as having vault-query tools. Adding a `search_vault(query: str, top_k: int) -> list[NoteResult]` MCP tool backed by the knowledge-graph index (improvement #1) would let sibling repo agents query Cortex knowledge in a single tool call instead of reading dozens of files.

## Cited evidence

- Topics/claude-obsidian-might-be-the-most-powerful-free-ai-setup-rig.md
- Topics/obsidian-x-claude-code.md
- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/ (find the MCP server file — search with `grep -r 'fastmcp\|FastMCP\|mcp' src/ -l`)
  - src/cortex/vault_graph.py (if created from improvement #1; otherwise read knowledge/ structure directly)
  - pyproject.toml (confirm fastmcp version and any existing MCP entry points)
  - CLAUDE.md (understand how sibling repos currently query Cortex)
  - docs/ (look for any MCP spec or API docs)

Task: Add a `search_vault` MCP tool to the existing Cortex MCP server.

1. Locate the existing MCP server file (likely `src/cortex/mcp_server.py` or similar). If it does not exist, create it.

2. Add the following tool using fastmcp's decorator pattern:
```python
from fastmcp import FastMCP
from pydantic import BaseModel
from cortex.vault_graph import VaultGraph  # from improvement #1
import pathlib, python_frontmatter as fm

mcp = FastMCP("cortex-brain")

class NoteResult(BaseModel):
    path: str
    title: str
    tags: list[str]
    excerpt: str  # first 400 chars of body

@mcp.tool()
def search_vault(query: str, top_k: int = 5) -> list[NoteResult]:
    """
    Search the Cortex knowledge vault by topic/tag keyword.
    Returns up to top_k matching notes with path, title, tags, and a body excerpt.
    Use this before starting any research task to check what Cortex already knows.
    """
    graph = VaultGraph().load()  # loads from knowledge/_graph.json
    paths = graph.query(query)[:top_k]
    results = []
    for p in paths:
        post = fm.load(p)
        body = post.content or ""
        results.append(NoteResult(
            path=p,
            title=post.metadata.get("title", pathlib.Path(p).stem),
            tags=post.metadata.get("tags", []),
            excerpt=body[:400].strip()
        ))
    return results

@mcp.tool()
def read_note(path: str) -> str:
    """
    Read the full content of a vault note by its relative path.
    Use after search_vault to get the complete text of a relevant note.
    """
    full_path = pathlib.Path(path)
    if not full_path.exists() or not str(full_path).startswith("knowledge/"):
        raise ValueError(f"Invalid or unsafe path: {path}")
    return full_path.read_text(encoding="utf-8")
```

3. Ensure the MCP server is startable via:
```bash
python -m cortex.mcp_server
```
Add this to pyproject.toml scripts if not already present.

4. Update `CLAUDE.md` (or the relevant skill card) with:
'External agents: connect to the Cortex MCP server and call `search_vault(query)` before reading vault files directly. This is faster and uses fewer tokens.'

5. Add the MCP server URL/command to `.env.example`:
```
CORTEX_MCP_HOST=127.0.0.1
CORTEX_MCP_PORT=8001
```

Edge cases:
  - `read_note` must validate that the path starts with `knowledge/` to prevent directory traversal.
  - If `knowledge/_graph.json` does not exist yet (graph not built), `search_vault` should fall back to a simple `pathlib.rglob('*.md')` + frontmatter tag scan rather than crashing.
  - `top_k` should be capped at 20 to prevent accidentally returning the entire vault.
  - The MCP server should not require DB connectivity to start — vault tools are filesystem-only.

Verification:
  - Start the MCP server: `python -m cortex.mcp_server`
  - In a separate terminal, use the fastmcp test client or curl the MCP endpoint to call `search_vault` with query='agent-orchestration' and confirm ≥1 result is returned.
  - Call `read_note` with a valid path and confirm full note content is returned.
  - Call `read_note` with path='../src/cortex/db.py' and confirm a ValueError is raised.
```
