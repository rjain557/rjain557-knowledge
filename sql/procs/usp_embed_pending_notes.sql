-- usp_embed_pending_notes
-- Backfill OpenAI embeddings for every dbo.notes row where embedding IS NULL.
-- Bounded by @max_batch to control cost. Idempotent — re-runs only NULL rows.

CREATE OR ALTER PROCEDURE dbo.usp_embed_pending_notes
    @max_batch INT = 100
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @done INT = 0, @failed INT = 0, @id BIGINT;

    DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
        SELECT TOP (@max_batch) note_id
        FROM   dbo.notes
        WHERE  embedding IS NULL
          AND  body_markdown IS NOT NULL
          AND  LEN(body_markdown) >= 10
        ORDER BY note_id;

    OPEN cur;
    FETCH NEXT FROM cur INTO @id;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        BEGIN TRY
            DECLARE @text NVARCHAR(MAX);
            SELECT @text = LEFT(ISNULL(title + N'. ', N'') + ISNULL(body_markdown, N''), 30000)
            FROM   dbo.notes WHERE note_id = @id;

            DECLARE @v VECTOR(1536) = AI_GENERATE_EMBEDDINGS(@text USE MODEL EmbeddingModel);

            IF @v IS NULL
                SET @failed = @failed + 1;
            ELSE
            BEGIN
                UPDATE dbo.notes
                SET    embedding = @v, embedded_at = SYSUTCDATETIME()
                WHERE  note_id = @id;
                SET @done = @done + 1;
            END
        END TRY
        BEGIN CATCH
            SET @failed = @failed + 1;
        END CATCH

        FETCH NEXT FROM cur INTO @id;
    END
    CLOSE cur; DEALLOCATE cur;

    SELECT @done AS embedded, @failed AS failed,
           (SELECT COUNT(*) FROM dbo.notes WHERE embedding IS NULL) AS still_pending;
END;
GO
