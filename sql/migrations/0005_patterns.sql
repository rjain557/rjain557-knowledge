-- 0005_patterns.sql
-- Patterns, authors, relevance scores, GSD runs, synthesis runs.
-- (SPEC §3.5 relevance, §3.6 GSD, §3.10 synthesizer, §4.2 frontmatter)

USE cortex;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================
-- Authors (SPEC §3.7 get_author_profile, §3.11)
-- ============================================================
IF OBJECT_ID('dbo.authors','U') IS NULL
CREATE TABLE dbo.authors (
    author_id        BIGINT IDENTITY PRIMARY KEY,
    name             NVARCHAR(500)  NOT NULL,
    canonical_name   NVARCHAR(500)  NOT NULL,
    primary_url      NVARCHAR(1000) NULL,
    affiliations     JSON           NULL,
    aliases          JSON           NULL,
    hit_count        INT            NOT NULL DEFAULT 0,
    quality_score    DECIMAL(5,3)   NULL,
    last_seen_at     DATETIME2      NULL,
    first_seen_at    DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    status           NVARCHAR(50)   NOT NULL DEFAULT 'tracking',  -- tracking | watched | promoted | retired
    notes            NVARCHAR(MAX)  NULL,
    metadata         JSON           NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_authors_canonical_name' AND object_id = OBJECT_ID('dbo.authors'))
CREATE UNIQUE INDEX UX_authors_canonical_name ON dbo.authors(canonical_name);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_authors_quality' AND object_id = OBJECT_ID('dbo.authors'))
CREATE INDEX IX_authors_quality ON dbo.authors(quality_score DESC);
GO

-- ============================================================
-- Per-domain relevance scores (SPEC §3.5)
-- One row per (source, domain).
-- ============================================================
IF OBJECT_ID('dbo.relevance_scores','U') IS NULL
CREATE TABLE dbo.relevance_scores (
    score_id     BIGINT IDENTITY PRIMARY KEY,
    source_id    BIGINT         NOT NULL REFERENCES dbo.sources(source_id),
    domain       NVARCHAR(100)  NOT NULL,                -- agent-orchestration | seo-agents | tech-support-agents
    score        DECIMAL(5,4)   NOT NULL,                -- 0.0000–1.0000
    rationale    NVARCHAR(MAX)  NULL,
    components   JSON           NULL,                    -- per-axis sub-scores
    scored_at    DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    model        NVARCHAR(100)  NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_relevance_scores_source_domain' AND object_id = OBJECT_ID('dbo.relevance_scores'))
CREATE UNIQUE INDEX UX_relevance_scores_source_domain ON dbo.relevance_scores(source_id, domain);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_relevance_domain_score' AND object_id = OBJECT_ID('dbo.relevance_scores'))
CREATE INDEX IX_relevance_domain_score ON dbo.relevance_scores(domain, score DESC);
GO

-- ============================================================
-- GSD runs (SPEC §3.6) — Researcher → Plan → Execute → Verify per source
-- ============================================================
IF OBJECT_ID('dbo.gsd_runs','U') IS NULL
CREATE TABLE dbo.gsd_runs (
    run_id          BIGINT IDENTITY PRIMARY KEY,
    source_id       BIGINT         NULL REFERENCES dbo.sources(source_id),
    started_at      DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    finished_at     DATETIME2      NULL,
    status          NVARCHAR(50)   NOT NULL DEFAULT 'running',     -- running | passed | failed | retried
    phase           NVARCHAR(50)   NULL,                            -- research | plan | execute | verify
    research_log    JSON           NULL,
    [plan]          JSON           NULL,
    execute_log     JSON           NULL,
    verify_result   JSON           NULL,
    artifact_paths  JSON           NULL,                            -- vault paths produced
    failure_reason  NVARCHAR(MAX)  NULL,
    cost_usd        DECIMAL(8,4)   NULL,
    tokens_in       BIGINT         NULL,
    tokens_out      BIGINT         NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_gsd_runs_started' AND object_id = OBJECT_ID('dbo.gsd_runs'))
CREATE INDEX IX_gsd_runs_started ON dbo.gsd_runs(started_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_gsd_runs_source' AND object_id = OBJECT_ID('dbo.gsd_runs'))
CREATE INDEX IX_gsd_runs_source ON dbo.gsd_runs(source_id);
GO

-- ============================================================
-- Synthesis runs (SPEC §3.10) — cross-source rollups producing patterns
-- ============================================================
IF OBJECT_ID('dbo.synthesis_runs','U') IS NULL
CREATE TABLE dbo.synthesis_runs (
    synth_id        BIGINT IDENTITY PRIMARY KEY,
    domain          NVARCHAR(100)  NOT NULL,
    pattern_type    NVARCHAR(100)  NULL,
    trigger_kind    NVARCHAR(50)   NOT NULL,                 -- threshold | scheduled | manual
    started_at      DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    finished_at     DATETIME2      NULL,
    status          NVARCHAR(50)   NOT NULL DEFAULT 'running',
    candidate_source_ids JSON      NULL,
    output_pattern_ids   JSON      NULL,
    notes           NVARCHAR(MAX)  NULL,
    cost_usd        DECIMAL(8,4)   NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_synthesis_runs_domain_started' AND object_id = OBJECT_ID('dbo.synthesis_runs'))
CREATE INDEX IX_synthesis_runs_domain_started ON dbo.synthesis_runs(domain, started_at DESC);
GO

-- ============================================================
-- Patterns (SPEC §3.10) — primary artifact for consumer repos
-- ============================================================
IF OBJECT_ID('dbo.patterns','U') IS NULL
CREATE TABLE dbo.patterns (
    pattern_id      BIGINT IDENTITY PRIMARY KEY,
    note_id         BIGINT         NULL REFERENCES dbo.notes(note_id),
    name            NVARCHAR(300)  NOT NULL,
    slug            NVARCHAR(300)  NOT NULL,
    domain          NVARCHAR(100)  NOT NULL,
    pattern_type    NVARCHAR(100)  NOT NULL,                 -- orchestration | planning | memory | tool-use | reflection | diagnostic | ...
    summary         NVARCHAR(MAX)  NULL,
    body_markdown   NVARCHAR(MAX)  NULL,
    examples        JSON           NULL,
    source_ids      JSON           NOT NULL,                 -- corroborating source ids
    corroboration_count INT        NOT NULL DEFAULT 0,
    confidence      DECIMAL(5,4)   NOT NULL DEFAULT 0.5000,
    last_corroborated_at DATETIME2 NULL,
    embedding       VECTOR(1536)   NULL,
    embedded_at     DATETIME2      NULL,
    status          NVARCHAR(50)   NOT NULL DEFAULT 'active',-- candidate | active | decaying | archived
    created_at      DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at      DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    archived_at     DATETIME2      NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_patterns_domain_slug' AND object_id = OBJECT_ID('dbo.patterns'))
CREATE UNIQUE INDEX UX_patterns_domain_slug ON dbo.patterns(domain, slug);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_patterns_domain_type' AND object_id = OBJECT_ID('dbo.patterns'))
CREATE INDEX IX_patterns_domain_type ON dbo.patterns(domain, pattern_type, status);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_patterns_confidence' AND object_id = OBJECT_ID('dbo.patterns'))
CREATE INDEX IX_patterns_confidence ON dbo.patterns(domain, confidence DESC);
GO

-- Vector index on patterns.embedding — same DiskANN preview as 0002, best-effort.
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'VIX_patterns_embedding' AND object_id = OBJECT_ID('dbo.patterns'))
    BEGIN
        EXEC('CREATE VECTOR INDEX VIX_patterns_embedding ON dbo.patterns(embedding) WITH (METRIC = ''cosine'', TYPE = ''diskann'');');
    END
END TRY
BEGIN CATCH
    PRINT 'NOTE: CREATE VECTOR INDEX on dbo.patterns skipped — preview not available or syntax differs. ' + ERROR_MESSAGE();
END CATCH
GO

INSERT INTO dbo.schema_migrations(migration_name, notes)
SELECT '0005_patterns', 'authors, relevance_scores, gsd_runs, synthesis_runs, patterns'
WHERE NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_name = '0005_patterns');
GO
