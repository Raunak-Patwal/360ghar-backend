-- Add 'apple' to the allowed last_auth_method values.
--
-- Sign in with Apple is being added to the mobile apps, so the backend must
-- accept 'apple' as an auth method. Drops and recreates the CHECK constraint
-- introduced in 20260606000000 to ALSO allow 'apple' (keeps the existing 5
-- values + NULL). Idempotent: DROP CONSTRAINT IF EXISTS then ADD CONSTRAINT.

ALTER TABLE public.users
    DROP CONSTRAINT IF EXISTS ck_users_last_auth_method;
ALTER TABLE public.users
    ADD CONSTRAINT ck_users_last_auth_method
        CHECK (
            last_auth_method IS NULL
            OR last_auth_method IN (
                'google',
                'apple',
                'email_password',
                'phone_password',
                'phone_otp',
                'email_otp'
            )
        );
