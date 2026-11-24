"""
tests/test_basic_locking.py
Updated basic verification tests for Phase 2 and 3 of Mini ZooKeeper.
"""

import unittest
import os
import sys

# Add 'src' to module path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from lock_manager import acquire_lock, release_lock, get_lock_status, HELD_LOCKS


class TestBasicLocking(unittest.TestCase):

    def setUp(self):
        # Clean up any held locks before each test
        for resource in list(HELD_LOCKS.keys()):
            info = HELD_LOCKS[resource]
            release_lock(resource, info["client_id"], info["lock_handle"])

    def test_single_client_acquire_and_release(self):
        resource = "item_1"
        client = "client_alice"

        # Initially, resource is not locked
        status = get_lock_status(resource)
        self.assertFalse(status["is_locked"])

        # Alice acquires the lock
        res = acquire_lock(resource, client, timeout_seconds=0.0)
        self.assertTrue(res["success"], "Alice should acquire the lock")
        self.assertIsNotNone(res["lock_handle"], "Lock handle must be generated")

        # Check status
        status = get_lock_status(resource)
        self.assertTrue(status["is_locked"])
        self.assertEqual(status["owner"], client)

        # Alice releases the lock
        rel = release_lock(resource, client, res["lock_handle"])
        self.assertTrue(rel["success"], "Alice should release the lock")

        # Now free
        status = get_lock_status(resource)
        self.assertFalse(status["is_locked"])

    def test_mutual_exclusion(self):
        resource = "item_2"
        alice = "client_alice"
        bob = "client_bob"

        # Alice acquires lock
        res_alice = acquire_lock(resource, alice, timeout_seconds=0.0)
        self.assertTrue(res_alice["success"])

        # Bob tries to acquire immediately without waiting -> should fail
        res_bob = acquire_lock(resource, bob, timeout_seconds=0.0)
        self.assertFalse(res_bob["success"])
        self.assertIsNone(res_bob["lock_handle"])

        # Alice releases
        rel_alice = release_lock(resource, alice, res_alice["lock_handle"])
        self.assertTrue(rel_alice["success"])

        # Now Bob can acquire
        res_bob_after = acquire_lock(resource, bob, timeout_seconds=0.0)
        self.assertTrue(res_bob_after["success"])

        # Clean up Bob's lock
        release_lock(resource, bob, res_bob_after["lock_handle"])


if __name__ == "__main__":
    unittest.main()
