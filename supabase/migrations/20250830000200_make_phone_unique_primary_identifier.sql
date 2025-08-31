-- Make phone the primary unique identifier for users
-- This supports the switch from email-based to phone-based authentication

-- First, clean up any duplicate phone numbers by keeping the earliest created user
-- and setting duplicates to NULL (they can be updated later)
WITH phone_duplicates AS (
    SELECT phone, MIN(id) as keep_id
    FROM public.users 
    WHERE phone IS NOT NULL 
    AND trim(phone) != ''
    GROUP BY phone 
    HAVING COUNT(*) > 1
)
UPDATE public.users 
SET phone = NULL 
WHERE phone IN (SELECT phone FROM phone_duplicates) 
AND id NOT IN (SELECT keep_id FROM phone_duplicates);

-- Add unique constraint on phone
ALTER TABLE public.users ADD CONSTRAINT users_phone_unique UNIQUE (phone);

-- Create an index for performance (PostgreSQL automatically creates one for UNIQUE constraints, but being explicit)
CREATE INDEX IF NOT EXISTS idx_users_phone_unique ON public.users(phone) WHERE phone IS NOT NULL;