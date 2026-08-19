# Database Schema (SSOT) - SIMS v2.2

*Note: This matches the actual current migrations. Do not invent columns.*

## 1. `users`
`id` (PK), `username` (Unique), `password_hash`, `role`, `is_active`

## 2. `students` (Current Migration Baseline)
`id` (PK), `first_name`, `last_name`, `email`, `mobile_number` (Unique), `created_at`
*(Note: Full address/parent details will be added via schema migration in Phase 2)*

## 3. `courses`
`id` (PK), `course_name` (Unique), `base_fee`, `duration`, `is_active`

## 4. `admissions`
`id` (PK), `student_id` (FK), `course_id` (FK), `agreed_fee`, `status`, `admission_date`

## 5. `payments`
`id` (PK), `admission_id` (FK), `amount_paid`, `payment_mode`, `payment_date`

## 6. `receipts`
`id` (PK), `receipt_number` (Unique), `payment_id` (FK), `generated_at`
