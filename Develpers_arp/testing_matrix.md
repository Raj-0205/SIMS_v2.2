# AI Output Verification Rules

Before the AI claims a task is "Complete" or "PASS", it must logically verify:

1.  **Routing Checks:** Did the change introduce any asynchronous `push_route` calls? (Must be NO).
2.  **UI Checks:** Does the UI logic contain raw SQL queries? (Must be NO).
3.  **Financial Checks:** Can a payment be deleted easily? (Must be NO, requires Admin PIN/correction workflow).
4.  **Error Handling:** Are there raw Python exceptions exposed to the user? (Must be NO).

*The AI must instruct the Project Manager to run specific terminal commands to prove functionality.*
