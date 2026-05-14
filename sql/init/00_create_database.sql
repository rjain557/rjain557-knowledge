-- Cortex / Inbox Brain — database bootstrap.
-- Apply once against the SQL Server instance, then run sql/migrations/0001..0007
-- against the new database in order.

USE master;
GO

IF DB_ID('cortex') IS NULL
BEGIN
    CREATE DATABASE cortex
    COLLATE SQL_Latin1_General_CP1_CI_AS;
END
GO

ALTER DATABASE cortex SET RECOVERY SIMPLE;
ALTER DATABASE cortex SET QUOTED_IDENTIFIER ON;
ALTER DATABASE cortex SET ANSI_NULL_DEFAULT ON;
ALTER DATABASE cortex SET ANSI_PADDING ON;
ALTER DATABASE cortex SET ANSI_WARNINGS ON;
ALTER DATABASE cortex SET ARITHABORT ON;
ALTER DATABASE cortex SET CONCAT_NULL_YIELDS_NULL ON;
ALTER DATABASE cortex SET QUERY_STORE = ON;
GO

-- Tracking table for migration application order (used by future scripts).
USE cortex;
GO

IF OBJECT_ID('dbo.schema_migrations','U') IS NULL
CREATE TABLE dbo.schema_migrations (
    migration_name NVARCHAR(200) NOT NULL PRIMARY KEY,
    applied_at     DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    notes          NVARCHAR(MAX) NULL
);
GO
