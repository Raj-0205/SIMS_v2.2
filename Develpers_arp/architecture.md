# Architecture & Tech Stack

## 1. Tech Stack
*   **Language:** Python 3.14
*   **UI Framework:** Flet 0.85.3 (Strictly this version)
*   **Database:** SQLite3
*   **Security:** Argon2id (Password Hashing)

## 2. 5-Layer Strict Architecture
1.  **UI (`/ui`):** Only visual components. NEVER executes SQL.
2.  **Controllers (`/controllers`):** Validates UI input, calls Services.
3.  **Services (`/services`):** The Brain. Holds all business rules and calculations.
4.  **Repositories (`/database/repositories`):** The ONLY layer that touches SQLite.
5.  **Database (`/database`):** SQLite engine and schema.

## 3. Navigation Architecture
*   **Router:** Enforces fail-closed authentication.
*   **Dashboard Shell:** Uses a persistent root view `ft.View(route="/")` to prevent Flet's full-page transition animation during internal sidebar clicks.
*   **Content Host:** Dynamic modules mount into `ContentHost.mount(view)` rather than rebuilding the entire page.
