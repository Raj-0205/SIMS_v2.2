-- Migration: 021_create_attendance_system
-- Description: Creates batch_attendance_sessions and student_attendance_records tables for batch attendance tracking.

CREATE TABLE IF NOT EXISTS batch_attendance_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    session_date DATE NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('ONLINE', 'OFFLINE')) DEFAULT 'ONLINE',
    scanned_image_path TEXT,
    recorded_by TEXT,
    remarks TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    UNIQUE(batch_id, session_date)
);

CREATE TABLE IF NOT EXISTS student_attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES batch_attendance_sessions(id) ON DELETE CASCADE,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    admission_id INTEGER REFERENCES admissions(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK(status IN ('PRESENT', 'ABSENT')) DEFAULT 'ABSENT',
    marking_method TEXT NOT NULL CHECK(marking_method IN ('TOGGLE', 'OCR_SCAN', 'MANUAL_EDIT')) DEFAULT 'TOGGLE',
    confidence_score REAL DEFAULT 1.0,
    remarks TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, student_id)
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_batch_attendance_sessions_batch_date ON batch_attendance_sessions(batch_id, session_date);
CREATE INDEX IF NOT EXISTS idx_student_attendance_records_student ON student_attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_student_attendance_records_session ON student_attendance_records(session_id);
CREATE INDEX IF NOT EXISTS idx_student_attendance_records_batch ON student_attendance_records(batch_id);
CREATE INDEX IF NOT EXISTS idx_student_attendance_records_status ON student_attendance_records(status);
