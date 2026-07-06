-- ============================================================
-- 360Ghar Schema — Flatmates Realtime Authorization
-- ============================================================
-- Supabase Realtime private Broadcast channel authorization for
-- per-user flatmates topics: flatmates:user:{local_user_id}
-- ============================================================

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "flatmates users receive own broadcasts" ON realtime.messages;

CREATE POLICY "flatmates users receive own broadcasts"
ON realtime.messages
FOR SELECT
TO authenticated
USING (
    CASE
        WHEN (SELECT realtime.topic()) ~ '^flatmates:user:[0-9]+$' THEN EXISTS (
            SELECT 1
            FROM public.users u
            WHERE u.id = split_part((SELECT realtime.topic()), ':', 3)::bigint
              AND u.supabase_user_id = (SELECT auth.uid())::text
              AND u.is_active IS TRUE
        )
        ELSE FALSE
    END
);
