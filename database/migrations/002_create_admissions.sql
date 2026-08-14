-- Migration: 002_create_admissions
-- Description: Core admission entity foundation. No cross-domain data (Course/Batch/Fees).

CREATE TABLE IF NOT EXISTS admissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    student_id INTEGER NOT NULL,
    
    status TEXT NOT NULL 
        CHECK (
            status IN (
                'DRAFT', 
                'REGISTERED', 
                'CONFIRMED', 
                'CANCELLED'
            )
        ),
        
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- ERP Rule: Never delete history. Restrict student deletion if an admission exists.
    FOREIGN KEY (student_id) 
        REFERENCES students(id) 
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_admissions_student_id ON admissions(student_id);
CREATE INDEX IF NOT EXISTS idx_admissions_status ON admissions(status);

-- TODO (Production Hardening): Add updated_at column + SQLite UPDATE trigger.
-- TODO (Production Hardening): Evaluate composite index (student_id, status).
