-- Expand property_type to support PG, flatmate, and commercial inventory.
ALTER TYPE property_type ADD VALUE IF NOT EXISTS 'pg';
ALTER TYPE property_type ADD VALUE IF NOT EXISTS 'flatmate';
ALTER TYPE property_type ADD VALUE IF NOT EXISTS 'office';
ALTER TYPE property_type ADD VALUE IF NOT EXISTS 'shop';
ALTER TYPE property_type ADD VALUE IF NOT EXISTS 'warehouse';

-- Add structured listing preferences for PG / flatmate matching.
ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS listing_preferences JSONB;

CREATE INDEX IF NOT EXISTS idx_properties_listing_preferences_gin
  ON public.properties
  USING GIN (listing_preferences);
