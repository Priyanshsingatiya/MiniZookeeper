"""
tests/test_core_locking.py
Mini ZooKeeper — Core Locking Test Suite (Backend A).

This test suite maps directly to the 6 required scenarios:
1. A client successfully acquiring a lock.
2. Another client being unable to acquire the same lock simultaneously.
3. A client acquiring the lock after the first client releases it.
4. Timeout when a lock is unavailable.
5. Unauthorized release being rejected.
6. Lock recovery after the owning process crashes.
"""

import unittest
import os
import sys
import time
import threading
import subprocess

# Add 'src' to Python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from lock_manager import (
    acquire_lock,
    release_lock,
    get_lock_status,
    HELD_LOCKS
)


class TestCoreLocking(unittest.TestCase):

    def setUp(self):
        """Runs before each test: cleans up any existing locks."""
        for res in list(HELD_LOCKS.keys()):
            info = HELD_LOCKS[res]
            release_lock(res, info["client_id"], info["lock_handle"])

    def tearDown(self):
        """Runs after each test: cleans up any held locks."""
        for res in list(HELD_LOCKS.keys()):
            info = HELD_LOCKS[res]
            release_lock(res, info["client_id"], info["lock_handle"])

    # ------------------------------------------------------------------------
    # Scenario 1: A client successfully acquiring a lock
    # ------------------------------------------------------------------------
    def test_1_client_successfully_acquires_lock(self):
        """Scenario 1: Verify a client can acquire a free resource lock."""
        resource = "inventory_item_101"
        client = "client_alice"

        result = acquire_lock(resource, client, timeout_seconds=0.0)

        # Assertions
        self.assertTrue(result["success"], "Lock should be successfully acquired")
        self.assertIsNotNone(result["lock_handle"], "A valid lock handle must be returned")
        self.assertEqual(result["client_id"], client)
        self.assertEqual(result["resource_name"], resource)

        # Status check
        status = get_lock_status(resource)
        self.assertTrue(status["is_locked"], "Resource should be reported as locked")
        self.assertEqual(status["owner"], client, "Alice should be reported as owner")

    # ------------------------------------------------------------------------
    # Scenario 2: Another client unable to acquire same lock simultaneously
    # ------------------------------------------------------------------------
    def test_2_concurrent_client_cannot_acquire_same_lock(self):
        """Scenario 2: Verify mutual exclusion — Bob cannot acquire while Alice holds it."""
        resource = "flight_ticket_seat_1A"
        alice = "client_alice"
        bob = "client_bob"

        # Alice acquires lock
        res_alice = acquire_lock(resource, alice, timeout_seconds=0.0)
        self.assertTrue(res_alice["success"])

        # Bob attempts to acquire the same lock without waiting (timeout=0.0)
        res_bob = acquire_lock(resource, bob, timeout_seconds=0.0)

        # Assertions
        self.assertFalse(res_bob["success"], "Bob must NOT be able to acquire the lock simultaneously")
        self.assertIsNone(res_bob["lock_handle"], "Bob must not receive a lock handle")
        self.assertIn("currently held", res_bob["message"])

    # ------------------------------------------------------------------------
    # Scenario 3: A client acquiring after the first client releases it
    # ------------------------------------------------------------------------
    def test_3_client_acquires_after_first_releases(self):
        """Scenario 3: Verify sequential handover — Bob acquires after Alice releases."""
        resource = "bank_account_77"
        alice = "client_alice"
        bob = "client_bob"

        # Alice acquires
        res_alice = acquire_lock(resource, alice, timeout_seconds=0.0)
        self.assertTrue(res_alice["success"])

        # Alice releases
        rel_alice = release_lock(resource, alice, res_alice["lock_handle"])
        self.assertTrue(rel_alice["success"], "Alice should successfully release the lock")

        # Now Bob attempts to acquire
        res_bob = acquire_lock(resource, bob, timeout_seconds=0.0)

        # Assertions
        self.assertTrue(res_bob["success"], "Bob must acquire the lock once Alice has released it")
        self.assertIsNotNone(res_bob["lock_handle"])
        self.assertEqual(res_bob["client_id"], bob)

    # ------------------------------------------------------------------------
    # Scenario 4: Timeout when a lock is unavailable
    # ------------------------------------------------------------------------
    def test_4_timeout_when_lock_unavailable(self):
        """Scenario 4: Verify client times out gracefully when resource remains busy."""
        resource = "database_migration_lock"
        alice = "client_alice"
        bob = "client_bob"

        # Alice acquires lock and holds it
        res_alice = acquire_lock(resource, alice, timeout_seconds=0.0)
        self.assertTrue(res_alice["success"])

        # Bob waits with a 0.25 second timeout
        start = time.time()
        res_bob = acquire_lock(resource, bob, timeout_seconds=0.25)
        elapsed = time.time() - start

        # Assertions
        self.assertFalse(res_bob["success"], "Bob's request should fail due to timeout")
        self.assertIsNone(res_bob["lock_handle"])
        self.assertIn("timed out", res_bob["message"])
        self.assertGreaterEqual(elapsed, 0.24, "Elapsed time should be at least timeout duration")

    # ------------------------------------------------------------------------
    # Scenario 5: Unauthorized release being rejected
    # ------------------------------------------------------------------------
    def test_5_unauthorized_release_rejected(self):
        """Scenario 5: Verify security — unauthorized client or wrong handle cannot unlock."""
        resource = "payment_gateway_lock"
        alice = "client_alice"
        eve = "client_eve"

        # Alice acquires lock
        res_alice = acquire_lock(resource, alice, timeout_seconds=0.0)
        self.assertTrue(res_alice["success"])
        valid_handle = res_alice["lock_handle"]

        # Attempt 1: Eve tries to release Alice's lock using Alice's handle
        rel_eve = release_lock(resource, eve, valid_handle)
        self.assertFalse(rel_eve["success"], "Eve should be rejected")
        self.assertIn("Unauthorized", rel_eve["message"])

        # Attempt 2: Alice tries to release with a fake handle
        rel_fake = release_lock(resource, alice, "forged_handle_999")
        self.assertFalse(rel_fake["success"], "Invalid handle should be rejected")
        self.assertIn("Invalid lock handle", rel_fake["message"])

        # Alice still legitimately owns the lock
        status = get_lock_status(resource)
        self.assertTrue(status["is_locked"])
        self.assertEqual(status["owner"], alice)

        # Legitimate release by Alice with valid handle succeeds
        rel_valid = release_lock(resource, alice, valid_handle)
        self.assertTrue(rel_valid["success"])

    # ------------------------------------------------------------------------
    # Scenario 6: Lock recovery after owning process crashes
    # ------------------------------------------------------------------------
    def test_6_lock_recovery_after_owning_process_crashes(self):
        """Scenario 6: Verify OS automatic crash recovery when a process dies (SIGKILL)."""
        resource = "critical_worker_batch"

        # Python child worker script that acquires lock and hangs
        child_script = f"""
import sys, os, time
sys.path.insert(0, '{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))}')
from lock_manager import acquire_lock

result = acquire_lock('{resource}', 'worker_child_process', timeout_seconds=0.0)
if result['success']:
    print('ACQUIRED_LOCK', flush=True)
    while True:
        time.sleep(1)
"""

        # Launch child process
        proc = subprocess.Popen(
            [sys.executable, "-c", child_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            # Wait for child to acquire lock
            signal_line = proc.stdout.readline().strip()
            self.assertEqual(signal_line, "ACQUIRED_LOCK")

            # Main process cannot acquire lock while child is alive
            attempt_while_alive = acquire_lock(resource, "main_client", timeout_seconds=0.0)
            self.assertFalse(attempt_while_alive["success"], "Should not acquire while child holds lock")

            # Simulate hard crash: terminate child process immediately with SIGKILL
            proc.kill()
            proc.wait()
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

        # The child process has crashed! The OS kernel must have auto-released the flock.
        # Main client should now be able to acquire the lock immediately!
        recovered = acquire_lock(resource, "main_client", timeout_seconds=1.0)
        self.assertTrue(recovered["success"], "Lock should be recovered automatically after crash")

        # Clean up
        release_lock(resource, "main_client", recovered["lock_handle"])


if __name__ == "__main__":
    unittest.main()
