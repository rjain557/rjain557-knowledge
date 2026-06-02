---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: L (>1 week)
generated_at: 2026-06-02T03:02:04.796423-07:00
---

# Add a persistent knowledge-graph index layer on top of the flat Markdown vault

**Impact:** high  ·  **Effort:** L (>1 week)

## Rationale

Vault note [1] (Graphify/structural pre-indexing) and note [5] (persistent-memory AI brains) both document that flat file stores force agents to re-read and re-orient on every run — the 'orientation cost' problem. The commit history shows daily knowledge refreshes committing raw Markdown files, but there is no graph or compiled index layer. Adding a lightweight pre-computed graph (entity nodes + typed edges extracted once per note, stored in the SQL Server already present via pyodbc) would let the MCP server answer 'what notes relate to X' in a single SQL query instead of scanning all files each session.

## Cited evidence

- Topics/claude-code-just-got-a-huge-upgrade-theres-a-free-plugin-cal.md
- Topics/we-built-an-ai-brain-that-actually-fires-neurons-watches-you.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (scan all Python modules, especially any vault reader, MCP server, and DB layer)
  - sql/  (all .sql files — understand current schema)
  - knowledge/  (sample 5-10 .md files to understand frontmatter shape)
  - CLAUDE.md

Goal: Design and implement a knowledge-graph index that is populated incrementally whenever a new vault note is written, and queried by the MCP server.

Step 1 — Schema (sql/graph_index.sql):
  Create two tables if they don't exist:
    CREATE TABLE vault_nodes (
      id INT IDENTITY PRIMARY KEY,
      slug NVARCHAR(512) UNIQUE NOT NULL,   -- note filename without .md
      title NVARCHAR(1024),
      domain NVARCHAR(128),                 -- frontmatter 'domain' or inferred
      summary NVARCHAR(4000),               -- first 500 chars of body
      embedding_json NVARCHAR(MAX),         -- optional: store raw embedding vector as JSON array
      updated_at DATETIME2 DEFAULT GETUTCDATE()
    );
    CREATE TABLE vault_edges (
      id INT IDENTITY PRIMARY KEY,
      src_slug NVARCHAR(512) NOT NULL,
      dst_slug NVARCHAR(512) NOT NULL,
      edge_type NVARCHAR(64) NOT NULL,      -- 'wikilink' | 'tag_shared' | 'llm_related'
      weight FLOAT DEFAULT 1.0,
      UNIQUE (src_slug, dst_slug, edge_type)
    );

Step 2 — Indexer (src/graph/indexer.py):
  Write a function `index_note(path: Path) -> None` that:
    a. Parses frontmatter with python-frontmatter.
    b. Extracts [[wikilinks]] from body via regex.
    c. UPSERTs a vault_nodes row (use MERGE or INSERT … ON CONFLICT).
    d. For each wikilink target, UPSERTs a vault_edges row with edge_type='wikilink'.
    e. For notes sharing >=2 tags, UPSERTs edge_type='tag_shared'.
  Write `index_all_notes(vault_dir: Path) -> None` that walks the vault and calls index_note for each .md.

Step 3 — Hook into vault writer:
  Find the module that writes new vault notes (likely in src/vault/ or src/writer.py).
  After the file is written, call `index_note(new_path)`.

Step 4 — MCP tool:
  In the MCP server (src/mcp/ or similar), add a tool `graph_neighbors(slug: str, depth: int = 1) -> list[dict]`
  that runs:
    SELECT dst_slug, edge_type, weight FROM vault_edges WHERE src_slug = ? 
    UNION SELECT src_slug, edge_type, weight FROM vault_edges WHERE dst_slug = ?
  and returns the results as JSON.

Edge cases:
  - Wikilinks that reference notes not yet indexed: insert a stub vault_nodes row with title=slug, summary=NULL.
  - Notes with no frontmatter: infer domain from directory path.
  - Re-indexing an existing note must not duplicate edges (use UPSERT).
  - The indexer must be idempotent so `index_all_notes` can be run as a nightly repair job.

Verification:
  1. Run `python -m src.graph.indexer` against the knowledge/ directory.
  2. Query: SELECT COUNT(*) FROM vault_nodes; — should equal number of .md files.
  3. Query: SELECT TOP 10 src_slug, dst_slug, edge_type FROM vault_edges; — spot-check links.
  4. Call the MCP tool via the existing test harness or a quick script and confirm neighbors are returned.
```
