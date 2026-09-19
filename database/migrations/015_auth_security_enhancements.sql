-- Migration: 015_auth_security_enhancements
-- Description: Hardens user security state, extends OTP purposes, adds Break-Glass lease keys, and email change requests.

-- 1. Preflight duplicate check: abort migration if normalized duplicates exist
CREATE TEMPORARY TABLE IF NOT EXISTS _preflight_email_check (
    email TEXT UNIQUE NOT NULL
);
INSERT INTO _preflight_email_check (email)
SELECT lower(trim(email))
FROM users
WHERE email IS NOT NULL AND trim(email) != '';
DROP TABLE IF EXISTS _preflight_email_check;

-- 2. Extend users table with monotonic version and random stamp
ALTER TABLE users ADD COLUMN security_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE users ADD COLUMN security_stamp TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN password_changed_at DATETIME;
ALTER TABLE users ADD COLUMN failed_break_glass_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN break_glass_locked_until DATETIME;

-- Initialize stamps for existing accounts
UPDATE users 
SET security_stamp = lower(hex(randomblob(16))),
    password_changed_at = CURRENT_TIMESTAMP
WHERE security_stamp = '';

-- Drop legacy raw email index from Migration 014 to establish single authoritative normalized index
DROP INDEX IF EXISTS idx_users_email_unique;

-- Ensure case-insensitive uniqueness on email
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_normalized_unique 
ON users(lower(trim(email))) 
WHERE email IS NOT NULL AND email != '';

-- 3. Extend auth_otp_challenges with typed purpose
ALTER TABLE auth_otp_challenges ADD COLUMN purpose TEXT NOT NULL DEFAULT 'LOGIN';
CREATE INDEX IF NOT EXISTS idx_otp_challenges_user_purpose 
ON auth_otp_challenges(user_id, purpose, is_consumed);

-- 4. Break-Glass Recovery Keys Table with Lease Semantics & Delivery Metadata
CREATE TABLE IF NOT EXISTS auth_recovery_keys (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_hash                    TEXT NOT NULL,
    key_identifier              TEXT NOT NULL,              -- Opaque public handle, e.g. "REC-8F2B"
    status                      TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, PENDING_REMEDIATION, CONSUMED, REVOKED
    session_nonce               TEXT,                       -- SHA-256 hash of active recovery session nonce
    pending_session_id          TEXT,                       -- Unique identifier of claiming session
    pending_started_at          DATETIME,                   -- Timestamp when lease was claimed
    pending_expires_at          DATETIME,                   -- Timestamp when lease expires (started + 10m)
    delivery_status             TEXT NOT NULL DEFAULT 'PENDING',
    delivered_at                DATETIME,
    delivery_email_status       TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, DELIVERED, FAILED
    delivery_email_attempted_at DATETIME,
    delivery_email_error        TEXT,
    is_active                   BOOLEAN NOT NULL DEFAULT 1,
    created_at                  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at                   DATETIME,
    used_at                     DATETIME,
    consumed_at                 DATETIME,
    revoked_at                  DATETIME
);

-- Exactly one ACTIVE key per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_keys_single_active 
ON auth_recovery_keys(user_id) 
WHERE status = 'ACTIVE' AND is_active = 1;

CREATE INDEX IF NOT EXISTS idx_recovery_keys_lookup 
ON auth_recovery_keys(user_id, status);

-- 5. Dual-Verification Email Change Requests Table
CREATE TABLE IF NOT EXISTS auth_email_change_requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_token       TEXT UNIQUE NOT NULL,       -- Public lookup UUIDv4
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_email       TEXT NOT NULL,
    new_email           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, COMPLETED, EXPIRED, CANCELLED, STALE_CONFLICT
    current_verified    BOOLEAN NOT NULL DEFAULT 0,
    new_verified        BOOLEAN NOT NULL DEFAULT 0,
    expires_at          DATETIME NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at        DATETIME
);

CREATE INDEX IF NOT EXISTS idx_email_change_token 
ON auth_email_change_requests(request_token, status);

-- 6. Password Reset Tokens Table (for Normal Administrator Email Recovery)
CREATE TABLE IF NOT EXISTS auth_password_reset_tokens (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash          TEXT UNIQUE NOT NULL,       -- SHA-256 of raw bearer token
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_consumed         BOOLEAN NOT NULL DEFAULT 0,
    expires_at          DATETIME NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    consumed_at         DATETIME
);

CREATE INDEX IF NOT EXISTS idx_pwd_reset_lookup 
ON auth_password_reset_tokens(token_hash, is_consumed);
