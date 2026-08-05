-- Faculty Settings module — single JSONB preferences column on users.
-- This is the only schema touch for the Settings module (plan 13, locked decision #13).
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB;
