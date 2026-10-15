-- Migration: 018_create_enquiries.sql
-- Description: Creates enquiries master table for prospective student walk-ins and inquiries.

CREATE TABLE IF NOT EXISTS enquiries (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name            TEXT NOT NULL,
    mobile_number           TEXT NOT NULL,
    alternate_mobile        TEXT,
    email                   TEXT,
    village                 TEXT,
    address                 TEXT,
    course_id               INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    interested_course       TEXT,
    qualification           TEXT,
    gender                  TEXT DEFAULT 'MALE',
    status                  TEXT NOT NULL DEFAULT 'NEW',  -- NEW, CONTACTED, VISITED, CONVERTED, CLOSED
    source                  TEXT DEFAULT 'WALK_IN',        -- WALK_IN, PHONE, SOCIAL_MEDIA, REFERENCE, BANNER, OTHER
    follow_up_date          DATE,
    notes                   TEXT,
    counselor_name          TEXT,
    converted_admission_id  INTEGER REFERENCES admissions(id) ON DELETE SET NULL,
    created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_enquiries_mobile ON enquiries(mobile_number);
CREATE INDEX IF NOT EXISTS idx_enquiries_village ON enquiries(village);
CREATE INDEX IF NOT EXISTS idx_enquiries_status ON enquiries(status);
CREATE INDEX IF NOT EXISTS idx_enquiries_created_at ON enquiries(created_at);
