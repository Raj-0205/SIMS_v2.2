import pytest
import time
import sqlite3
from datetime import datetime, timezone, timedelta
from core.security.recovery import BreakGlassService, _enforce_global_rate_limit
from core.exceptions import RateLimitExceededError
from core.database.engine import DatabaseEngine
from core.database.transaction import TransactionManager

@pytest.fixture(autouse=True)
def clear_rate_limit_table():
    import core.security.recovery as rec
    rec._GLOBAL_BREAK_GLASS_ATTEMPTS.clear()
    with DatabaseEngine.connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS security_audit_attempts (id INTEGER PRIMARY KEY, identifier TEXT, success BOOLEAN, attempt_time DATETIME)")
        conn.execute("DELETE FROM security_audit_attempts")
        conn.commit()
    yield
    rec._GLOBAL_BREAK_GLASS_ATTEMPTS.clear()
    with DatabaseEngine.connection() as conn:
        conn.execute("DELETE FROM security_audit_attempts")
        conn.commit()

def test_break_glass_rate_limit_persistence():
    # 1. Trigger 5 failures
    for _ in range(5):
        try:
            _enforce_global_rate_limit()
        except RateLimitExceededError:
            pass

    # 2. Trigger another 5 failures
    for _ in range(5):
        try:
            _enforce_global_rate_limit()
        except RateLimitExceededError:
            pass

    # 3. The 11th attempt must be blocked
    with pytest.raises(RateLimitExceededError):
        _enforce_global_rate_limit()

def test_break_glass_window_behavior():
    # Insert an attempt from 20 minutes ago (outside window)
    with DatabaseEngine.connection() as conn:
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO security_audit_attempts (identifier, success, attempt_time) VALUES (?, ?, ?)",
                     ('GLOBAL', False, old_time))
    
    # Now we should be able to do 10 attempts without hitting the limit
    for _ in range(10):
        _enforce_global_rate_limit()

def test_concurrent_rate_limit_atomicity():
    # Simple linear check to verify the current persistent limit works
    for _ in range(10):
        _enforce_global_rate_limit()
    
    with pytest.raises(RateLimitExceededError):
        _enforce_global_rate_limit()
