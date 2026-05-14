-- 0002_vector_index.sql
-- Enable preview features (DiskANN vector index) and create the index on
-- dbo.notes.embedding. SQL Server 2025 ships CREATE VECTOR INDEX as a preview
-- feature; preview features must be turned on at the database scope.
--
-- If you are running against a build without DiskANN preview enabled, the
-- CREATE VECTOR INDEX statement will fail. The index is not strictly required
-- for correctness — VECTOR_SEARCH falls back to a scan. Run this migration
-- once the instance has the preview feature available.

USE cortex;
GO

-- Enable preview features at the database scope. Required for DiskANN.
ALTER DATABASE SCOPED CONFIGURATION SET PREVIEW_FEATURES = ON;
GO

-- Guard with TRY/CATCH so the migration succeeds on builds where the syntax
-- has shifted or the preview is gated. The vector column itself already exists
-- from 0001; vector search will work without the index (just slower).
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'VIX_notes_embedding' AND object_id = OBJECT_ID('dbo.notes'))
    BEGIN
        EXEC('CREATE VECTOR INDEX VIX_notes_embedding ON dbo.notes(embedding) WITH (METRIC = ''cosine'', TYPE = ''diskann'');');
    END
END TRY
BEGIN CATCH
    PRINT 'NOTE: CREATE VECTOR INDEX skipped — preview not available or syntax differs in this build. Error: ' + ERROR_MESSAGE();
END CATCH
GO

INSERT INTO dbo.schema_migrations(migration_name, notes)
SELECT '0002_vector_index', 'DiskANN vector index on dbo.notes.embedding (preview)'
WHERE NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_name = '0002_vector_index');
GO
