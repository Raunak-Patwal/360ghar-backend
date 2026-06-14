-- Sync properties.owner_name from the owner's users.full_name.
--
-- Background: properties.owner_name is a denormalized cache of the owning
-- user's display name, but no app code ever wrote it, so it was stale/NULL and
-- diverged from the live name shown elsewhere (e.g. the flatmates owner modal,
-- which reads users.full_name via /flatmates/profiles/{id}). This makes
-- users.full_name the single source of truth and keeps owner_name in sync via
-- triggers so it can never drift again.

-- (a) Backfill: set owner_name from the owner's current full_name where missing/stale.
UPDATE public.properties p
SET owner_name = u.full_name
FROM public.users u
WHERE p.owner_id = u.id
  AND p.owner_name IS DISTINCT FROM u.full_name;

-- (b) Keep owner_name in sync when a user's full_name changes.
CREATE OR REPLACE FUNCTION public.sync_owner_name_on_user_rename()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    UPDATE public.properties
    SET owner_name = NEW.full_name
    WHERE owner_id = NEW.id
      AND owner_name IS DISTINCT FROM NEW.full_name;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_users_sync_owner_name ON public.users;
CREATE TRIGGER trg_users_sync_owner_name
AFTER UPDATE OF full_name ON public.users
FOR EACH ROW
EXECUTE FUNCTION public.sync_owner_name_on_user_rename();

-- (c) Set owner_name when a property is created or its owner_id changes.
-- (BEFORE trigger so the value is authoritative regardless of app code.)
CREATE OR REPLACE FUNCTION public.set_property_owner_name()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    owner_full_name TEXT;
BEGIN
    IF TG_OP = 'INSERT' OR NEW.owner_id IS DISTINCT FROM OLD.owner_id THEN
        SELECT full_name INTO owner_full_name FROM public.users WHERE id = NEW.owner_id;
        NEW.owner_name := owner_full_name;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_properties_set_owner_name ON public.properties;
CREATE TRIGGER trg_properties_set_owner_name
BEFORE INSERT OR UPDATE OF owner_id ON public.properties
FOR EACH ROW
EXECUTE FUNCTION public.set_property_owner_name();
