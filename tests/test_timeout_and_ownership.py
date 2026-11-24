"""
tests/test_timeout_and_ownership.py
Comprehensive tests for Phase 3:
- Configurable waiting timeout expiration
- Unique request IDs
- Client ID and resource ownership tracking
- Lock handle verification
- Prevention of unauthorized release attempts
"""

import unittest
import os
import sys
import time
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from lock_manager import acquire_lock, release_lock, get_lock_status, HELD_LOCKS


class TestTimeoutAndOwnership(unittest.TestCase):

    def setUp(self):
        # Reset state before each test
        for res in list(HELD_LOCKS.keys()):
            info = HELD_LOCKS[res]
            release_lock(res, info["client_id"], info["lock_handle"])

    def test_unique_request_ids(self):
        """Verify that every lock attempt receives a distinct, unique request ID."""
        res1 = acquire_lock("resource_req_1", "client_1", timeout_seconds=0.0)
        res2 = acquire_lock("resource_req_2", "client_2", timeout_seconds=0.0)

        self.assertTrue(res1["request_id"].startswith("req_"))
        self.assertTrue(res2["request_id"].startswith("req_"))
        self.assertNotEqual(res1["request_id"], res2["request_id"])

        release_lock("resource_req_1", "client_1", res1["lock_handle"])
        release_lock("resource_req_2", "client_2", res2["lock_handle"])

    def test_timeout_expiration(self):
        """Verify that a client times out when a lock is not released in time."""
        resource = "busy_resource"
        alice = "client_alice"
        bob = "client_bob"

        # Alice acquires the lock
        res_alice = acquire_lock(resource, alice, timeout_seconds=0.0)
        self.assertTrue(res_alice["success"])

        # Bob requests the lock with a 0.3 second timeout
        start_time = time.time()
        res_bob = acquire_lock(resource, bob, timeout_seconds=0.3)
        duration = time.time() - start_time

        # Bob's attempt should have failed due to timeout
        self.assertFalse(res_bob["success"])
        self.assertIsNone(res_bob["lock_handle"])
        self.assertIn("timed out", res_bob["message"])
        self.assertGreaterEqual(duration, 0.28, "Waiting time should be around 0.3 seconds")

        # Alice still holds the lock
        status = get_lock_status(resource)
        self.assertTrue(status["is_locked"])
        self.assertEqual(status["owner"], alice)

        # Clean up
        release_lock(resource, alice, res_alice["lock_handle"])

    def test_acquire_within_timeout(self):
        """Verify that if the lock is released before the timeout expires, waiting client succeeds."""
        resource = "transient_resource"
        alice = "client_alice"
        bob = "client_bob"

        # Alice acquires the lock
        res_alice = acquire_lock(resource, alice, timeout_seconds=0.0)
        self.assertTrue(res_alice["success"])

        # Bob will wait up to 1.5 seconds in another thread
        bob_container = []

        def bob_thread_func():
            result = acquire_lock(resource, bob, timeout_seconds=1.5)
            bob_container.append(result)

        t = threading.Thread(target=bob_thread_func)
        t.start()

        # Alice holds lock for 0.2 seconds, then releases it
        time.sleep(0.2)
        release_lock(resource, alice, res_alice["lock_handle"])

        # Wait for Bob's thread
        t.join(timeout=2.0)

        # Bob should have succeeded!
        self.assertEqual(len(bob_container), 1)
        res_bob = bob_container[0]
        self.assertTrue(res_bob["success"])
        self.assertEqual(res_bob["client_id"], bob)
        self.assertIsNotNone(res_bob["lock_handle"])

        # Clean up Bob's lock
        release_lock(resource, bob, res_bob["lock_handle"])

    def test_unauthorized_release_rejected(self):
        """Verify that another client cannot release someone else's lock."""
        resource = "secure_account"
        alice = "client_alice"
        eve = "client_eve"

        # Alice acquires lock
        res_alice = acquire_lock(resource, alice, timeout_seconds=0.0)
        self.assertTrue(res_alice["success"])

        # Eve tries to release Alice's lock with Eve's client_id
        res_unauth_client = release_lock(resource, eve, res_alice["lock_handle"])
        self.assertFalse(res_unauth_client["success"])
        self.assertIn("Unauthorized", res_unauth_client["message"])

        # Eve tries to forge a fake lock handle using Alice's client_id
        res_fake_handle = release_lock(resource, alice, "fake_handle_999")
        self.assertFalse(res_fake_handle["success"])
        self.assertIn("Invalid lock handle", res_fake_handle["message"])

        # Alice can still legitimately release her lock with her valid handle
        res_valid = release_lock(resource, alice, res_alice["lock_handle"])
        self.assertTrue(res_valid["success"])


if __name__ == "__main__":
    unittest.main()
