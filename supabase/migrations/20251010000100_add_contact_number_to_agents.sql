-- Add contact_number to agents
ALTER TABLE public.agents
ADD COLUMN IF NOT EXISTS contact_number VARCHAR;

COMMENT ON COLUMN public.agents.contact_number IS 'Primary contact phone number for the agent (E.164 recommended)';

