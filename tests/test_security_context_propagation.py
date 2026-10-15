import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from core.security.context import SecurityContext, UserIdentity

def test_context_capture_and_restore():
    """Verify identity is correctly captured and restored in a new context."""
    SecurityContext.set_current_user(1, "admin", "ADMIN")
    ctx = SecurityContext.capture_context()
    SecurityContext.clear()
    
    assert SecurityContext.current_user() is None
    
    # Run in captured context
    def check_user():
        return SecurityContext.current_user().username
    
    result = SecurityContext.run_in_context(ctx, check_user)
    assert result == "admin"

def test_concurrency_isolation():
    """Prove two simultaneous operations cannot observe each other's identity."""
    results = []
    
    def worker(user_id, username, role):
        # Set identity and sleep to simulate work and overlap
        SecurityContext.set_current_user(user_id, username, role)
        time.sleep(0.1)
        results.append(SecurityContext.current_user().username)
        SecurityContext.clear()

    # Run two workers concurrently in separate threads
    # Note: contextvars.ContextVar is local to the thread by default
    t1 = threading.Thread(target=worker, args=(1, "user1", "ADMIN"))
    t2 = threading.Thread(target=worker, args=(2, "user2", "ADMINISTRATOR"))
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    assert "user1" in results
    assert "user2" in results
    assert len(results) == 2

def test_worker_wrap_propagation():
    """Verify wrap_worker correctly propagates identity to background thread."""
    SecurityContext.set_current_user(100, "worker_boss", "ADMINISTRATOR")
    
    def task():
        return SecurityContext.current_user().username
    
    wrapped_task = SecurityContext.wrap_worker(task)
    
    # Execute wrapped task in a new thread
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(wrapped_task)
        result = future.result()
        
    assert result == "worker_boss"
    SecurityContext.clear()

def test_fail_closed_behavior():
    """Verify that missing context fails closed (returns None)."""
    SecurityContext.clear()
    assert SecurityContext.current_user() is None
    assert SecurityContext.get_current_role() is None
