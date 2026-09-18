-- Migration: 014_user_roles_email_and_otp
-- Description: Adds email, lockout tracking to users table and creates auth_otp_challenges table.

ALTER TABLE users ADD COLUMN email TEXT;
ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN locked_until DATETIME;
ALTER TABLE users ADD COLUMN updated_at DATETIME;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email) WHERE email IS NOT NULL AND email != '';

CREATE TABLE IF NOT EXISTS auth_otp_challenges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_token TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_hash TEXT NOT NULL,
    attempts_left INTEGER NOT NULL DEFAULT 3,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    expires_at DATETIME NOT NULL,
    is_consumed BOOLEAN NOT NULL DEFAULT 0,
    consumed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_otp_challenges_token ON auth_otp_challenges(challenge_token);
CREATE INDEX IF NOT EXISTS idx_otp_challenges_user_id ON auth_otp_challenges(user_id);
CREATE INDEX IF NOT EXISTS idx_otp_challenges_expires_at ON auth_otp_challenges(expires_at);
