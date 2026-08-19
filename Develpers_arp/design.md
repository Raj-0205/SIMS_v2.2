# Luxury UI/UX Design System

## 1. Core Philosophy (The Premium Feel)
*   **Fluid but Fast:** Speed > Heavy Animations. We use smooth *micro-interactions* (button hover states, subtle elevations, ripple effects) but no heavy page-load transitions that slow down office work.
*   **Information Hierarchy:** The UI must guide the user's eye. Primary actions (like "Receive Payment") should be highly visible, while secondary actions are subtle.
*   **Intelligent Empty States:** Never show a blank table. If there are no students, show a beautiful illustrative icon with text: "No students found. Add a new student to get started."

## 2. Typography & Visual Identity
*   **Headings/Major Titles:** Canela (Premium, authoritative, trustworthy).
*   **Standard UI (Forms, Tables, Buttons):** Helvetica Neue (Crisp, fast readability, modern).
*   **Spacing:** Use generous padding (`padding=30`) and spacing (`spacing=20`) to let the UI "breathe". Avoid cramped layouts.

## 3. Premium Component Behavior
*   **Sidebar:** Left-aligned, collapsible. Uses an acrylic/glassy hover effect. Contains Dark/Light theme toggle at bottom.
*   **Cards (KPIs):** Elevated `ft.Card` with subtle shadows. Hovering over a card slightly increases elevation to make it feel tactile.
*   **Data Tables:** Must support smooth scrolling. Selected rows highlight gently.
*   **Dialogs & Modals:** Centralized, with blurred or darkened background overlays. Escape key always closes them.
*   **Toast Notifications:** Top-right, floating, elegant snackbars for success/error alerts.

## 4. Color System (Semantic & Elegant)
*   **Success:** Emerald Green (Confirmed admissions, Payments done).
*   **Information/Active:** Deep Corporate Blue.
*   **Warning/Pending:** Amber/Orange (Pending installments).
*   **Critical:** Soft Crimson Red (Deletions, Overdue fees).
