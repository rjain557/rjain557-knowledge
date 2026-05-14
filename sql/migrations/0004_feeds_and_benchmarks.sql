-- 0004_feeds_and_benchmarks.sql
-- Direct-feed ingestion + library/benchmark tracking (SPEC §3.2, §3.4, §3.8).
-- Adds: feed_sources, processed_feed_items, tracked_libraries, benchmark_snapshots
-- and the FK from dbo.sources.feed_id back to dbo.feed_sources.

USE cortex;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

-- ============================================================
-- Feed sources (configured in config/tracked-feeds.yaml, mirrored here)
-- ============================================================
IF OBJECT_ID('dbo.feed_sources','U') IS NULL
CREATE TABLE dbo.feed_sources (
    feed_id              BIGINT IDENTITY PRIMARY KEY,
    name                 NVARCHAR(200)  NOT NULL,
    feed_type            NVARCHAR(50)   NOT NULL,         -- arxiv | rss | github_trending | benchmark_leaderboard
    url                  NVARCHAR(1000) NOT NULL,
    config               JSON           NULL,             -- per-feed knobs (categories, keywords, max_per_poll, etc.)
    poll_interval_hours  INT            NOT NULL DEFAULT 6,
    last_polled_at       DATETIME2      NULL,
    last_success_at      DATETIME2      NULL,
    consecutive_failures INT            NOT NULL DEFAULT 0,
    status               NVARCHAR(50)   NOT NULL DEFAULT 'active',  -- active | paused | under_review | retired
    notes                NVARCHAR(MAX)  NULL,
    created_at           DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_feed_sources_name' AND object_id = OBJECT_ID('dbo.feed_sources'))
CREATE UNIQUE INDEX UX_feed_sources_name ON dbo.feed_sources(name);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_feed_sources_due' AND object_id = OBJECT_ID('dbo.feed_sources'))
CREATE INDEX IX_feed_sources_due ON dbo.feed_sources(status, last_polled_at);
GO

-- ============================================================
-- Wire dbo.sources.feed_id -> dbo.feed_sources(feed_id)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_sources_feed_id')
ALTER TABLE dbo.sources
  ADD CONSTRAINT FK_sources_feed_id FOREIGN KEY (feed_id) REFERENCES dbo.feed_sources(feed_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_sources_feed' AND object_id = OBJECT_ID('dbo.sources'))
CREATE INDEX IX_sources_feed ON dbo.sources(feed_id, captured_at DESC);
GO

-- ============================================================
-- Feed item dedup (one row per consumed item — stable per-feed item_id)
-- ============================================================
IF OBJECT_ID('dbo.processed_feed_items','U') IS NULL
CREATE TABLE dbo.processed_feed_items (
    feed_item_id    BIGINT IDENTITY PRIMARY KEY,
    feed_id         BIGINT         NOT NULL REFERENCES dbo.feed_sources(feed_id),
    external_id     NVARCHAR(500)  NOT NULL,             -- arXiv ID, RSS guid, etc.
    item_url        NVARCHAR(2000) NULL,
    title           NVARCHAR(1000) NULL,
    published_at    DATETIME2      NULL,
    captured_at     DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    source_id       BIGINT         NULL REFERENCES dbo.sources(source_id),
    status          NVARCHAR(50)   NOT NULL DEFAULT 'extracted',
    raw_metadata    JSON           NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_processed_feed_items_feed_extid' AND object_id = OBJECT_ID('dbo.processed_feed_items'))
CREATE UNIQUE INDEX UX_processed_feed_items_feed_extid ON dbo.processed_feed_items(feed_id, external_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_processed_feed_items_captured' AND object_id = OBJECT_ID('dbo.processed_feed_items'))
CREATE INDEX IX_processed_feed_items_captured ON dbo.processed_feed_items(captured_at DESC);
GO

-- ============================================================
-- Tracked libraries / repos (auto-discovered from github_trending + manual adds)
-- ============================================================
IF OBJECT_ID('dbo.tracked_libraries','U') IS NULL
CREATE TABLE dbo.tracked_libraries (
    library_id           BIGINT IDENTITY PRIMARY KEY,
    name                 NVARCHAR(200)  NOT NULL,
    repo                 NVARCHAR(300)  NOT NULL,             -- owner/repo
    homepage_url         NVARCHAR(1000) NULL,
    domain               NVARCHAR(100)  NULL,                  -- agent-orchestration | seo-agents | tech-support-agents
    stars                INT            NULL,
    last_release_at      DATETIME2      NULL,
    last_commit_at       DATETIME2      NULL,
    last_checked         DATETIME2      NULL,
    check_interval_days  INT            NOT NULL DEFAULT 7,
    activity_score       DECIMAL(5,3)   NULL,
    status               NVARCHAR(50)   NOT NULL DEFAULT 'tracking',  -- tracking | dormant | retired
    metadata             JSON           NULL,
    created_at           DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_tracked_libraries_repo' AND object_id = OBJECT_ID('dbo.tracked_libraries'))
CREATE UNIQUE INDEX UX_tracked_libraries_repo ON dbo.tracked_libraries(repo);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tracked_libraries_due' AND object_id = OBJECT_ID('dbo.tracked_libraries'))
CREATE INDEX IX_tracked_libraries_due ON dbo.tracked_libraries(status, last_checked);
GO

-- ============================================================
-- Benchmark snapshots (SPEC §3.2 benchmark_leaderboard)
-- ============================================================
IF OBJECT_ID('dbo.benchmark_snapshots','U') IS NULL
CREATE TABLE dbo.benchmark_snapshots (
    snapshot_id     BIGINT IDENTITY PRIMARY KEY,
    benchmark_name  NVARCHAR(200)  NOT NULL,             -- swe-bench, gaia, oswold, agentbench, webarena, ...
    feed_id         BIGINT         NULL REFERENCES dbo.feed_sources(feed_id),
    captured_at     DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),
    leaderboard     JSON           NOT NULL,             -- normalized [{rank,name,score,model,date,...}, ...]
    metadata        JSON           NULL,
    diff_from_prev  JSON           NULL                  -- structured diff vs last snapshot for the same benchmark
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_benchmark_snapshots_bn_date' AND object_id = OBJECT_ID('dbo.benchmark_snapshots'))
CREATE INDEX IX_benchmark_snapshots_bn_date ON dbo.benchmark_snapshots(benchmark_name, captured_at DESC);
GO

INSERT INTO dbo.schema_migrations(migration_name, notes)
SELECT '0004_feeds_and_benchmarks', 'feed_sources, processed_feed_items, tracked_libraries, benchmark_snapshots + sources.feed_id FK'
WHERE NOT EXISTS (SELECT 1 FROM dbo.schema_migrations WHERE migration_name = '0004_feeds_and_benchmarks');
GO
