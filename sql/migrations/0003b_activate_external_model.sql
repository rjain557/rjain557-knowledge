-- 0003b_activate_external_model.sql
-- Activates the external embedding model that 0003 left inert.
-- OpenAI direct (NOT Azure OpenAI) — auth header is "Authorization: Bearer sk-..."
-- so the credential SECRET is the JSON shape SQL Server 2025 uses for
-- HTTPEndpointHeaders identity.
--
-- Safe to re-run: each block is guarded by an existence check; the
-- SECRET update path uses ALTER, not DROP/CREATE, so the model keeps
-- working through key rotations.

USE cortex;
GO

-- Enable database master key if not present (required for credentials)
IF NOT EXISTS (SELECT 1 FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
BEGIN
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = N'$(MASTER_KEY_PWD)';
END
GO

-- Database-scoped credential containing the Bearer header for OpenAI
IF NOT EXISTS (SELECT 1 FROM sys.database_scoped_credentials WHERE name = 'EmbeddingCred')
BEGIN
    CREATE DATABASE SCOPED CREDENTIAL EmbeddingCred
    WITH IDENTITY = 'HTTPEndpointHeaders',
         SECRET   = '$(OPENAI_HEADER_JSON)';
END
ELSE
BEGIN
    ALTER DATABASE SCOPED CREDENTIAL EmbeddingCred
    WITH IDENTITY = 'HTTPEndpointHeaders',
         SECRET   = '$(OPENAI_HEADER_JSON)';
END
GO

-- External model pointing at OpenAI's embeddings endpoint
IF NOT EXISTS (SELECT 1 FROM sys.external_models WHERE name = 'EmbeddingModel')
BEGIN
    CREATE EXTERNAL MODEL EmbeddingModel
    WITH (
        LOCATION   = 'https://api.openai.com/v1/embeddings',
        API_FORMAT = 'OpenAI',
        MODEL_TYPE = EMBEDDINGS,
        MODEL      = 'text-embedding-3-small',
        CREDENTIAL = EmbeddingCred
    );
END
GO

INSERT INTO dbo.schema_migrations(migration_name, notes)
SELECT '0003b_activate_external_model',
       'OpenAI text-embedding-3-small wired via DATABASE SCOPED CREDENTIAL'
WHERE NOT EXISTS (SELECT 1 FROM dbo.schema_migrations
                  WHERE migration_name = '0003b_activate_external_model');
GO

-- Smoke test — exercise the model. VECTOR can't be cast to NVARCHAR; check via VECTOR_NORM.
DECLARE @v VECTOR(1536) = AI_GENERATE_EMBEDDINGS(N'cortex embedding smoke test' USE MODEL EmbeddingModel);
SELECT VECTOR_NORM(@v, 'norm2') AS embedding_l2_norm,
       'Non-zero norm = embedding generated successfully' AS status;
GO
