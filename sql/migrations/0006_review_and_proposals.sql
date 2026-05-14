-- 0006_review_and_proposals.sql
-- 7-day self-review machinery (SPEC §3.12, §4.3).

USE cortex;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================
-- Self-review and self-improvement
-- ============================================================

IF OBJECT_ID('dbo.system_reviews','U') IS NULL
CREATE TABLE dbo.system_reviews (
    review_id                  BIGINT IDENTITY PRIMARY KEY,
    started_at                 DATETIME2     NOT NULL,
    finished_at                DATETIME2     NULL,
    period_days                INT           NOT NULL DEFAULT 7,
    triggered_by               NVARCHAR(50)  NOT NULL DEFAULT 'scheduled', -- scheduled | manual
    metrics_snapshot           JSON          NOT NULL,
    findings                   JSON          NULL,
    autonomous_changes_applied INT           NOT NULL DEFAULT 0,
    proposals_created          INT           NOT NULL DEFAULT 0,
    status                     NVARCHAR(50)  NOT NULL DEFAULT 'running',   -- running | passed | failed
    report_path                NVARCHAR(1000)NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_reviews_started' AND object_id = OBJECT_ID('dbo.system_reviews'))
CREATE INDEX IX_reviews_started ON dbo.system_reviews(started_at DESC);
GO

IF OBJECT_ID('dbo.proposed_changes','U') IS NULL
CREATE TABLE dbo.proposed_changes (
    proposal_id        BIGINT IDENTITY PRIMARY KEY,
    review_id          BIGINT        NULL REFERENCES dbo.system_reviews(review_id),
    proposed_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    category           NVARCHAR(100) NOT NULL,
        -- feed_change | domain_profile | threshold | tracking_addition | schema | cost | vault_structure | other
    title              NVARCHAR(500) NOT NULL,
    description        NVARCHAR(MAX) NOT NULL,
    rationale          NVARCHAR(MAX) NULL,
    impact             NVARCHAR(MAX) NULL,
    proposed_action    JSON          NOT NULL,
    vault_path         NVARCHAR(1000)NULL,
    status             NVARCHAR(50)  NOT NULL DEFAULT 'pending',
        -- pending | approved | rejected | applied | superseded
    decided_at         DATETIME2     NULL,
    decided_by         NVARCHAR(200) NULL,
    decision_notes     NVARCHAR(MAX) NULL,
    applied_at         DATETIME2     NULL,
    application_result JSON          NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_proposals_status' AND object_id = OBJECT_ID('dbo.proposed_changes'))
CREATE INDEX IX_proposals_status ON dbo.proposed_changes(status, proposed_at);
GO

IF OBJECT_ID('dbo.autonomous_changes','U') IS NULL
CREATE TABLE dbo.autonomous_changes (
    change_id    BIGINT IDENTITY PRIMARY KEY,
    review_id    BIGINT        NULL REFERENCES dbo.system_reviews(review_id),
    applied_at   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    category     NVARCHAR(100) NOT NULL,
    description  NVARCHAR(MAX) NOT NULL,
    target_table NVARCHAR(200) NULL,
    target_id    NVARCHAR(200) NULL,
    before_state JSON          NULL,
    after_state  JSON          NULL,
    reversible   BIT           NOT NULL DEFAULT 1,
    reverted_at  DATETIME2     NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_auto_changes_applied' AND object_id = OBJECT_ID('dbo.autonomous_changes'))
CREATE INDEX IX_auto_changes_applied ON dbo.autonomous_changes(applied_at DESC);
GO

-- ============================================================
-- Materialized rollup view used by the Reviewer's metric gathering
-- ============================================================
CREATE OR ALTER VIEW dbo.v_ingestion_quality_7d AS
SELECT
    s.source_type,
    s.feed_id,
    f.name AS feed_name,
    rs.domain,
    COUNT(*) AS items,
    AVG(rs.score) AS mean_score,
    SUM(CASE WHEN rs.score < 0.3 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS noise_rate
FROM dbo.sources s
LEFT JOIN dbo.feed_sources f ON f.feed_id = s.feed_id
LEFT JOIN dbo.relevance_scores rs ON rs.source_id = s.source_id
WHERE s.captured_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY s.source_type, s.feed_id, f.name, rs.domain;
GO

INSERT INTO dbo.schema_migrations(migration_name, notes)
SELECT '0006_review_and_proposals', 'system_reviews, proposed_changes, autonomous_changes + v_ingestion_quality_7d'
WHERE NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_name = '0006_review_and_proposals');
GO
