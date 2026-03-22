-- Convert remaining naive amenity timestamps to timestamptz.
-- Existing values are interpreted as UTC during conversion.

begin;

alter table public.amenities
    alter column created_at type timestamptz
    using created_at at time zone 'UTC',
    alter column updated_at type timestamptz
    using updated_at at time zone 'UTC';

alter table public.property_amenities
    alter column created_at type timestamptz
    using created_at at time zone 'UTC';

commit;
