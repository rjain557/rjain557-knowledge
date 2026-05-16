-- usp_embed_note
-- Generate an OpenAI text-embedding-3-small vector for one note and store
-- it in dbo.notes.embedding. Truncates input to 30 000 chars (~7 500 tokens
-- — well under text-embedding-3-small's 8 192-token limit).
--
-- Call after every vault writer / deep_research upsert. Re-call to refresh
-- when the body changes.

CREATE OR ALTER PROCEDURE dbo.usp_embed_note
    @note_id BIGINT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @text NVARCHAR(MAX);
    SELECT @text = LEFT(ISNULL(title + N'. ', N'') + ISNULL(body_markdown, N''), 30000)
    FROM   dbo.notes
    WHERE  note_id = @note_id;

    IF @text IS NULL OR LEN(@text) < 10
    BEGIN
        SELECT @note_id AS note_id, NULL AS norm, 'SKIP: empty body' AS status;
        RETURN;
    END

    DECLARE @v VECTOR(1536) = AI_GENERATE_EMBEDDINGS(@text USE MODEL EmbeddingModel);

    IF @v IS NULL
    BEGIN
        SELECT @note_id AS note_id, NULL AS norm, 'FAIL: embedding returned NULL' AS status;
        RETURN;
    END

    UPDATE dbo.notes
    SET    embedding   = @v,
           embedded_at = SYSUTCDATETIME()
    WHERE  note_id = @note_id;

    SELECT @note_id AS note_id,
           VECTOR_NORM(@v, 'norm2') AS norm,
           'OK' AS status;
END;
GO
