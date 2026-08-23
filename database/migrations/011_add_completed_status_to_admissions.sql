-- Migration: 011_add_completed_status_to_admissions
-- Description: Adds 'COMPLETED' to the admissions status CHECK constraint via SQLite table recreation.

PRAGMA foreign_keys = OFF;

CREATE TABLE admissions_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    status TEXT NOT NULL 
        CHECK (
            status IN (
                'DRAFT', 
                'REGISTERED', 
                'CONFIRMED', 
                'CANCELLED',
                'COMPLETED'
            )
        ),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    candidate_year INTEGER,
    candidate_sequence INTEGER,
    batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    agreed_fee NUMERIC NOT NULL DEFAULT 0.0,
    discount NUMERIC NOT NULL DEFAULT 0.0,
    remarks TEXT,
    updated_at DATETIME,
    institution_id INTEGER,
    institution_name TEXT,
    qualification TEXT,
    qualification_other TEXT,
    blood_group TEXT,
    village TEXT,
    address TEXT,
    aadhaar_number TEXT,
    mother_name TEXT,
    parent_guardian_name TEXT,
    dob DATE,
    gender TEXT,
    middle_name TEXT,
    photo_path TEXT,
    signature_path TEXT,

    FOREIGN KEY (student_id) 
        REFERENCES students(id) 
        ON DELETE RESTRICT
);

INSERT INTO admissions_new (
    id,
    student_id,
    status,
    created_at,
    candidate_year,
    candidate_sequence,
    batch_id,
    agreed_fee,
    discount,
    remarks,
    updated_at,
    institution_id,
    institution_name,
    qualification,
    qualification_other,
    blood_group,
    village,
    address,
    aadhaar_number,
    mother_name,
    parent_guardian_name,
    dob,
    gender,
    middle_name,
    photo_path,
    signature_path
)
SELECT 
    id,
    student_id,
    status,
    created_at,
    candidate_year,
    candidate_sequence,
    batch_id,
    agreed_fee,
    discount,
    remarks,
    updated_at,
    institution_id,
    institution_name,
    qualification,
    qualification_other,
    blood_group,
    village,
    address,
    aadhaar_number,
    mother_name,
    parent_guardian_name,
    dob,
    gender,
    middle_name,
    photo_path,
    signature_path
FROM admissions;

DROP TABLE admissions;

ALTER TABLE admissions_new RENAME TO admissions;

CREATE INDEX IF NOT EXISTS idx_admissions_student_id ON admissions(student_id);
CREATE INDEX IF NOT EXISTS idx_admissions_status ON admissions(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_admissions_yearly_candidate
ON admissions(candidate_year, candidate_sequence)
WHERE candidate_year IS NOT NULL AND candidate_sequence IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_admissions_batch_id ON admissions(batch_id);
CREATE INDEX IF NOT EXISTS idx_admissions_created_at ON admissions(created_at);
CREATE INDEX IF NOT EXISTS idx_admissions_village ON admissions(village);

PRAGMA foreign_keys = ON;
