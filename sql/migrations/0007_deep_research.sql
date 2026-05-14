-- 0007_deep_research.sql
-- Deep Research Pipeline tables (SPEC §3.13, v4.1).

USE cortex;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================
-- Deep research runs — one row per /deep-research invocation
-- ============================================================
IF OBJECT_ID('dbo.deep_research_runs','U') IS NULL
CREATE TABLE dbo.deep_research_runs (
    run_id              BIGINT IDENTITY PRIMARY KEY,
    topic               NVARCHAR(500) NOT NULL,
    triggered_by        NVARCHAR(50)  NOT NULL,                  -- manual | auto_post_ingest | reviewer_gap
    triggered_source_id BIGINT        NULL REFERENCES dbo.sources(source_id),
    domains             JSON          NOT NULL,
    started_at          DATETIME2     NOT NULL,
    finished_at         DATETIME2     NULL,
    sources_consulted   INT           NOT NULL DEFAULT 0,
    sources_cited       INT           NOT NULL DEFAULT 0,
    search_engines_used JSON          NULL,
    cost_usd            DECIMAL(8,4)  NULL,
    output_topic_path   NVARCHAR(1000) NULL,
    output_pattern_ids  JSON          NULL,
    citation_graph      JSON          NULL,
    status              NVARCHAR(50)  NOT NULL DEFAULT 'running',-- running | passed | failed | halted_cost
    failure_reason      NVARCHAR(MAX) NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_deep_research_started' AND object_id = OBJECT_ID('dbo.deep_research_runs'))
CREATE INDEX IX_deep_research_started ON dbo.deep_research_runs(started_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_deep_research_topic' AND object_id = OBJECT_ID('dbo.deep_research_runs'))
CREATE INDEX IX_deep_research_topic ON dbo.deep_research_runs(topic);
GO

-- ============================================================
-- Track which sub-question / search engine surfaced each source
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE Name = 'discovery_path' AND Object_ID = OBJECT_ID('dbo.sources'))
    ALTER TABLE dbo.sources ADD discovery_path JSON NULL;
GO

INSERT INTO dbo.schema_migrations(migration_name, notes)
SELECT '0007_deep_research', 'deep_research_runs + sources.discovery_path'
WHERE NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_name = '0007_deep_research');
GO
