-- Email-linked, multi-method identity model.
--
-- Moves the canonical linking key from phone to EMAIL while keeping phone
-- unique-when-present (no longer required/primary). Mirrors Supabase native
-- identity-linking, which collapses Google + email-signup with the same
-- CONFIRMED email into one auth user. Local users remain keyed on
-- supabase_user_id; email becomes the unique linking key (partial unique
-- WHERE email IS NOT NULL).
--
-- SAFE on production data: existing rows are phone-keyed, emails may be NULL
-- or duplicated. De-duplication is NON-DESTRUCTIVE (no rows are deleted; they
-- may own properties/visits) — duplicate emails are nulled on all but the
-- earliest row.

-- =========================================================================
-- a. email_verified column (+ backfill from is_verified where email present)
-- =========================================================================
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE public.users
   SET email_verified = is_verified
 WHERE email IS NOT NULL
   AND trim(email) != '';

-- =========================================================================
-- b. Normalize empty-string emails to NULL
-- =========================================================================
UPDATE public.users
   SET email = NULL
 WHERE email IS NOT NULL
   AND trim(email) = '';

-- =========================================================================
-- c. De-duplicate emails NON-DESTRUCTIVELY: keep earliest id, NULL the rest.
--    Never delete rows (they may own properties/visits).
-- =========================================================================
WITH email_duplicates AS (
    SELECT email, MIN(id) AS keep_id
      FROM public.users
     WHERE email IS NOT NULL
     GROUP BY email
    HAVING COUNT(*) > 1
)
UPDATE public.users
   SET email = NULL
 WHERE email IN (SELECT email FROM email_duplicates)
   AND id NOT IN (SELECT keep_id FROM email_duplicates);

-- =========================================================================
-- d. Replace the non-unique email index with a partial UNIQUE index.
--    The legacy index from 20250830000100 is named idx_users_email.
-- =========================================================================
DROP INDEX IF EXISTS idx_users_email;
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email
    ON public.users (email)
    WHERE email IS NOT NULL;

-- =========================================================================
-- e. last_auth_method (TEXT + CHECK over the 5 allowed values, or NULL) and
--    last_auth_method_at.
-- =========================================================================
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS last_auth_method TEXT;

ALTER TABLE public.users
    DROP CONSTRAINT IF EXISTS ck_users_last_auth_method;
ALTER TABLE public.users
    ADD CONSTRAINT ck_users_last_auth_method
        CHECK (
            last_auth_method IS NULL
            OR last_auth_method IN (
                'google',
                'email_password',
                'phone_password',
                'phone_otp',
                'email_otp'
            )
        );

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS last_auth_method_at TIMESTAMPTZ;

-- =========================================================================
-- f. phone is left as-is (unique-when-present, nullable). No change.
-- =========================================================================
