-- Add role column to users for RBAC
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';

-- Backfill existing rows to 'user' explicitly (redundant with default, but ensures consistency)
UPDATE users SET role = 'user' WHERE role IS NULL;
