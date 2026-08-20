-- Migration: 005_student_mobile_unique
-- Description: Enforce unique constraint on non-empty student mobile numbers.

CREATE UNIQUE INDEX IF NOT EXISTS idx_students_mobile_unique 
ON students(mobile_number) 
WHERE mobile_number IS NOT NULL 
  AND TRIM(mobile_number) <> '';
