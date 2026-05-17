-- usp_vector_search_notes
-- Embed @query_text via the registered OpenAI EmbeddingModel, then return
-- the top @top_k notes ranked by cosine distance to that embedding.
-- Optional @domain filters via dbo.relevance_scores OR dbo.notes.domain.
--
-- Used by cortex.repo_review.vault_search.find_relevant_notes().

CREATE OR ALTER PROCEDURE dbo.usp_vector_search_notes
    @query_text NVARCHAR(MAX),
    @top_k      INT           = 10,
    @domain     NVARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    -- DECLARE is required so the result is typed VECTOR(1536) instead of
    -- the raw JSON-ish AI_GENERATE_EMBEDDINGS output, which VECTOR_DISTANCE
    -- rejects when used inline.
    DECLARE @v VECTOR(1536) =
        AI_GENERATE_EMBEDDINGS(LEFT(@query_text, 30000) USE MODEL EmbeddingModel);

    IF @v IS NULL
    BEGIN
        SELECT TOP 0 CAST(NULL AS BIGINT) AS note_id,
                     CAST(NULL AS NVARCHAR(2000)) AS vault_path,
                     CAST(NULL AS NVARCHAR(1000)) AS title,
                     CAST(NULL AS NVARCHAR(100))  AS note_type,
                     CAST(NULL AS NVARCHAR(100))  AS domain,
                     CAST(NULL AS NVARCHAR(MAX))  AS preview,
                     CAST(NULL AS FLOAT)          AS distance;
        RETURN;
    END

    IF @domain IS NULL
    BEGIN
        SELECT TOP (@top_k)
               n.note_id, n.vault_path, n.title, n.note_type, n.domain,
               LEFT(n.body_markdown, 800) AS preview,
               VECTOR_DISTANCE('cosine', n.embedding, @v) AS distance
        FROM   dbo.notes n
        WHERE  n.embedding IS NOT NULL
        ORDER BY distance ASC;
    END
    ELSE
    BEGIN
        SELECT TOP (@top_k)
               n.note_id, n.vault_path, n.title, n.note_type, n.domain,
               LEFT(n.body_markdown, 800) AS preview,
               VECTOR_DISTANCE('cosine', n.embedding, @v) AS distance
        FROM   dbo.notes n
        LEFT JOIN dbo.relevance_scores rs
               ON rs.source_id = n.source_id AND rs.domain = @domain
        WHERE  n.embedding IS NOT NULL
          AND  (n.domain = @domain OR rs.score >= 0.3)
        ORDER BY distance ASC;
    END
END;
GO
