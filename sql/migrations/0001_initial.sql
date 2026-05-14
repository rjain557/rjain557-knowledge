-- 0001_initial.sql
-- Core ingestion tables (SPEC §3.1, §3.3, §3.4, §3.9, §4).
-- Includes: processed_emails, processed_links, sources, notes.
-- Embeddings on dbo.notes use VECTOR(1536) — server-side via AI_GENERATE_EMBEDDINGS
-- against the EmbeddingModel registered in 0003.

USE cortex;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================
-- Email dedup (SPEC §3.1)
-- ============================================================
IF OBJECT_ID('dbo.processed_emails','U') IS NULL
CREATE TABLE dbo.processed_emails (
    email_id        BIGINT IDENTITY PRIMARY KEY,
    message_id      NVARCHAR(500)  NOT NULL,            -- Graph internetMessageId
    sender          NVARCHAR(500)  NULL,
    subject         NVARCHAR(1000) NULL,
    received_at     DATETIME2      NOT NULL,
    body_preview    NVARCHAR(2000) NULL,
    folder          NVARCHAR(200)  NULL,
    captured_at     DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    processed_at    DATETIME2      NULL,
    status          NVARCHAR(50)   NOT NULL DEFAULT 'received',
    metadata        JSON           NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_processed_emails_message_id' AND object_id = OBJECT_ID('dbo.processed_emails'))
CREATE UNIQUE INDEX UX_processed_emails_message_id ON dbo.processed_emails(message_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_processed_emails_received' AND object_id = OBJECT_ID('dbo.processed_emails'))
CREATE INDEX IX_processed_emails_received ON dbo.processed_emails(received_at DESC);
GO

-- ============================================================
-- Link dedup (SPEC §3.3)
-- ============================================================
IF OBJECT_ID('dbo.processed_links','U') IS NULL
CREATE TABLE dbo.processed_links (
    link_id         BIGINT IDENTITY PRIMARY KEY,
    email_id        BIGINT         NULL REFERENCES dbo.processed_emails(email_id),
    original_url    NVARCHAR(2000) NOT NULL,
    canonical_url   NVARCHAR(2000) NOT NULL,
    url_hash        BINARY(32)     NOT NULL,            -- SHA2_256(canonical_url) dedup key
    source_type     NVARCHAR(50)   NULL,
    classified_at   DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    status          NVARCHAR(50)   NOT NULL DEFAULT 'pending'
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_processed_links_url_hash' AND object_id = OBJECT_ID('dbo.processed_links'))
CREATE UNIQUE INDEX UX_processed_links_url_hash ON dbo.processed_links(url_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_processed_links_email' AND object_id = OBJECT_ID('dbo.processed_links'))
CREATE INDEX IX_processed_links_email ON dbo.processed_links(email_id);
GO

-- ============================================================
-- Sources (SPEC §3.4) — one row per extracted source
-- ============================================================
IF OBJECT_ID('dbo.sources','U') IS NULL
CREATE TABLE dbo.sources (
    source_id           BIGINT IDENTITY PRIMARY KEY,
    link_id             BIGINT         NULL REFERENCES dbo.processed_links(link_id),
    feed_id             BIGINT         NULL,                   -- FK to dbo.feed_sources added in 0004
    source_url          NVARCHAR(2000) NOT NULL,
    canonical_url       NVARCHAR(2000) NOT NULL,
    url_hash            BINARY(32)     NOT NULL,
    source_type         NVARCHAR(50)   NOT NULL,
        -- article | youtube | tiktok | repo | pdf | arxiv | twitter | reddit
        -- | hackernews | podcast | code_artifact
    title               NVARCHAR(1000) NULL,
    author              NVARCHAR(500)  NULL,
    published_at        DATETIME2      NULL,
    captured_at         DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    body_markdown       NVARCHAR(MAX)  NULL,
    transcript          NVARCHAR(MAX)  NULL,
    metadata            JSON           NULL,
    raw_blob_path       NVARCHAR(1000) NULL,
    code_artifacts      JSON           NULL,
    extractor           NVARCHAR(100)  NULL,
    extraction_status   NVARCHAR(50)   NOT NULL DEFAULT 'ok'  -- ok | partial | failed
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_sources_url_hash' AND object_id = OBJECT_ID('dbo.sources'))
CREATE UNIQUE INDEX UX_sources_url_hash ON dbo.sources(url_hash);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_sources_captured' AND object_id = OBJECT_ID('dbo.sources'))
CREATE INDEX IX_sources_captured ON dbo.sources(captured_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_sources_type_captured' AND object_id = OBJECT_ID('dbo.sources'))
CREATE INDEX IX_sources_type_captured ON dbo.sources(source_type, captured_at DESC);
GO

-- ============================================================
-- Notes (SPEC §3.9, §4.2) — vault note mirror with embeddings
-- ============================================================
IF OBJECT_ID('dbo.notes','U') IS NULL
CREATE TABLE dbo.notes (
    note_id         BIGINT IDENTITY PRIMARY KEY,
    source_id       BIGINT         NULL REFERENCES dbo.sources(source_id),
    vault_path      NVARCHAR(1000) NOT NULL,                    -- /Inbox/.../foo.md
    note_type       NVARCHAR(50)   NOT NULL,                    -- source | topic | author | library | framework | benchmark | pattern | lesson | review | proposal | health
    domain          NVARCHAR(100)  NULL,                        -- agent-orchestration | seo-agents | tech-support-agents
    title           NVARCHAR(1000) NULL,
    body_markdown   NVARCHAR(MAX)  NULL,
    frontmatter     JSON           NULL,
    tags            JSON           NULL,
    status          NVARCHAR(50)   NOT NULL DEFAULT 'raw',      -- raw | curated | archived
    embedding       VECTOR(1536)   NULL,
    embedded_at     DATETIME2      NULL,
    created_at      DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at      DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    archived_at     DATETIME2      NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_notes_vault_path' AND object_id = OBJECT_ID('dbo.notes'))
CREATE UNIQUE INDEX UX_notes_vault_path ON dbo.notes(vault_path);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_notes_type_domain' AND object_id = OBJECT_ID('dbo.notes'))
CREATE INDEX IX_notes_type_domain ON dbo.notes(note_type, domain);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_notes_source' AND object_id = OBJECT_ID('dbo.notes'))
CREATE INDEX IX_notes_source ON dbo.notes(source_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_notes_updated' AND object_id = OBJECT_ID('dbo.notes'))
CREATE INDEX IX_notes_updated ON dbo.notes(updated_at DESC);
GO

INSERT INTO dbo.schema_migrations(migration_name, notes)
SELECT '0001_initial', 'core ingestion tables'
WHERE NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_name = '0001_initial');
GO
