# scripts/seed_admin.py

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

# Ensure project root is importable when this script is executed directly.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.configuration.service import ConfigService
from core.database.engine import DatabaseEngine
from core.database.migration import MigrationEngine
from core.database.transaction import TransactionManager
from core.security.auth import AuthService
from modules.users.repository import UserRepository


def _read_password(username: str) -> str:
    """Read a non-empty password securely from environment or terminal."""
    password = os.getenv("SIMS_ADMIN_PASS")

    if password is None:
        password = getpass.getpass(
            f"Enter new password for '{username}': "
        )

    if not password or not password.strip():
        raise ValueError("Password cannot be empty.")

    if os.getenv("SIMS_ADMIN_PASS") is None:
        confirmation = getpass.getpass("Confirm password: ")

        if password != confirmation:
            raise ValueError("Passwords do not match.")

    return password


def seed_admin() -> int:
    """Create the initial administrative user when it does not exist."""
    print("Initializing authentication database...")

    ConfigService.initialize()
    DatabaseEngine.initialize()
    MigrationEngine.initialize()
    MigrationEngine.upgrade()

    username = os.getenv("SIMS_ADMIN_USER", "admin").strip()

    if not username:
        print("[X] SIMS_ADMIN_USER cannot be empty.")
        return 1

    repository = UserRepository()

    TransactionManager.begin()

    try:
        existing = repository.get_by_username(username)

        if existing:
            TransactionManager.commit()
            print(f"[!] User '{username}' already exists. No changes made.")
            return 0

        TransactionManager.commit()
    except Exception as exc:
        if TransactionManager.in_transaction():
            TransactionManager.rollback()

        print(f"[X] Failed to inspect existing users: {exc}")
        return 1

    try:
        password = _read_password(username)
        password_hash = AuthService.hash_password(password)
    except ValueError as exc:
        print(f"[X] {exc}")
        return 1

    TransactionManager.begin()

    try:
        user_id = repository.create_user(
            username=username,
            password_hash=password_hash,
            role="ADMIN",
        )

        TransactionManager.commit()

        print(
            f"[✓] Admin user '{username}' seeded successfully "
            f"with id={user_id}."
        )
        return 0

    except Exception as exc:
        if TransactionManager.in_transaction():
            TransactionManager.rollback()

        print(f"[X] Failed to create admin user: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(seed_admin())
