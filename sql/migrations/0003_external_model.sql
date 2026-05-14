-- 0003_external_model.sql
-- Register the external embedding model used by AI_GENERATE_EMBEDDINGS.
-- SPEC default: text-embedding-3-small (1536). To change models or providers,
-- drop and recreate; if dim changes, also re-create dbo.notes.embedding and
-- re-embed all rows.
--
-- This script is INERT by default: it requires you to fill in the API key (or
-- set up Managed Identity / Service Principal credential) before it does
-- anything. Uncomment the CREATE blocks and supply your secret first.

USE cortex;
GO

-- ============================================================
-- Step 1 — provision a database-scoped credential
-- Replace the SECRET payload with your real API key (or use AAD/MI auth).
-- ============================================================
-- IF NOT EXISTS (SELECT 1 FROM sys.database_scoped_credentials WHERE name = 'EmbeddingCred')
-- BEGIN
--     CREATE DATABASE SCOPED CREDENTIAL EmbeddingCred
--     WITH IDENTITY = 'HTTPEndpointHeaders',
--          SECRET = '{"api-key":"<REPLACE_WITH_OPENAI_API_KEY>"}';
-- END
-- GO

-- ============================================================
-- Step 2 — register the external model
-- ============================================================
-- IF NOT EXISTS (SELECT 1 FROM sys.external_models WHERE name = 'EmbeddingModel')
-- BEGIN
--     CREATE EXTERNAL MODEL EmbeddingModel
--     WITH (
--         LOCATION   = 'https://api.openai.com/v1/embeddings',
--         API_FORMAT = 'OpenAI',
--         MODEL_TYPE = EMBEDDINGS,
--         MODEL      = 'text-embedding-3-small',
--         CREDENTIAL = EmbeddingCred
--     );
-- END
-- GO

-- ============================================================
-- Smoke test (run manually after provisioning)
-- ============================================================
-- DECLARE @v VECTOR(1536) = AI_GENERATE_EMBEDDINGS(N'hello world' USE MODEL EmbeddingModel);
-- SELECT @v AS embedding_sample;
-- GO

INSERT INTO dbo.schema_migrations(migration_name, notes)
SELECT '0003_external_model', 'external embedding model — INERT until API key provisioned'
WHERE NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_name = '0003_external_model');
GO
