-- usp_score_authors
-- EWMA quality-score update for dbo.authors, run nightly.
-- score_new = alpha * hit_rate_7d + (1-alpha) * score_old
-- where hit_rate_7d = fraction of this author's last 7-day sources that
-- scored ≥ 0.5 on any domain.

CREATE OR ALTER PROCEDURE dbo.usp_score_authors
    @alpha FLOAT = 0.3   -- EWMA weight for the new observation
AS
BEGIN
    SET NOCOUNT ON;

    WITH recent AS (
        SELECT
            a.author_id,
            COUNT(*)                                                        AS total,
            SUM(CASE WHEN rs.score >= 0.5 THEN 1 ELSE 0 END)               AS hits
        FROM   dbo.authors a
        JOIN   dbo.sources s  ON s.source_id IN (
                   SELECT source_id FROM dbo.notes
                   WHERE  domain IS NOT NULL
                     AND  created_at >= DATEADD(day, -7, GETUTCDATE())
               )
        LEFT JOIN dbo.relevance_scores rs ON rs.source_id = s.source_id
        WHERE  s.source_id IN (
                   SELECT source_id FROM dbo.notes
                   WHERE  created_at >= DATEADD(day, -7, GETUTCDATE()))
        GROUP BY a.author_id
    )
    UPDATE a
    SET    quality_score = @alpha * (CAST(r.hits AS FLOAT) / NULLIF(r.total, 0))
                         + (1.0 - @alpha) * a.quality_score,
           hit_count     = a.hit_count + r.hits,
           last_seen_at  = SYSUTCDATETIME()
    FROM   dbo.authors a
    JOIN   recent r ON r.author_id = a.author_id
    WHERE  r.total > 0;
END;
GO
