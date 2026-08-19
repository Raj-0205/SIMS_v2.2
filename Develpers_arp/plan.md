# SIMS Project Plan & The Flagship Vision

## 1. The Flagship DNA (What makes SIMS Premium)
SIMS is NOT a standard, basic desktop app. It is a **Premium Offline-First Enterprise Resource Planning (ERP)** system. 
*   **Zero-Latency Feel:** Database operations and UI rendering must feel instant. No freezing, no hanging.
*   **Enterprise Reliability:** Data is never lost. The system handles errors gracefully without exposing raw Python tracebacks to the user.
*   **Luxury UX:** The interface uses micro-interactions, glassy sidebar effects, intelligent empty states, and skeleton loading screens instead of blank white pages.

## 2. Original Handwritten Concept (The Foundation)
*   **Application Shell:** Sudharm Infotech Management System (Powered by ARP Group).
*   **Dashboard Widgets:** Registration overview, Financial Collection Efficiency (Progress bars), Latest Confirmed, Pending Installments, Today's Work.
*   **Student Workflow:** Double-click to open workspace. Right-click context menu (Open, Payment, Receipt, Edit, PDF, History).
*   **Inquiry CRM:** Categorized by Hot, Warm, Cold with seamless conversion to Admission.

## 3. Current Execution Phase (SIMS v2.2)
*   **Code Freeze:** August 28.
*   **Launch Date:** September 3.
*   **Current State:** Core framework, SQLite database, Argon2id Auth, and fail-closed Router are heavily tested and functional.
*   **Immediate Goal:** Build the critical Day-1 modules strictly mapping to the premium vision.

## 4. Strict Launch Scope (Day-1 Must-Haves)
1.  **Core:** Secure login, fail-closed router, persistent dashboard shell (preventing full-page route animations).
2.  **Students:** Add new student, view/edit profile with high-end workspace UI.
3.  **Courses/Batches:** Create/edit courses, manage batches with capacity warnings.
4.  **Finance Engine:** Robust payment collection, sequential & immutable receipt numbers, automatic pending fee calculation.
5.  **Reports:** Daily/monthly collection, active students list with data tables supporting search/sort.
