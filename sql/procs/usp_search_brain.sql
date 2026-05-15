-- usp_search_brain
-- Text-based fallback search used by the MCP server when vector search
-- is unavailable (DiskANN preview not active). Phase 2 will layer
-- VECTOR_SEARCH on top once embeddings are populated.

CREATE OR ALTER PROCEDURE dbo.usp_search_brain
    @query       NVARCHAR(500),
    @limit       INT            = 10,
    @domains     NVARCHAR(MAX)  = NULL,   -- JSON array, e.g. '["agent-orchestration"]'
    @note_types  NVARCHAR(MAX)  = NULL    -- JSON array, e.g. '["source","lesson"]'
AS
BEGIN
    SET NOCOUNT ON;

    SELECT TOP (@limit)
           n.note_id,
           n.vault_path,
           n.title,
           n.note_type,
           n.domain,
           n.tags,
           n.created_at,
           n.updated_at,
           -- simple relevance proxy: title match scores higher than body match
           CASE
               WHEN n.title         LIKE '%' + @query + '%' THEN 2.0
               WHEN n.body_markdown LIKE '%' + @query + '%' THEN 1.0
               ELSE 0.0
           END AS text_score
    FROM   dbo.notes n
    WHERE  (n.title LIKE '%' + @query + '%'
            OR n.body_markdown LIKE '%' + @query + '%')
      AND  (@domains    IS NULL
            OR EXISTS (
                SELECT 1
                FROM   OPENJSON(@domains)    WITH (val NVARCHAR(100) '$')
                WHERE  val = n.domain))
      AND  (@note_types IS NULL
            OR EXISTS (
                SELECT 1
                FROM   OPENJSON(@note_types) WITH (val NVARCHAR(100) '$')
                WHERE  val = n.note_type))
    ORDER BY text_score DESC, n.updated_at DESC;
END;
GO
