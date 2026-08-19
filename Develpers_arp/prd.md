# Product Requirements Document (PRD) - SIMS v2.2

## 1. Purpose
SIMS is a desktop ERP for Sudharm Infotech (MKCL ALC). It replaces manual registers with a fast, offline-first, offline-reliant application.

## 2. Target Users (v2.2 Launch)
*   Single Administrator (Owner/Manager). Full system access.

## 3. Locked Scope (Do NOT build beyond this list)
*   **Auth:** Secure login/logout.
*   **Dashboard:** High-level metrics (Today's Collection, Pending Fees, Active Students).
*   **Admissions/Students:** CRUD operations for student profiles. No duplicate mobile numbers.
*   **Finance Engine:** Collect partial/full fees. Generate sequential, immutable receipt numbers. Calculate pending amounts automatically.
*   **Settings:** Institute profile management, manual/automatic SQLite backup triggers.

## 4. Out of Scope (Pushed to v2.3)
*   Attendance System.
*   WhatsApp / SMS Integration (Template generation is fine, API sending is out).
*   OCR / Complex Document Scanning.
*   Multiple User Roles (Faculty, Accountant).
