-- ============================================================================
-- Identities Table for Cross-Channel Identity Unification
-- Version: 2025-01-20
-- ============================================================================
-- Purpose: Track user identities across channels, support anonymous→verified flow
-- ============================================================================

-- ============================================================================
-- Identities table
-- ============================================================================

CREATE TABLE IF NOT EXISTS identities (
    identity_id TEXT PRIMARY KEY,          -- "anon_telegram_123456" or "user_abc123"
    persistent_user_id TEXT,               -- NULL for anon, 'user_*' after merge
    channel TEXT,                          -- 'telegram', 'email', 'http'
    thread_id TEXT NOT NULL UNIQUE,        -- Thread this identity belongs to
    created_at TIMESTAMP DEFAULT NOW(),
    merged_at TIMESTAMP,                   -- NULL until merged
    verification_status TEXT DEFAULT 'anonymous',  -- 'anonymous', 'pending', 'verified'
    verification_method TEXT,              -- 'email', 'phone', 'oauth'
    verification_contact TEXT              -- Email/phone for verification
);

-- ============================================================================
-- Indexes for common queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_identities_persistent_user ON identities(persistent_user_id) WHERE persistent_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_identities_channel ON identities(channel);
CREATE INDEX IF NOT EXISTS idx_identities_verification ON identities(verification_status);
CREATE INDEX IF NOT EXISTS idx_identities_contact ON identities(verification_contact) WHERE verification_contact IS NOT NULL;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE identities IS 'Track user identities across channels with anonymous→verified flow';
COMMENT ON COLUMN identities.identity_id IS 'Display ID (anon_* for anonymous, immutable after creation)';
COMMENT ON COLUMN identities.persistent_user_id IS 'Unified user ID (NULL for anon, set after merge)';
COMMENT ON COLUMN identities.thread_id IS 'Thread/conversation ID (unique per identity)';
COMMENT ON COLUMN identities.verification_status IS 'anonymous → pending → verified';
COMMENT ON COLUMN identities.verification_contact IS 'Email/phone used for verification (for pending/verified)';
