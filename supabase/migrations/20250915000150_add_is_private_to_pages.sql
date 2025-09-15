-- Add is_private flag to pages for public/private access
-- Migration: 20250915000150_add_is_private_to_pages

BEGIN;

-- Add column with default true (private by default)
ALTER TABLE pages
    ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT TRUE;

-- Backfill nulls to TRUE (in case of pre-existing rows)
UPDATE pages SET is_private = TRUE WHERE is_private IS NULL;

-- Ensure future rows default to TRUE
ALTER TABLE pages
    ALTER COLUMN is_private SET DEFAULT TRUE;

-- Optional: enforce NOT NULL now that backfill is done
ALTER TABLE pages
    ALTER COLUMN is_private SET NOT NULL;

-- Index for filtering by privacy
CREATE INDEX IF NOT EXISTS idx_pages_is_private ON pages(is_private);

COMMIT;

