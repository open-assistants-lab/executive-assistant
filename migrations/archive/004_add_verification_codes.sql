-- ============================================================================
-- Add Verification Code Support to Identities Table
-- Version: 2025-01-20
-- ============================================================================
-- Purpose: Store verification codes for identity merge flow
-- ============================================================================

-- Add verification code columns
ALTER TABLE identities
ADD COLUMN IF NOT EXISTS verification_code TEXT,
ADD COLUMN IF NOT EXISTS code_expires_at TIMESTAMP;

-- Add index for code lookups
CREATE INDEX IF NOT EXISTS idx_identities_verification_code
ON identities(verification_code, code_expires_at)
WHERE verification_code IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN identities.verification_code IS 'Verification code for merge (email/SMS)';
COMMENT ON COLUMN identities.code_expires_at IS 'Code expiration time (typically 15 minutes)';
