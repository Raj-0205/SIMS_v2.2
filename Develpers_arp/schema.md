# Enterprise Database Schema (SSOT)

## 1. Database Philosophy (Enterprise-Grade)
*   **ACID Compliant:** All critical workflows (like Admissions + Payments) must use Transactions (`TransactionManager.begin()`, `.commit()`, `.rollback()`).
*   **Audit-Ready:** Every table uses standard audit columns: `created_at`, `updated_at`, `created_by`.
*   **Soft Deletes:** We DO NOT use `DELETE FROM`. We use `is_active=0` or `deleted_at` to move items to Trash, preserving financial and historical integrity.
*   **Foreign Key Constraints:** Strict relationships. You cannot delete a Course if Students are enrolled in it.

## 2. Table Structures

### A. `users` (System Operators)
*   `id` (PK, AutoIncrement)
*   `username` (Text, Unique, Indexed)
*   `password_hash` (Text, Argon2id)
*   `role` (Text - Admin/Operator)
*   `is_active` (Integer, Default 1)
*   `last_login` (DateTime)

### B. `students` (Master Profile)
*   `id` (PK)
*   `full_name` (Text), `mobile_number` (Text, Unique, Indexed)
*   `gender`, `dob`, `address`
*   `created_at`, `updated_at`, `is_deleted`

### C. `courses` & `batches` (Master Data)
*   **courses:** `id`, `course_name` (Unique), `base_fee` (Real), `duration`, `is_active`
*   **batches:** `id`, `course_id` (FK), `batch_name`, `max_capacity`, `start_time`, `end_time`, `is_active`

### D. `admissions` (The Link Entity)
*   `id` (PK)
*   `student_id` (FK), `course_id` (FK), `batch_id` (FK)
*   `agreed_fee` (Real - locked fee for this student)
*   `status` (Text - Draft, Active, Completed, Cancelled)
*   `admission_date` (DateTime)

### E. `payments` & `receipts` (Financial Engine - IMMUTABLE)
*   **payments:** `id` (PK), `admission_id` (FK), `amount_paid` (Real), `payment_mode` (Text: Cash/UPI), `payment_date`
*   **receipts:** `id` (PK), `receipt_number` (Text, Unique, Sequential), `payment_id` (FK), `generated_at`, `generated_by` (FK)
