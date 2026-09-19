# modules/users/repository.py

from __future__ import annotations
from typing import Any, Optional
import secrets
from datetime import datetime, timezone, timedelta

from core.database.repository import BaseRepository

__all__ = ["UserRepository"]


class UserRepository(BaseRepository):
    """Data access layer for user and authentication entities."""

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        """Fetch a user by exact username."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                email,
                is_active,
                failed_login_attempts,
                locked_until,
                security_version,
                security_stamp,
                password_changed_at,
                failed_break_glass_attempts,
                break_glass_locked_until,
                created_at,
                updated_at
            FROM users
            WHERE username = ?;
            """,
            (username,),
        )

    def get_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Fetch a user by primary key."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                email,
                is_active,
                failed_login_attempts,
                locked_until,
                security_version,
                security_stamp,
                password_changed_at,
                failed_break_glass_attempts,
                break_glass_locked_until,
                created_at,
                updated_at
            FROM users
            WHERE id = ?;
            """,
            (user_id,),
        )

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch a user by case-insensitive normalized email."""
        if not email or not email.strip():
            return None
        return self.execute_fetchone(
            """
            SELECT
                id,
                username,
                password_hash,
                role,
                email,
                is_active,
                failed_login_attempts,
                locked_until,
                security_version,
                security_stamp,
                password_changed_at,
                failed_break_glass_attempts,
                break_glass_locked_until,
                created_at,
                updated_at
            FROM users
            WHERE lower(trim(email)) = lower(trim(?));
            """,
            (email.strip(),),
        )

    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "ADMIN",
        email: str | None = None,
        security_stamp: str | None = None,
    ) -> int:
        """Create a user and return its generated primary key."""
        stamp = security_stamp or secrets.token_hex(16)
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return self.execute_insert(
            """
            INSERT INTO users (
                username,
                password_hash,
                role,
                email,
                security_version,
                security_stamp,
                password_changed_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?);
            """,
            (
                username.strip(),
                password_hash,
                role,
                email.strip() if email else None,
                stamp,
                now_utc,
                now_utc,
                now_utc,
            ),
        )

    def record_failed_login(
        self,
        user_id: int,
        max_attempts: int = 5,
        lockout_minutes: int = 15,
    ) -> int:
        """
        Increments failed_login_attempts. If threshold is reached, locks the account.
        Returns the new failed attempt count.
        """
        user = self.get_by_id(user_id)
        if not user:
            return 0
        new_attempts = int(user.get("failed_login_attempts") or 0) + 1
        now_utc = datetime.now(timezone.utc)
        locked_until_str = None
        if new_attempts >= max_attempts:
            locked_until_dt = now_utc + timedelta(minutes=lockout_minutes)
            locked_until_str = locked_until_dt.strftime("%Y-%m-%d %H:%M:%S")

        self.execute(
            """
            UPDATE users
            SET failed_login_attempts = ?,
                locked_until = COALESCE(?, locked_until),
                updated_at = ?
            WHERE id = ?;
            """,
            (new_attempts, locked_until_str, now_utc.strftime("%Y-%m-%d %H:%M:%S"), user_id),
        )
        return new_attempts

    def reset_failed_logins(self, user_id: int) -> None:
        """Clears failed login attempts and unlocks the account."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE users
            SET failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = ?
            WHERE id = ?;
            """,
            (now_utc, user_id),
        )

    def update_email(self, user_id: int, email: str | None) -> None:
        """Update a user's email address."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE users
            SET email = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (email.strip() if email else None, now_utc, user_id),
        )

    def update_role(self, user_id: int, role: str) -> None:
        """Update a user's role."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE users
            SET role = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (role, now_utc, user_id),
        )

    def update_password(self, user_id: int, password_hash: str) -> tuple[int, str]:
        """
        Update a user's password hash, bumps monotonic security_version and rotates security_stamp.
        Returns: (new_security_version, new_security_stamp)
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        new_stamp = secrets.token_hex(16)
        self.execute(
            """
            UPDATE users
            SET password_hash = ?,
                password_changed_at = ?,
                security_version = security_version + 1,
                security_stamp = ?,
                failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = ?
            WHERE id = ?;
            """,
            (password_hash, now_utc, new_stamp, now_utc, user_id),
        )
        user = self.get_by_id(user_id)
        if user:
            return int(user["security_version"]), str(user["security_stamp"])
        return 1, new_stamp

    def rotate_security_credentials(self, user_id: int) -> tuple[int, str]:
        """
        Rotates the security stamp and increments security_version without altering password.
        Terminates all active sessions immediately.
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        new_stamp = secrets.token_hex(16)
        self.execute(
            """
            UPDATE users
            SET security_version = security_version + 1,
                security_stamp = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (new_stamp, now_utc, user_id),
        )
        user = self.get_by_id(user_id)
        if user:
            return int(user["security_version"]), str(user["security_stamp"])
        return 1, new_stamp

    def record_failed_break_glass(
        self,
        user_id: int,
        max_attempts: int = 3,
        lockout_minutes: int = 30,
    ) -> int:
        """
        Increments failed_break_glass_attempts. If threshold is reached, locks break-glass access.
        """
        user = self.get_by_id(user_id)
        if not user:
            return 0
        new_attempts = int(user.get("failed_break_glass_attempts") or 0) + 1
        now_utc = datetime.now(timezone.utc)
        locked_until_str = None
        if new_attempts >= max_attempts:
            locked_until_dt = now_utc + timedelta(minutes=lockout_minutes)
            locked_until_str = locked_until_dt.strftime("%Y-%m-%d %H:%M:%S")

        self.execute(
            """
            UPDATE users
            SET failed_break_glass_attempts = ?,
                break_glass_locked_until = COALESCE(?, break_glass_locked_until),
                updated_at = ?
            WHERE id = ?;
            """,
            (new_attempts, locked_until_str, now_utc.strftime("%Y-%m-%d %H:%M:%S"), user_id),
        )
        return new_attempts

    def reset_failed_break_glass(self, user_id: int) -> None:
        """Clears failed break glass attempts and unlocks break-glass recovery."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE users
            SET failed_break_glass_attempts = 0,
                break_glass_locked_until = NULL,
                updated_at = ?
            WHERE id = ?;
            """,
            (now_utc, user_id),
        )

    # --- OTP Challenge Operations ---

    def create_otp_challenge(
        self,
        challenge_token: str,
        user_id: int,
        otp_hash: str,
        expires_at: str,
        max_attempts: int = 3,
        purpose: str = "LOGIN",
    ) -> int:
        """Persist a new OTP challenge token with specified purpose."""
        return self.execute_insert(
            """
            INSERT INTO auth_otp_challenges (
                challenge_token,
                user_id,
                otp_hash,
                attempts_left,
                max_attempts,
                expires_at,
                purpose,
                is_consumed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0);
            """,
            (challenge_token, user_id, otp_hash, max_attempts, max_attempts, expires_at, purpose),
        )

    def get_otp_challenge(self, challenge_token: str) -> dict[str, Any] | None:
        """Retrieve an OTP challenge by token."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                challenge_token,
                user_id,
                otp_hash,
                attempts_left,
                max_attempts,
                expires_at,
                purpose,
                is_consumed,
                consumed_at,
                created_at
            FROM auth_otp_challenges
            WHERE challenge_token = ?;
            """,
            (challenge_token,),
        )

    def decrement_otp_attempts(self, challenge_id: int) -> int:
        """Decrement attempts_left by 1. Returns remaining attempts."""
        self.execute(
            """
            UPDATE auth_otp_challenges
            SET attempts_left = MAX(0, attempts_left - 1)
            WHERE id = ?;
            """,
            (challenge_id,),
        )
        row = self.execute_fetchone(
            "SELECT attempts_left FROM auth_otp_challenges WHERE id = ?;",
            (challenge_id,),
        )
        return int(row["attempts_left"]) if row else 0

    def mark_otp_consumed(self, challenge_id: int) -> None:
        """Mark an OTP challenge as consumed."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE auth_otp_challenges
            SET is_consumed = 1,
                consumed_at = ?
            WHERE id = ?;
            """,
            (now_utc, challenge_id),
        )

    def invalidate_pending_challenges_for_user(self, user_id: int, purpose: str | None = None) -> None:
        """Invalidate unconsumed OTP challenges for a user (optionally filtered by purpose)."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if purpose:
            self.execute(
                """
                UPDATE auth_otp_challenges
                SET is_consumed = 1,
                    consumed_at = ?
                WHERE user_id = ? AND purpose = ? AND is_consumed = 0;
                """,
                (now_utc, user_id, purpose),
            )
        else:
            self.execute(
                """
                UPDATE auth_otp_challenges
                SET is_consumed = 1,
                    consumed_at = ?
                WHERE user_id = ? AND is_consumed = 0;
                """,
                (now_utc, user_id),
            )

    # --- Break-Glass Recovery Keys Operations ---

    def create_recovery_key(
        self,
        user_id: int,
        key_hash: str,
        key_identifier: str,
        delivery_email_status: str = "PENDING",
        delivery_email_error: str | None = None,
    ) -> int:
        """
        Creates a new ACTIVE recovery key. Revokes any existing ACTIVE keys for this user.
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        # Revoke existing active keys
        self.execute(
            """
            UPDATE auth_recovery_keys
            SET status = 'REVOKED',
                is_active = 0,
                revoked_at = ?
            WHERE user_id = ? AND status = 'ACTIVE' AND is_active = 1;
            """,
            (now_utc, user_id),
        )
        return self.execute_insert(
            """
            INSERT INTO auth_recovery_keys (
                user_id,
                key_hash,
                key_identifier,
                status,
                delivery_email_status,
                delivery_email_attempted_at,
                delivery_email_error,
                is_active,
                created_at
            )
            VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, 1, ?);
            """,
            (
                user_id,
                key_hash,
                key_identifier,
                delivery_email_status,
                now_utc,
                delivery_email_error,
                now_utc,
            ),
        )

    def update_recovery_key_delivery_status(
        self,
        key_id: int,
        status: str,
        error: str | None = None,
    ) -> None:
        """Updates delivery telemetry for a recovery key."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.execute(
            """
            UPDATE auth_recovery_keys
            SET delivery_status = ?,
                delivered_at = ?,
                delivery_email_status = ?,
                delivery_email_attempted_at = ?,
                delivery_email_error = ?
            WHERE id = ?;
            """,
            (status, now_utc, status, now_utc, error, key_id),
        )

    # Alias for compatibility
    update_recovery_key_delivery_telemetry = update_recovery_key_delivery_status

    def get_active_recovery_key(self, user_id: int) -> dict[str, Any] | None:
        """Fetch the single ACTIVE or PENDING_REMEDIATION recovery key for the given user."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                user_id,
                key_hash,
                key_identifier,
                status,
                session_nonce,
                pending_session_id,
                pending_started_at,
                pending_expires_at,
                delivery_status,
                delivered_at,
                delivery_email_status,
                delivery_email_attempted_at,
                delivery_email_error,
                is_active,
                created_at,
                locked_at,
                used_at,
                consumed_at,
                revoked_at
            FROM auth_recovery_keys
            WHERE user_id = ? AND status IN ('ACTIVE', 'PENDING_REMEDIATION') AND is_active = 1
            ORDER BY id DESC LIMIT 1;
            """,
            (user_id,),
        )

    def get_recovery_key_by_id(self, key_id: int) -> dict[str, Any] | None:
        """Fetch recovery key row by ID."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                user_id,
                key_hash,
                key_identifier,
                status,
                session_nonce,
                pending_session_id,
                pending_started_at,
                pending_expires_at,
                delivery_status,
                delivered_at,
                delivery_email_status,
                delivery_email_attempted_at,
                delivery_email_error,
                is_active,
                created_at,
                locked_at,
                used_at,
                consumed_at,
                revoked_at
            FROM auth_recovery_keys
            WHERE id = ?;
            """,
            (key_id,),
        )

    def claim_break_glass_lease(
        self,
        key_id: int,
        session_id: str,
        session_nonce: str,
        lease_seconds: int = 600,
    ) -> bool:
        """
        Atomically claims a Break-Glass recovery lease.
        Succeeds if key is ACTIVE, or if currently PENDING_REMEDIATION but lease expired.
        Fails closed if another active session holds an unexpired lease.
        """
        rowcount = self.execute(
            """
            UPDATE auth_recovery_keys
            SET status = 'PENDING_REMEDIATION',
                pending_session_id = ?,
                session_nonce = ?,
                pending_started_at = CURRENT_TIMESTAMP,
                pending_expires_at = datetime(CURRENT_TIMESTAMP, '+' || ? || ' seconds')
            WHERE id = ?
              AND (
                  (status = 'ACTIVE' AND is_active = 1)
                  OR (status = 'PENDING_REMEDIATION' AND pending_expires_at < CURRENT_TIMESTAMP)
              );
            """,
            (session_id, session_nonce, lease_seconds, key_id),
        )
        return rowcount == 1

    def cancel_break_glass_lease(self, key_id: int, session_id: str) -> bool:
        """
        Releases a claimed lease back to ACTIVE state upon explicit cancellation.
        """
        rowcount = self.execute(
            """
            UPDATE auth_recovery_keys
            SET status = 'ACTIVE',
                pending_session_id = NULL,
                session_nonce = NULL,
                pending_started_at = NULL,
                pending_expires_at = NULL
            WHERE id = ? AND status = 'PENDING_REMEDIATION' AND pending_session_id = ?;
            """,
            (key_id, session_id),
        )
        return rowcount == 1

    def commit_break_glass_remediation(
        self,
        key_id: int,
        session_id: str,
        session_nonce: str,
        user_id: int,
        new_password_hash: str,
        new_email: str | None,
        new_key_identifier: str,
        new_key_hash: str,
        delivery_email_status: str = "PENDING",
        delivery_email_error: str | None = None,
    ) -> tuple[int, str, int]:
        """
        Atomically commits the Break-Glass remediation workflow:
        1. Validates the active lease (status, session_id, session_nonce, unexpired).
        2. Consumes the claimed recovery key.
        3. Updates user credentials (password, optional email), resets break-glass lockout, bumps security version.
        4. Inserts newly generated replacement recovery key as ACTIVE.
        Returns: (new_security_version, new_security_stamp, new_key_row_id)
        """
        # 1. 4-way lease validation
        existing_key = self.execute_fetchone(
            "SELECT status, pending_session_id, session_nonce, pending_expires_at FROM auth_recovery_keys WHERE id = ?;",
            (key_id,),
        )
        if not existing_key:
            from core.exceptions import AuthenticationError
            raise AuthenticationError("Recovery key not found.")
        if existing_key.get("status") != "PENDING_REMEDIATION":
            from core.exceptions import AuthenticationError
            raise AuthenticationError("Recovery key is not in PENDING_REMEDIATION state.")
        if (
            existing_key.get("pending_session_id") != session_id
            or existing_key.get("session_nonce") != session_nonce
        ):
            from core.exceptions import AuthenticationError
            raise AuthenticationError("Session ID or session nonce mismatch.")

        pending_exp = existing_key.get("pending_expires_at")
        if pending_exp:
            try:
                exp_dt = datetime.strptime(pending_exp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                exp_dt = datetime.fromisoformat(pending_exp).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= exp_dt:
                from core.exceptions import AuthenticationError
                raise AuthenticationError("Break-Glass lease has expired.")

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        new_stamp = secrets.token_hex(16)

        # 2. Mark old key consumed
        self.execute(
            """
            UPDATE auth_recovery_keys
            SET status = 'CONSUMED',
                is_active = 0,
                used_at = ?,
                consumed_at = ?
            WHERE id = ?;
            """,
            (now_utc, now_utc, key_id),
        )

        # 3. Update user
        if new_email and new_email.strip():
            self.execute(
                """
                UPDATE users
                SET password_hash = ?,
                    email = ?,
                    security_version = security_version + 1,
                    security_stamp = ?,
                    password_changed_at = ?,
                    failed_break_glass_attempts = 0,
                    break_glass_locked_until = NULL,
                    failed_login_attempts = 0,
                    locked_until = NULL,
                    updated_at = ?
                WHERE id = ?;
                """,
                (new_password_hash, new_email.strip(), new_stamp, now_utc, now_utc, user_id),
            )
        else:
            self.execute(
                """
                UPDATE users
                SET password_hash = ?,
                    security_version = security_version + 1,
                    security_stamp = ?,
                    password_changed_at = ?,
                    failed_break_glass_attempts = 0,
                    break_glass_locked_until = NULL,
                    failed_login_attempts = 0,
                    locked_until = NULL,
                    updated_at = ?
                WHERE id = ?;
                """,
                (new_password_hash, new_stamp, now_utc, now_utc, user_id),
            )

        # 4. Insert replacement key
        new_key_row_id = self.execute_insert(
            """
            INSERT INTO auth_recovery_keys (
                user_id,
                key_hash,
                key_identifier,
                status,
                delivery_email_status,
                delivery_email_attempted_at,
                delivery_email_error,
                is_active,
                created_at
            )
            VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, 1, ?);
            """,
            (
                user_id,
                new_key_hash,
                new_key_identifier,
                delivery_email_status,
                now_utc,
                delivery_email_error,
                now_utc,
            ),
        )

        user = self.get_by_id(user_id)
        new_version = int(user["security_version"]) if user else 1
        return new_version, new_stamp, new_key_row_id

    # --- Email Change Requests Operations ---

    def create_email_change_request(
        self,
        request_token: str,
        user_id: int,
        current_email: str,
        new_email: str,
        expires_at: str,
    ) -> int:
        """Creates an email change request, cancelling any existing pending requests for user."""
        self.execute(
            """
            UPDATE auth_email_change_requests
            SET status = 'CANCELLED'
            WHERE user_id = ? AND status = 'PENDING';
            """,
            (user_id,),
        )
        return self.execute_insert(
            """
            INSERT INTO auth_email_change_requests (
                request_token,
                user_id,
                current_email,
                new_email,
                status,
                current_verified,
                new_verified,
                expires_at
            )
            VALUES (?, ?, ?, ?, 'PENDING', 0, 0, ?);
            """,
            (request_token, user_id, current_email.strip(), new_email.strip(), expires_at),
        )

    def get_email_change_request(self, request_token: str) -> dict[str, Any] | None:
        """Retrieve an email change request by token."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                request_token,
                user_id,
                current_email,
                new_email,
                status,
                current_verified,
                new_verified,
                expires_at,
                created_at,
                completed_at
            FROM auth_email_change_requests
            WHERE request_token = ?;
            """,
            (request_token,),
        )

    def mark_email_change_current_verified(self, request_token: str) -> None:
        """Mark current email verification OTP as verified."""
        self.execute(
            """
            UPDATE auth_email_change_requests
            SET current_verified = 1
            WHERE request_token = ? AND status = 'PENDING';
            """,
            (request_token,),
        )

    def mark_email_change_new_verified(self, request_token: str) -> None:
        """Mark new email verification OTP as verified."""
        self.execute(
            """
            UPDATE auth_email_change_requests
            SET new_verified = 1
            WHERE request_token = ? AND status = 'PENDING';
            """,
            (request_token,),
        )

    def finalize_email_change(self, request_token: str) -> tuple[int, str]:
        """
        Validates dual verification and finalizes the email change in an atomic update.
        Bumps security_version, rotates security_stamp, updates email.
        Returns: (new_security_version, new_security_stamp)
        """
        request = self.get_email_change_request(request_token)
        if not request:
            from core.exceptions import ValidationError
            raise ValidationError("Email change request not found.")

        if request["status"] != "PENDING":
            from core.exceptions import ValidationError
            raise ValidationError(f"Email change request is already {request['status']}.")

        if not (bool(request["current_verified"]) and bool(request["new_verified"])):
            from core.exceptions import ValidationError
            raise ValidationError("Both current and new email addresses must be verified before completion.")

        # Check expiration
        expires_at_str = request["expires_at"]
        try:
            expires_at_dt = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            expires_at_dt = datetime.fromisoformat(expires_at_str).replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at_dt:
            self.execute(
                "UPDATE auth_email_change_requests SET status = 'EXPIRED' WHERE request_token = ?;",
                (request_token,),
            )
            from core.exceptions import ValidationError
            raise ValidationError("Email change request has expired. Please initiate a new request.")

        user_id = int(request["user_id"])
        new_email = str(request["new_email"]).strip()

        # Check uniqueness against existing users
        existing_owner = self.get_by_email(new_email)
        if existing_owner and int(existing_owner["id"]) != user_id:
            self.execute(
                "UPDATE auth_email_change_requests SET status = 'STALE_CONFLICT' WHERE request_token = ?;",
                (request_token,),
            )
            from core.exceptions import ConflictError
            raise ConflictError("The new email address is already registered to another account.")

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        new_stamp = secrets.token_hex(16)

        self.execute(
            """
            UPDATE users
            SET email = ?,
                security_version = security_version + 1,
                security_stamp = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (new_email, new_stamp, now_utc, user_id),
        )

        self.execute(
            """
            UPDATE auth_email_change_requests
            SET status = 'COMPLETED',
                completed_at = ?
            WHERE request_token = ?;
            """,
            (now_utc, request_token),
        )

        user = self.get_by_id(user_id)
        new_version = int(user["security_version"]) if user else 1
        return new_version, new_stamp

    def cancel_email_change_request(self, request_token: str) -> None:
        """Cancel a pending email change request."""
        self.execute(
            """
            UPDATE auth_email_change_requests
            SET status = 'CANCELLED'
            WHERE request_token = ? AND status = 'PENDING';
            """,
            (request_token,),
        )

    def get_latest_otp_challenge_by_purpose(self, user_id: int, purpose: str) -> dict[str, Any] | None:
        """Retrieve the latest unconsumed OTP challenge for a user and purpose."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                challenge_token,
                user_id,
                otp_hash,
                attempts_left,
                max_attempts,
                expires_at,
                purpose,
                is_consumed,
                consumed_at,
                created_at
            FROM auth_otp_challenges
            WHERE user_id = ? AND purpose = ? AND is_consumed = 0
            ORDER BY id DESC
            LIMIT 1;
            """,
            (user_id, purpose),
        )

    # --- Password Reset Tokens Operations ---

    def create_password_reset_token(
        self,
        token_hash: str,
        user_id: int,
        expires_at: str,
    ) -> int:
        """Persists a password reset token for normal email recovery."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        # Invalidate previous unconsumed tokens for this user
        self.execute(
            """
            UPDATE auth_password_reset_tokens
            SET is_consumed = 1,
                consumed_at = ?
            WHERE user_id = ? AND is_consumed = 0;
            """,
            (now_utc, user_id),
        )
        return self.execute_insert(
            """
            INSERT INTO auth_password_reset_tokens (
                token_hash,
                user_id,
                is_consumed,
                expires_at
            )
            VALUES (?, ?, 0, ?);
            """,
            (token_hash, user_id, expires_at),
        )

    def get_password_reset_token(self, token_hash: str) -> dict[str, Any] | None:
        """Retrieve a password reset token by hash."""
        return self.execute_fetchone(
            """
            SELECT
                id,
                token_hash,
                user_id,
                is_consumed,
                expires_at,
                created_at,
                consumed_at
            FROM auth_password_reset_tokens
            WHERE token_hash = ?;
            """,
            (token_hash,),
        )

    def consume_password_reset_token_and_update_password(
        self,
        token_hash: str,
        new_password_hash: str,
    ) -> tuple[int, str]:
        """
        Validates token, consumes it, and updates the user's password with security stamp rotation.
        Returns: (new_security_version, new_security_stamp)
        """
        record = self.get_password_reset_token(token_hash)
        if not record:
            from core.exceptions import AuthenticationError
            raise AuthenticationError("Invalid or expired password reset link.")

        if bool(record["is_consumed"]):
            from core.exceptions import AuthenticationError
            raise AuthenticationError("This password reset link has already been used.")

        # Check expiration
        expires_at_str = record["expires_at"]
        try:
            expires_at_dt = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            expires_at_dt = datetime.fromisoformat(expires_at_str).replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at_dt:
            from core.exceptions import AuthenticationError
            raise AuthenticationError("This password reset link has expired. Please request a new one.")

        user_id = int(record["user_id"])
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        new_stamp = secrets.token_hex(16)

        # Mark consumed
        self.execute(
            """
            UPDATE auth_password_reset_tokens
            SET is_consumed = 1,
                consumed_at = ?
            WHERE token_hash = ?;
            """,
            (now_utc, token_hash),
        )

        # Update user
        self.execute(
            """
            UPDATE users
            SET password_hash = ?,
                password_changed_at = ?,
                security_version = security_version + 1,
                security_stamp = ?,
                failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = ?
            WHERE id = ?;
            """,
            (new_password_hash, now_utc, new_stamp, now_utc, user_id),
        )

        user = self.get_by_id(user_id)
        new_version = int(user["security_version"]) if user else 1
        return new_version, new_stamp

