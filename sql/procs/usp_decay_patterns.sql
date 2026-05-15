-- usp_decay_patterns
-- Daily confidence decay for patterns with no recent corroboration.
-- Patterns with confidence < archive_threshold are flagged for review.

CREATE OR ALTER PROCEDURE dbo.usp_decay_patterns
    @decay_rate          FLOAT = 0.97,
    @stale_days          INT   = 90,
    @archive_threshold   FLOAT = 0.2
AS
BEGIN
    SET NOCOUNT ON;

    -- Apply decay to stale patterns
    UPDATE dbo.patterns
    SET    confidence  = confidence * @decay_rate,
           updated_at  = SYSUTCDATETIME()
    WHERE  updated_at < DATEADD(day, -@stale_days, GETUTCDATE())
      AND  confidence  > @archive_threshold;

    -- Return patterns that dropped below archive threshold
    SELECT pattern_id, domain, pattern_type, name, confidence, updated_at
    FROM   dbo.patterns
    WHERE  confidence < @archive_threshold
      AND  status     = 'active'
    ORDER BY confidence ASC;
END;
GO
