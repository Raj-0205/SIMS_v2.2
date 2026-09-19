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


import argparse
from core.security.recovery import RecoveryKeyService


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


def seed_admin(
    is_administrator: bool = False,
    custom_username: str | None = None,
    custom_email: str | None = None,
) -> int:
    """Create an administrative user (Admin or Administrator) when it does not exist."""
    print("Initializing authentication database...")

    ConfigService.initialize()
    DatabaseEngine.initialize()
    MigrationEngine.initialize()
    MigrationEngine.upgrade()

    target_role = "ADMINISTRATOR" if is_administrator else "ADMIN"
    default_name = "administrator" if is_administrator else "admin"
    username = (custom_username or os.getenv("SIMS_ADMIN_USER", default_name)).strip()
    email = (custom_email or os.getenv("SIMS_ADMIN_EMAIL", "")).strip() or None

    if not username:
        print("[X] Username cannot be empty.")
        return 1

    if is_administrator and not email:
        print("[X] Administrator account requires an email address (--email or SIMS_ADMIN_EMAIL).")
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
            role=target_role,
            email=email,
        )

        TransactionManager.commit()

        print(
            f"[✓] {target_role} user '{username}' seeded successfully "
            f"with id={user_id}."
        )

        # Provision recovery key for Administrator
        if is_administrator:
            TransactionManager.begin()
            try:
                formatted_key, key_id, deliv = RecoveryKeyService.issue_recovery_key(
                    user_id=user_id,
                    user_repo=repository,
                    send_email=True,
                )
                TransactionManager.commit()
                print("=" * 65)
                print("CRITICAL: BREAK-GLASS EMERGENCY RECOVERY KEY GENERATED")
                print("=" * 65)
                print(f"Key Identifier: {key_id}")
                print(f"Recovery Key:   {formatted_key}")
                print(f"Email Delivery: {deliv}")
                print("=" * 65)
                print("Store this key securely in an encrypted vault or password manager.")
                print("=" * 65)
            except Exception as k_exc:
                if TransactionManager.in_transaction():
                    TransactionManager.rollback()
                print(f"[!] Warning: Failed to generate recovery key: {k_exc}")

        return 0

    except Exception as exc:
        if TransactionManager.in_transaction():
            TransactionManager.rollback()

        print(f"[X] Failed to create user: {exc}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed initial SIMS administrative users.")
    parser.add_argument(
        "--administrator",
        action="store_true",
        help="Seed elevated Administrator account (requires email)",
    )
    parser.add_argument("--username", help="Account username (defaults to 'admin' or 'administrator')")
    parser.add_argument("--email", help="Account email address (mandatory for Administrator)")
    args = parser.parse_args()

    raise SystemExit(
        seed_admin(
            is_administrator=args.administrator,
            custom_username=args.username,
            custom_email=args.email,
        )
    )
