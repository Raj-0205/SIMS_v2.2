-- Migration: 017_security_audit_attempts.sql
-- Description: Creates table for security audit login attempts.

CREATE TABLE IF NOT EXISTS security_audit_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_time    DATETIME DEFAULT CURRENT_TIMESTAMP,
    identifier      TEXT NOT NULL,
    success         BOOLEAN NOT NULL,
    ip_address      TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_attempts_identifier ON security_audit_attempts(identifier);
CREATE INDEX IF NOT EXISTS idx_audit_attempts_time ON security_audit_attempts(attempt_time);
