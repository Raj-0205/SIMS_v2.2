-- Migration: 006_admission_candidate_number
-- Description: Adds yearly candidate sequencing (YYYY-NNN) to the Admissions entity.

ALTER TABLE admissions ADD COLUMN candidate_year INTEGER;
ALTER TABLE admissions ADD COLUMN candidate_sequence INTEGER;

-- Composite unique index to ensure sequence uniqueness within each calendar year
CREATE UNIQUE INDEX IF NOT EXISTS idx_admissions_yearly_candidate
ON admissions(candidate_year, candidate_sequence)
WHERE candidate_year IS NOT NULL AND candidate_sequence IS NOT NULL;
