# Testing & Acceptance Matrix

Before claiming a task is "PASS", verify the following logically:
1. **Routing:** Are there any `coroutine never awaited` warnings? (Must be NO).
2. **Layer Bleed:** Does a UI file import `sqlite3` or `database.py`? (Must be NO).
3. **Validation:** Does entering a duplicate mobile number trigger a hard stop? (Must be YES).
4. **Immutability:** Can a payment record be easily deleted from the UI without an Admin override? (Must be NO).

*AI must provide the exact terminal commands required for the Project Manager to verify these conditions locally.*
