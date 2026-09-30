-- database/migrations/016_performance_indexes.sql
-- Optimizes high-volume reporting queries across payments and admissions

-- Covering index on payments for installment breakdown and total paid calculation
CREATE INDEX IF NOT EXISTS idx_payments_adm_inst_amt 
ON payments(admission_id, installment_number, amount);

-- Composite index on admissions for student identity and lifecycle status lookups
CREATE INDEX IF NOT EXISTS idx_admissions_student_status 
ON admissions(student_id, status);
