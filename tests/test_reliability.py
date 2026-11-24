"""
tests/test_reliability.py
Reliability, error handling, and crash recovery tests for Phase 4.
"""

import unittest
import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from lock_manager import (
    acquire_lock,
    release_lock,
    get_lock_status,
    validate_resource_name,
    validate_client_id,
    HELD_LOCKS
)


class TestReliability(unittest.TestCase):

    def setUp(self):
        # Reset held locks
        for res in list(HELD_LOCKS.keys()):
            info = HELD_LOCKS[res]
            release_lock(res, info["client_id"], info["lock_handle"])

    def test_invalid_resource_names(self):
        """Verify invalid and dangerous resource names are rejected cleanly."""
        invalid_names = [
            "",                       # Empty
            "   ",                    # Whitespace only
            "../../etc/passwd",       # Path traversal attempt
            "folder/item",            # Directory separator
            "item\\file",             # Windows backslash
            "item*star",              # Illegal wildcard
            None,                     # Non-string
            12345                     # Integer
        ]

        for bad_name in invalid_names:
            is_valid, msg = validate_resource_name(bad_name)
            self.assertFalse(is_valid, f"Should reject invalid name: {bad_name}")

            # Also check acquire_lock returns clean error without crashing
            res = acquire_lock(bad_name, "client_1", timeout_seconds=0.0)
            self.assertFalse(res["success"])
            self.assertIn("Invalid resource name", res["message"])

    def test_invalid_client_ids(self):
        """Verify invalid client IDs are rejected."""
        invalid_clients = ["", "   ", None, 999]
        for bad_client in invalid_clients:
            is_valid, msg = validate_client_id(bad_client)
            self.assertFalse(is_valid)

            res = acquire_lock("valid_resource", bad_client, timeout_seconds=0.0)
            self.assertFalse(res["success"])
            self.assertIn("Invalid client ID", res["message"])

    def test_invalid_lock_handle_release(self):
        """Verify releasing with an invalid or empty lock handle fails safely."""
        res = acquire_lock("valid_item", "client_alice", timeout_seconds=0.0)
        self.assertTrue(res["success"])

        # Try releasing with empty handle
        rel_empty = release_lock("valid_item", "client_alice", "")
        self.assertFalse(rel_empty["success"])
        self.assertIn("Invalid lock handle", rel_empty["message"])

        # Try releasing with wrong handle
        rel_wrong = release_lock("valid_item", "client_alice", "wrong_token_123")
        self.assertFalse(rel_wrong["success"])
        self.assertIn("Invalid lock handle", rel_wrong["message"])

        # Clean up properly
        release_lock("valid_item", "client_alice", res["lock_handle"])

    def test_process_crash_recovery(self):
        """
        Verify that if a process crashes (killed with SIGKILL) while holding a lock,
        the OS kernel automatically releases the lock, allowing another process to acquire it.
        """
        resource = "crash_test_resource"

        # Worker script that acquires a lock and sleeps forever
        worker_code = f"""
import sys, os, time
sys.path.insert(0, '{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))}')
from lock_manager import acquire_lock

result = acquire_lock('{resource}', 'worker_child_process', timeout_seconds=0.0)
if result['success']:
    print('LOCKED', flush=True)
    # Sleep indefinitely until forcefully killed
    while True:
        time.sleep(1)
else:
    print('FAILED', flush=True)
"""

        # Start the worker process
        proc = subprocess.Popen(
            [sys.executable, "-c", worker_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait until the child process prints 'LOCKED'
        first_line = proc.stdout.readline().strip()
        self.assertEqual(first_line, "LOCKED", "Child process should acquire the lock")

        # Now, from this main process, verify the lock is held by external_process
        status_before = get_lock_status(resource)
        self.assertTrue(status_before["is_locked"])

        # Try to acquire in main process -> must fail immediately
        main_attempt = acquire_lock(resource, "main_client", timeout_seconds=0.0)
        self.assertFalse(main_attempt["success"], "Main client should not be able to acquire held lock")

        # Simulate a sudden process crash by forcefully killing the child process (SIGKILL / kill -9)
        proc.kill()
        proc.wait()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

        # The child process is dead! Now the OS kernel should have automatically freed the lock.
        # Main client tries to acquire the lock -> must succeed!
        recovered_acquire = acquire_lock(resource, "main_client", timeout_seconds=1.0)
        self.assertTrue(recovered_acquire["success"], "Main process should successfully acquire lock after child crashes")

        # Clean up
        release_lock(resource, "main_client", recovered_acquire["lock_handle"])


if __name__ == "__main__":
    unittest.main()
