-- usp_upsert_note
-- Insert or update a note row. Called by src/cortex/vault/writer.py after
-- every vault write so dbo.notes stays in sync with the markdown file.
--
-- Returns: note_id of the upserted row.

CREATE OR ALTER PROCEDURE dbo.usp_upsert_note
    @vault_path     NVARCHAR(2000),
    @source_id      BIGINT         = NULL,
    @title          NVARCHAR(1000),
    @note_type      NVARCHAR(100),
    @domain         NVARCHAR(100)  = NULL,
    @body_markdown  NVARCHAR(MAX),
    @frontmatter    NVARCHAR(MAX)  = NULL,   -- JSON
    @tags           NVARCHAR(MAX)  = NULL    -- JSON array of strings
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @note_id BIGINT;

    -- Check if a row already exists for this vault path
    SELECT @note_id = note_id
    FROM   dbo.notes
    WHERE  vault_path = @vault_path;

    IF @note_id IS NOT NULL
    BEGIN
        UPDATE dbo.notes
        SET    title         = @title,
               note_type     = @note_type,
               domain        = @domain,
               body_markdown = @body_markdown,
               frontmatter   = TRY_CAST(@frontmatter AS NVARCHAR(MAX)),
               tags          = TRY_CAST(@tags        AS NVARCHAR(MAX)),
               updated_at    = SYSUTCDATETIME()
        WHERE  note_id = @note_id;
    END
    ELSE
    BEGIN
        INSERT INTO dbo.notes
               (source_id, vault_path, title, note_type, domain,
                body_markdown, frontmatter, tags)
        VALUES (@source_id, @vault_path, @title, @note_type, @domain,
                @body_markdown,
                TRY_CAST(@frontmatter AS NVARCHAR(MAX)),
                TRY_CAST(@tags        AS NVARCHAR(MAX)));

        SET @note_id = SCOPE_IDENTITY();
    END

    SELECT @note_id AS note_id;
END;
GO
