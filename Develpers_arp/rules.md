# AI Development Constitution & Guardrails

## 1. Absolute Directives
*   **NO GUESSING:** If business logic or UI requirements are missing, ask the Project Manager.
*   **NO SCOPE CREEP:** Do not add features outside `prd.md`.
*   **NO SILENT REWRITES:** Do not refactor core architectural files (`auth.py`, `router.py`, `database.py`) without explicit permission.

## 2. Flet & Python Specifics
*   **Synchronous Routing:** Use `page.navigate(route)`. Do NOT use asynchronous `push_route` to avoid coroutine warnings.
*   **Properties:** Do not invent Flet properties (e.g., `alignment=ft.alignment.bottom_center` does not exist in Flet 0.85.3 and will crash).
*   **Errors:** Handle errors gracefully. Show a red `ft.Text` or Snackbar. Never crash the app with a raw Python traceback on the UI.

## 3. Database Rules
*   Use parameterized queries only (`?`). No string formatting for SQL.
*   Financial records (Payments, Receipts) are append-only and immutable.
*   Use `Try/Except` blocks with `TransactionManager.rollback()` for critical operations.
