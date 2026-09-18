-- Migration: 012_student_secondary_contact_and_identity
-- Description: Add secondary_mobile column to students and relax single-column mobile uniqueness
-- to support shared family contact numbers while preserving index performance.

-- 1. Add secondary_mobile column to students table
ALTER TABLE students ADD COLUMN secondary_mobile TEXT;

-- 2. Drop the obsolete single-column unique index on mobile_number
DROP INDEX IF EXISTS idx_students_mobile_unique;

-- 3. Create non-unique lookup indexes on primary and secondary mobile numbers
CREATE INDEX IF NOT EXISTS idx_students_mobile_number ON students(mobile_number);
CREATE INDEX IF NOT EXISTS idx_students_secondary_mobile ON students(secondary_mobile);
