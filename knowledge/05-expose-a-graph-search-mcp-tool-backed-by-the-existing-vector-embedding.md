---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: S (<1 day)
generated_at: 2026-06-02T03:02:04.796423-07:00
---

# Expose a `graph_search` MCP tool backed by the existing vector embeddings (fix single-call context assembly)

**Impact:** medium  ·  **Effort:** S (<1 day)

## Rationale

Vault note [6] ('The Company That Made RAG Mainstream Is Now Betting Against It') describes Pinecone Nexus's KnowQL pattern: agents should be able to assemble all relevant context in a single typed query call rather than multiple round-trips. Commit 2026-05-16 added server-side embeddings, but if the MCP server only exposes raw note retrieval and not a semantic search tool, the agent still needs multiple tool calls to orient itself. Adding a `semantic_search(query: str, top_k: int, domain_filter: str)` MCP tool that returns ranked note summaries in one call directly addresses this.

## Cited evidence

- Topics/the-company-that-made-rag-mainstream-is-now-betting-against-.md
- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the MCP server module — likely src/mcp/ — and the embeddings module introduced 2026-05-16)
  - sql/  (find the table that stores embeddings — likely a column like embedding_json or a dedicated table)
  - CLAUDE.md

Goal: Add a single `semantic_search` tool to the MCP server that returns the top-K most semantically relevant vault notes for a query string, with optional domain filtering.

Step 1 — Understand existing embedding storage:
  Open the embeddings module. Confirm:
    a. Which SQL table stores embeddings (column name, data type — likely NVARCHAR(MAX) JSON array or VARBINARY).
    b. Which embedding model/provider is used (e.g., text-embedding-3-small, Voyage, etc.).
    c. Whether embeddings are stored as JSON float arrays or binary.

Step 2 — Implement cosine similarity search (src/search/semantic.py):
  `async def semantic_search(query: str, top_k: int = 10, domain_filter: str = None) -> list[dict]`:
    a. Embed the query using the same provider/model already in use.
    b. Fetch all rows from the embeddings table: SELECT slug, title, domain, summary, embedding_json FROM vault_nodes WHERE embedding_json IS NOT NULL [AND domain = domain_filter IF provided].
    c. Deserialize each embedding_json to a list[float].
    d. Compute cosine similarity between query embedding and each note embedding (use numpy if available, else pure Python).
    e. Return top_k results sorted by similarity descending, each as:
       {"slug": ..., "title": ..., "domain": ..., "summary": ..., "score": <float rounded to 4dp>}

  Performance note: if vault has >5000 notes, add a warning log and consider fetching only notes updated in the last 90 days unless domain_filter is set.

Step 3 — Register the MCP tool:
  In the MCP server module, add:
    @mcp.tool()
    async def semantic_search_tool(query: str, top_k: int = 10, domain: str = None) -> str:
        results = await semantic_search(query, top_k=top_k, domain_filter=domain)
        return json.dumps(results, indent=2)

  Tool description string: 'Search the knowledge vault by semantic similarity. Returns top_k note summaries ranked by relevance to query. Optional domain filter: agent-orchestration | seo | tech-support | office-ops.'

Step 4 — Update CLAUDE.md:
  Add a line under the MCP tools section:
    'Use semantic_search_tool as your FIRST action when starting any task that requires vault context. Pass the task description as the query.'

Edge cases:
  - If the query embedding call fails, raise a clear error (do not return empty results silently).
  - If no notes have embeddings yet (fresh install), return [] with a warning message in the JSON.
  - top_k must be clamped to max 50 to avoid returning the entire vault.
  - The tool must be async-safe (do not block the event loop on the DB fetch — use asyncio.to_thread if pyodbc is synchronous).

Verification:
  1. Start the MCP server locally.
  2. Call semantic_search_tool with query='multi-provider model routing' — confirm results include the note from commit 2026-05-24.
  3. Call with domain='seo' — confirm all returned notes have domain='seo'.
  4. Call with top_k=60 — confirm it is clamped to 50.
```
