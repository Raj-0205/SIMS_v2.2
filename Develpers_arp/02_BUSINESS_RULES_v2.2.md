# Core Business Rules - SIMS v2.2

1. **Duplicate Mobile Numbers:** A duplicate mobile number is a HARD BLOCK for creating a new student profile. No duplicates allowed.
2. **Financial Immutability:** Payments and Receipts cannot be casually deleted. Corrections require a specific adjustment/correction workflow or Admin-level intervention.
3. **Receipt Allocation:** Receipt numbers must be strictly sequential, unique, and generated only after a payment is successfully committed to the database.
4. **User Roles:** The v2.2 launch has a single `Administrator` role. Do not build UI or logic for Operators, Faculty, or Accountants yet.
5. **Transactions:** Any workflow involving money (Payments + Receipts) must be wrapped in a database transaction. If one fails, both roll back.
