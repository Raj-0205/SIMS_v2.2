-- Migration: 003_course_and_bridge
-- Description: Creates the Course entity and the Admission-Course bridge table.

-- 1. Course Foundation
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    
    status TEXT NOT NULL 
        CHECK (
            status IN ('ACTIVE', 'INACTIVE')
        ) DEFAULT 'ACTIVE'
);

-- 2. Admission-Course Bridge (Many-to-Many)
CREATE TABLE IF NOT EXISTS admission_courses (
    admission_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    
    -- Composite Primary Key ensures a student can't be registered to the EXACT same course in the SAME admission twice
    PRIMARY KEY (admission_id, course_id),
    
    -- ERP Rule: No orphan records, strict history preservation.
    FOREIGN KEY (admission_id) REFERENCES admissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT
);

-- Indexes for reverse lookups (e.g., finding all admissions for a specific course)
CREATE INDEX IF NOT EXISTS idx_admission_courses_course_id ON admission_courses(course_id);
