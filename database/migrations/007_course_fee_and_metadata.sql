-- Migration: 007_course_fee_and_metadata
-- Description: Expands the Course entity with financial base_fee, duration, category, and audit timestamps.

-- 1. Add financial and descriptive metadata
ALTER TABLE courses ADD COLUMN base_fee NUMERIC NOT NULL DEFAULT 0.0;
ALTER TABLE courses ADD COLUMN duration TEXT;
ALTER TABLE courses ADD COLUMN category TEXT DEFAULT 'General';
ALTER TABLE courses ADD COLUMN description TEXT;

-- 2. Add audit timestamp columns with SQLite ALTER TABLE compatibility
ALTER TABLE courses ADD COLUMN created_at DATETIME;
ALTER TABLE courses ADD COLUMN updated_at DATETIME;

-- 3. Backfill created_at for any pre-existing course records
UPDATE courses SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;

-- 4. Auto-populate created_at on future INSERTs when not explicitly provided
CREATE TRIGGER IF NOT EXISTS trg_courses_created_at 
AFTER INSERT ON courses 
FOR EACH ROW 
WHEN NEW.created_at IS NULL 
BEGIN 
    UPDATE courses SET created_at = CURRENT_TIMESTAMP WHERE id = NEW.id; 
END;
