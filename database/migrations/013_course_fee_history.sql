-- Migration: 013_course_fee_history
-- Description: Creates dedicated audit trail table for Course Institute Fee revisions.

CREATE TABLE IF NOT EXISTS course_fee_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    old_fee NUMERIC NOT NULL CHECK (old_fee >= 0.0),
    new_fee NUMERIC NOT NULL CHECK (new_fee >= 0.0),
    changed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    changed_by_username TEXT NOT NULL,
    reason TEXT NOT NULL,
    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT,
    CHECK (old_fee <> new_fee)
);

CREATE INDEX IF NOT EXISTS idx_course_fee_history_course_id ON course_fee_history(course_id);
CREATE INDEX IF NOT EXISTS idx_course_fee_history_changed_at ON course_fee_history(changed_at);
