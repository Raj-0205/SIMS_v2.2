-- database/migrations/019_comprehensive_performance_indexes.sql
-- Description: Comprehensive performance indexes to eliminate full table scans,
-- optimize sorting (eliminating temporary B-tree filesorts), and accelerate
-- multi-column filters across students, admissions, finance, enquiries, and peers.

-- ============================================================================
-- 1. Students Table Optimization
-- ============================================================================

-- Eliminates temporary B-tree filesort on student directory and search sorting
CREATE INDEX IF NOT EXISTS idx_students_name_sort 
ON students(first_name ASC, last_name ASC, id ASC);

-- Instant case-insensitive village lookup for peer discovery & friendship matching
CREATE INDEX IF NOT EXISTS idx_students_village_normalized 
ON students(LOWER(TRIM(village))) 
WHERE village IS NOT NULL AND village != '';

-- Chronological sorting for student enrollment timeline
CREATE INDEX IF NOT EXISTS idx_students_created_at 
ON students(created_at DESC);


-- ============================================================================
-- 2. Admissions & Bridge Tables Optimization
-- ============================================================================

-- Fast status filtering with primary key reverse ordering (avoids filesort)
CREATE INDEX IF NOT EXISTS idx_admissions_status_id 
ON admissions(status, id DESC);

-- Fast status filtering with creation date reverse ordering (avoids filesort)
CREATE INDEX IF NOT EXISTS idx_admissions_status_created 
ON admissions(status, created_at DESC);

-- Optimizes correlated subqueries fetching the student's latest admission record
CREATE INDEX IF NOT EXISTS idx_admissions_student_id_desc 
ON admissions(student_id, id DESC);

-- Fast lookup of active students assigned to a specific batch
CREATE INDEX IF NOT EXISTS idx_admissions_batch_status 
ON admissions(batch_id, status);

-- Historical village lookup on admissions
CREATE INDEX IF NOT EXISTS idx_admissions_village_normalized 
ON admissions(LOWER(TRIM(village))) 
WHERE village IS NOT NULL AND village != '';

-- Candidate sequence generation and yearly status tracking
CREATE INDEX IF NOT EXISTS idx_admissions_year_status 
ON admissions(candidate_year, status);

-- Reverse covering index for finding admissions by course
CREATE INDEX IF NOT EXISTS idx_admission_courses_course_adm 
ON admission_courses(course_id, admission_id);


-- ============================================================================
-- 3. Walk-ins & Enquiries Pipeline Optimization
-- ============================================================================

-- Status filtering with chronological ordering (replaces temp B-tree with index scan)
CREATE INDEX IF NOT EXISTS idx_enquiries_status_created 
ON enquiries(status, created_at DESC);

-- Course interest lookup
CREATE INDEX IF NOT EXISTS idx_enquiries_course_id 
ON enquiries(course_id);

-- Course interest combined with lead qualification status
CREATE INDEX IF NOT EXISTS idx_enquiries_course_status 
ON enquiries(course_id, status);

-- Reverse lookup for enquiries converted into confirmed admissions
CREATE INDEX IF NOT EXISTS idx_enquiries_converted_adm 
ON enquiries(converted_admission_id);

-- Follow-up reminder scheduler
CREATE INDEX IF NOT EXISTS idx_enquiries_followup 
ON enquiries(follow_up_date, status);

-- Normalized village index for geographical cluster analysis
CREATE INDEX IF NOT EXISTS idx_enquiries_village_normalized 
ON enquiries(LOWER(TRIM(village))) 
WHERE village IS NOT NULL AND village != '';


-- ============================================================================
-- 4. Payments & Receipts (Financial Reporting Optimization)
-- ============================================================================

-- Accelerates daily cash collection dashboards: WHERE DATE(payment_date) = ...
CREATE INDEX IF NOT EXISTS idx_payments_date_expr 
ON payments(DATE(payment_date));

-- Chronological payment reconciliation per collector
CREATE INDEX IF NOT EXISTS idx_payments_collector 
ON payments(collector_id, payment_date DESC);

-- Installment verification for admissions receipts
CREATE INDEX IF NOT EXISTS idx_receipts_adm_seq 
ON receipts(admission_id, installment_number);

-- Chronological student receipt history
CREATE INDEX IF NOT EXISTS idx_receipts_student_date 
ON receipts(student_id, receipt_date DESC);


-- ============================================================================
-- 5. Student Friendships & Peer Discovery Optimization
-- ============================================================================

-- Replaces full table scan in get_friends_for_admission() with direct index lookup
CREATE INDEX IF NOT EXISTS idx_friendships_adm_active 
ON student_friendships(admission_id, is_active);

-- Active friendship peer traversal
CREATE INDEX IF NOT EXISTS idx_friendships_student_active 
ON student_friendships(student_id, is_active);

CREATE INDEX IF NOT EXISTS idx_friendships_friend_active 
ON student_friendships(friend_student_id, is_active);


-- ============================================================================
-- 6. Academic Master Data (Courses & Batches) Optimization
-- ============================================================================

-- Replaces full table scan & filesort with ordered index scan for active course dropdowns
CREATE INDEX IF NOT EXISTS idx_courses_status_name 
ON courses(status, name ASC);

-- Academic category filtering
CREATE INDEX IF NOT EXISTS idx_courses_category_status 
ON courses(category, status);

-- High-speed active batch dropdowns filtered by course
CREATE INDEX IF NOT EXISTS idx_batches_course_status_name 
ON batches(course_id, status, batch_name ASC);


-- ============================================================================
-- 7. Security & Governance Audit Log Optimization
-- ============================================================================

-- Brute-force rate limiting and forensic login history inspection
CREATE INDEX IF NOT EXISTS idx_audit_attempts_ident_time 
ON security_audit_attempts(identifier, attempt_time DESC);

CREATE INDEX IF NOT EXISTS idx_audit_attempts_time_desc 
ON security_audit_attempts(attempt_time DESC);


-- ============================================================================
-- 8. Refresh SQLite Cost-Based Query Optimizer Statistics
-- ============================================================================
ANALYZE;
