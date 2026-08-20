-- Migration: 010_admission_finance_and_support_masters
-- Description: Adds personal/location fields to students & admissions, payments, receipts, institutions, collectors, friendships, settings, activity logs, and seed data.

-- 1. Expand students table with personal and location fields
ALTER TABLE students ADD COLUMN middle_name TEXT;
ALTER TABLE students ADD COLUMN mother_name TEXT;
ALTER TABLE students ADD COLUMN dob DATE;
ALTER TABLE students ADD COLUMN gender TEXT;
ALTER TABLE students ADD COLUMN aadhaar_number TEXT;
ALTER TABLE students ADD COLUMN parent_guardian_name TEXT;
ALTER TABLE students ADD COLUMN village TEXT;
ALTER TABLE students ADD COLUMN address TEXT;
ALTER TABLE students ADD COLUMN qualification TEXT;
ALTER TABLE students ADD COLUMN blood_group TEXT;
ALTER TABLE students ADD COLUMN photo_path TEXT;
ALTER TABLE students ADD COLUMN signature_path TEXT;
ALTER TABLE students ADD COLUMN updated_at DATETIME;

CREATE INDEX IF NOT EXISTS idx_students_village ON students(village);
CREATE INDEX IF NOT EXISTS idx_students_aadhaar ON students(aadhaar_number);

-- 2. Expand admissions table with candidate profile and academic details
ALTER TABLE admissions ADD COLUMN institution_id INTEGER;
ALTER TABLE admissions ADD COLUMN institution_name TEXT;
ALTER TABLE admissions ADD COLUMN qualification TEXT;
ALTER TABLE admissions ADD COLUMN qualification_other TEXT;
ALTER TABLE admissions ADD COLUMN blood_group TEXT;
ALTER TABLE admissions ADD COLUMN village TEXT;
ALTER TABLE admissions ADD COLUMN address TEXT;
ALTER TABLE admissions ADD COLUMN aadhaar_number TEXT;
ALTER TABLE admissions ADD COLUMN mother_name TEXT;
ALTER TABLE admissions ADD COLUMN parent_guardian_name TEXT;
ALTER TABLE admissions ADD COLUMN dob DATE;
ALTER TABLE admissions ADD COLUMN gender TEXT;
ALTER TABLE admissions ADD COLUMN middle_name TEXT;
ALTER TABLE admissions ADD COLUMN photo_path TEXT;
ALTER TABLE admissions ADD COLUMN signature_path TEXT;

CREATE INDEX IF NOT EXISTS idx_admissions_village ON admissions(village);

-- 3. Educational Institutions Master (School / College)
CREATE TABLE IF NOT EXISTS educational_institutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    institution_type TEXT DEFAULT 'COLLEGE',
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_educational_institutions_name ON educational_institutions(name);
CREATE INDEX IF NOT EXISTS idx_educational_institutions_active ON educational_institutions(is_active);

-- 4. Payment Collectors Master
CREATE TABLE IF NOT EXISTS payment_collectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    role_title TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_payment_collectors_name ON payment_collectors(name);
CREATE INDEX IF NOT EXISTS idx_payment_collectors_active ON payment_collectors(is_active);

