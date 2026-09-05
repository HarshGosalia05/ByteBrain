-- 23_token_version_revocation.sql
-- Adds a token_version column to support session revocation.
-- When sign-out-all is called, token_version is incremented,
-- invalidating all existing JWTs for that user.

ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INT NOT NULL DEFAULT 1;
