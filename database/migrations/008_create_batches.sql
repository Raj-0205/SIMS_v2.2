-- Migration: 008_create_batches
-- Description: Creates the Batches master entity and relevant performance and constraint indexes.

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    batch_name TEXT NOT NULL,
    batch_code TEXT,
    timing TEXT NOT NULL,
    max_capacity INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (
        status IN ('OPEN', 'FULL', 'COMPLETED', 'CANCELLED', 'ARCHIVED')
    ) DEFAULT 'OPEN',
    start_date DATE,
    end_date DATE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_batches_course_id ON batches(course_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);

-- Scoped uniqueness: No two batches with the same name under the same course
CREATE UNIQUE INDEX IF NOT EXISTS idx_batches_course_batch_name ON batches(course_id, batch_name);