-- 5. Student Friendships (Explicit Relational Pairs)
CREATE TABLE IF NOT EXISTS student_friendships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    friend_student_id INTEGER NOT NULL,
    admission_id INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (friend_student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (admission_id) REFERENCES admissions(id) ON DELETE SET NULL,
    
    CHECK (student_id <> friend_student_id)
);
CREATE INDEX IF NOT EXISTS idx_student_friendships_student ON student_friendships(student_id);
CREATE INDEX IF NOT EXISTS idx_student_friendships_friend ON student_friendships(friend_student_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_student_friendships_unique_pair 
ON student_friendships(
    CASE WHEN student_id < friend_student_id THEN student_id ELSE friend_student_id END,
    CASE WHEN student_id < friend_student_id THEN friend_student_id ELSE student_id END
);

-- 6. Payments (Financial Transactions & Installments)
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admission_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    installment_number INTEGER NOT NULL,
    amount NUMERIC NOT NULL CHECK (amount > 0),
    payment_mode TEXT NOT NULL CHECK (payment_mode IN ('CASH', 'UPI', 'CARD', 'NET_BANKING', 'CHEQUE')),
    payment_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    collector_id INTEGER REFERENCES payment_collectors(id) ON DELETE RESTRICT,
    collector_name TEXT NOT NULL,
    transaction_ref TEXT,
    remarks TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (admission_id) REFERENCES admissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_payments_admission_id ON payments(admission_id);
CREATE INDEX IF NOT EXISTS idx_payments_student_id ON payments(student_id);
CREATE INDEX IF NOT EXISTS idx_payments_payment_date ON payments(payment_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_admission_installment ON payments(admission_id, installment_number);

-- 7. Receipts (Official Sequential Billing Slips)
CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL UNIQUE,
    admission_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    receipt_number TEXT NOT NULL UNIQUE,
    receipt_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_course_fee NUMERIC NOT NULL,
    amount_paid NUMERIC NOT NULL,
    total_paid_till_now NUMERIC NOT NULL,
    pending_amount NUMERIC NOT NULL,
    installment_number INTEGER NOT NULL,
    payment_mode TEXT NOT NULL,
    collector_name TEXT NOT NULL,
    pdf_path TEXT,
    generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    generated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    
    FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE RESTRICT,
    FOREIGN KEY (admission_id) REFERENCES admissions(id) ON DELETE RESTRICT,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_receipts_receipt_number ON receipts(receipt_number);
CREATE INDEX IF NOT EXISTS idx_receipts_admission_id ON receipts(admission_id);
CREATE INDEX IF NOT EXISTS idx_receipts_student_id ON receipts(student_id);
CREATE INDEX IF NOT EXISTS idx_receipts_receipt_date ON receipts(receipt_date);

-- 8. Institute Settings (Global Configuration & Branding)
CREATE TABLE IF NOT EXISTS institute_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT DEFAULT 'GENERAL',
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 9. Activity Logs (Audit Trail)
CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor_name TEXT NOT NULL DEFAULT 'SYSTEM',
    actor_id INTEGER,
    details TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_activity_logs_entity ON activity_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at ON activity_logs(created_at);

-- 10. Seed Data
-- 10a. Educational Institutions
INSERT OR IGNORE INTO educational_institutions (name, institution_type) VALUES 
('Karmaveer Bhausaheb Hiray Arts, Science and Commerce College, Chandwad', 'COLLEGE'),
('SNJB''s Late Sau Kantabai Bhavarlalji Jain College of Engineering, Chandwad', 'COLLEGE'),
('R. N. Chandak High School, Chandwad', 'SCHOOL'),
('Abhinav Secondary School, Chandwad', 'SCHOOL'),
('Other / External Institution', 'OTHER');

-- 10b. Payment Collectors
INSERT OR IGNORE INTO payment_collectors (name, role_title) VALUES 
('Hemant Mahale (Sir)', 'Center Director'),
('Training & Support Operator', 'Administration');

-- 10c. Institute Settings
INSERT OR IGNORE INTO institute_settings (key, value, category, description) VALUES
('institute_name', 'Sudharm Infotech', 'BRANDING', 'Institute legal business name'),
('contact_person', 'Hemant Mahale', 'BRANDING', 'Director/Contact person'),
('contact_mobile', '9271226772', 'BRANDING', 'Official contact phone'),
('alc_code', '57210242', 'BRANDING', 'Authorized Learning Center code'),
('address_line1', 'Renuka Complex, 3rd Floor,', 'BRANDING', 'Primary premise location'),
('address_line2', 'Opp. Market Yard, Chandwad - 423101', 'BRANDING', 'City/Postal address'),
('admin_pin_hash', '$argon2id$v=19$m=65536,t=3,p=4$LMBDwbcXZCRwJlJcvk5TVQ$7fGh7akuhlrdx7DaIX5StIh7LA3bfdOOKYNifj4RZ2E', 'SECURITY', 'Argon2id hash of 4-digit Admin authorization PIN'),
('require_photo', 'true', 'ADMISSION', 'Whether student photo is mandatory'),
('require_signature', 'false', 'ADMISSION', 'Whether student signature is mandatory'),
('min_confirmation_amount', '500.0', 'FINANCE', 'Minimum initial payment to confirm admission');

-- 10d. Seed Courses (MS-CIT and KLiC Courses)
INSERT OR IGNORE INTO courses (code, name, base_fee, duration, category, description, status) VALUES
('MSCIT', 'MS-CIT (Mastering IT)', 4500.0, '2 Months', 'IT Literacy', 'Maharashtra State Certificate in Information Technology', 'ACTIVE'),
('KLIC-PYTHON', 'KLiC Python Programming', 5000.0, '2 Months', 'Programming', 'Python fundamentals, data structures, and automation', 'ACTIVE'),
('KLIC-JAVA', 'KLiC Java Programming', 5000.0, '2 Months', 'Programming', 'Core Java, OOPs, Collections, and Applications', 'ACTIVE'),
('KLIC-CPP', 'KLiC C / C++ / C#', 4500.0, '2 Months', 'Programming', 'C, C++, C# Object Oriented System Programming', 'ACTIVE'),
('KLIC-TALLY', 'KLiC Tally Prime GST', 5000.0, '2 Months', 'Accounting', 'Computerized Financial Accounting with GST in Tally Prime', 'ACTIVE'),
('KLIC-EXCEL', 'KLiC Advanced Excel', 4000.0, '1 Month', 'Office', 'Advanced formulas, Pivot Tables, Dashboards, and Analytics', 'ACTIVE'),
('KLIC-WEB', 'KLiC Web Designing', 5000.0, '2 Months', 'Development', 'HTML5, CSS3, JavaScript, Bootstrap, Responsive UI', 'ACTIVE'),
('KLIC-PHOTO', 'KLiC Photo Editing', 4000.0, '1 Month', 'Design', 'Adobe Photoshop, image retouching, color grading', 'ACTIVE'),
('KLIC-MOBILE', 'KLiC Mobile App Development', 6000.0, '2 Months', 'Development', 'Android and Cross-platform Mobile App Development', 'ACTIVE'),
('KLIC-ADVJAVA', 'KLiC Advanced Java', 6000.0, '2 Months', 'Programming', 'J2EE, Servlets, JSP, Spring Boot, Hibernate', 'ACTIVE'),
('KLIC-DTP', 'KLiC Desktop Publishing / Adobe', 4500.0, '2 Months', 'Design', 'InDesign, PageMaker, CorelDRAW, print layouts', 'ACTIVE'),
('KLIC-ILLUST', 'KLiC Content Illustration', 4500.0, '2 Months', 'Design', 'Adobe Illustrator, vector graphic design, branding', 'ACTIVE');
