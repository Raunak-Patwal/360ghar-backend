-- Targeted composite indexes for high-volume read paths.
-- These are additive and idempotent; no data is modified.

-- Swipe history: per-user newest pages and liked/disliked filters.
CREATE INDEX IF NOT EXISTS idx_user_swipes_user_created_at_desc
    ON user_swipes (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_swipes_user_liked_created_at_desc
    ON user_swipes (user_id, is_liked, created_at DESC);

-- Property management dashboard/reporting: owner-scoped date/status lookups.
CREATE INDEX IF NOT EXISTS idx_rent_payments_owner_paid_at_desc
    ON rent_payments (owner_id, paid_at DESC);

CREATE INDEX IF NOT EXISTS idx_rent_charges_owner_status_due_date
    ON rent_charges (owner_id, status, due_date);

CREATE INDEX IF NOT EXISTS idx_leases_owner_status_created_at_desc
    ON leases (owner_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_leases_property_status_created_at_desc
    ON leases (property_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_maintenance_requests_owner_created_at_desc
    ON maintenance_requests (owner_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_expenses_owner_expense_date_desc
    ON expenses (owner_id, expense_date DESC);

-- Media library keyset pagination.
CREATE INDEX IF NOT EXISTS idx_media_files_user_created_at_id_desc
    ON media_files (user_id, created_at DESC, id DESC);

-- Property feed sort orders. Partial indexes keep these focused on live feed rows.
CREATE INDEX IF NOT EXISTS idx_properties_feed_newest_available
    ON properties (created_at DESC, id DESC)
    WHERE is_available;

CREATE INDEX IF NOT EXISTS idx_properties_feed_popular_available
    ON properties (like_count DESC, view_count DESC, created_at DESC, id DESC)
    WHERE is_available;

CREATE INDEX IF NOT EXISTS idx_properties_feed_price_low_available
    ON properties (base_price ASC, id ASC)
    WHERE is_available;

CREATE INDEX IF NOT EXISTS idx_properties_feed_price_high_available
    ON properties (base_price DESC, id DESC)
    WHERE is_available;
