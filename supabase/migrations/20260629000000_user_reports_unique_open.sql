-- Enforce at most one OPEN report per (reporter, reported) pair.
-- Backfill: keep the oldest open report per pair, mark the rest reviewed, then add the
-- partial unique index that the app-level dedup relies on for race safety.

UPDATE user_reports
SET status = 'reviewed'
WHERE id IN (
    SELECT id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY reporter_user_id, reported_user_id
                   ORDER BY created_at ASC
               ) AS rn
        FROM user_reports
        WHERE status = 'open'
    ) sub
    WHERE sub.rn > 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_reports_unique_open
ON user_reports (reporter_user_id, reported_user_id)
WHERE status = 'open';
