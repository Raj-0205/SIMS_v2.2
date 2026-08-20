-- Migration: 009_admission_metadata_and_batch
-- Description: Expands admissions table with batch linkage, agreed fee, discount, remarks, and updated_at timestamp.

ALTER TABLE admissions ADD COLUMN batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL;
ALTER TABLE admissions ADD COLUMN agreed_fee NUMERIC NOT NULL DEFAULT 0.0;
ALTER TABLE admissions ADD COLUMN discount NUMERIC NOT NULL DEFAULT 0.0;
ALTER TABLE admissions ADD COLUMN remarks TEXT;
ALTER TABLE admissions ADD COLUMN updated_at DATETIME;

CREATE INDEX IF NOT EXISTS idx_admissions_batch_id ON admissions(batch_id);
CREATE INDEX IF NOT EXISTS idx_admissions_created_at ON admissions(created_at);
