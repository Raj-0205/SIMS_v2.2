# Software Architecture - SIMS v2.2

## 1. Tech Stack
- Python 3.14
- Flet 0.85.3 (Strictly this version)
- SQLite3
- Argon2id (Hashing)

## 2. Actual Folder Structure
- `core/`: Config, database engine, security/auth, routing logic.
- `modules/`: Feature-specific logic (e.g., student, admission, course). Contains controllers, services, and repositories.
- `ui/`: Visuals only. Contains `screens/`, `layout/`, and `widgets/`.

## 3. Strict 5-Layer Pattern
`UI` -> `Controller` -> `Service` -> `Repository` -> `Database`
*Rule: UI files must NEVER execute raw SQL or contain direct business logic.*

## 4. Flet Constraints
- Do NOT use asynchronous `push_route`. Use synchronous `page.navigate()`.
- Top-level routing uses a persistent `ft.View(route="/")` to prevent full-page transition animations during internal sidebar clicks.
