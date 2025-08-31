-- Remove UNIQUE constraint from users.email column to allow duplicate emails
-- This enables scenarios like family accounts or testing with shared email addresses

-- Drop the existing unique constraint on email
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_email_key;

-- Keep the index for performance but make it non-unique
DROP INDEX IF EXISTS users_email_key;
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email) WHERE email IS NOT NULL;