"""
tests/test_integration.py
Demonstrates how Backend A (Lock Manager) integrates with Backend B (Telemetry).
"""

import shutil
import time
import unittest
from pathlib import Path

from src.telemetry import emit_event, record_event


class DummyLockManager:
    """
    Simulated Backend A Lock Manager.
    Notice: NO CSV or file writing code exists in this class!
    It simply calls emit_event() when lock state changes.
    """

    def __init__(self, log_filepath="data/locks.csv"):
        self.log_filepath = log_filepath
        self.locks = {}  # {resource_name: client_id}

    def request_lock(self, request_id, client_id, resource_name, timeout_ms=100):
        # 1. Log request attempt
        emit_event(
            request_id=request_id,
            client_id=client_id,
            resource_name=resource_name,
            status="requested",
            filepath=self.log_filepath,
        )

        start_time = time.time()
        # Simulate lock acquisition
        if resource_name not in self.locks:
            self.locks[resource_name] = client_id
            wait_ms = int((time.time() - start_time) * 1000)
            # 2. Log successful acquisition
            emit_event(
                request_id=request_id,
                client_id=client_id,
                resource_name=resource_name,
                status="acquired",
                wait_ms=wait_ms,
                filepath=self.log_filepath,
            )
            return True
        else:
            # Simulate timeout
            time.sleep(0.01)
            wait_ms = int((time.time() - start_time) * 1000)
            emit_event(
                request_id=request_id,
                client_id=client_id,
                resource_name=resource_name,
                status="timed_out",
                wait_ms=wait_ms,
                filepath=self.log_filepath,
            )
            return False

    def release_lock(self, request_id, client_id, resource_name, hold_ms=50):
        if self.locks.get(resource_name) == client_id:
            del self.locks[resource_name]
            # 3. Log release
            emit_event(
                request_id=request_id,
                client_id=client_id,
                resource_name=resource_name,
                status="released",
                hold_ms=hold_ms,
                filepath=self.log_filepath,
            )
            return True
        return False


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_integration")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = str(self.test_dir / "integration_locks.csv")
        self.manager = DummyLockManager(log_filepath=self.csv_path)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_lock_lifecycle_telemetry(self):
        # 1. Client 1 acquires lock
        acquired = self.manager.request_lock("req-1", "client-1", "cart-item")
        self.assertTrue(acquired)

        # 2. Client 2 tries to acquire same lock and times out
        timed_out = self.manager.request_lock("req-2", "client-2", "cart-item")
        self.assertFalse(timed_out)

        # 3. Client 1 releases lock
        released = self.manager.release_lock("req-1", "client-1", "cart-item", hold_ms=120)
        self.assertTrue(released)

        # Verify CSV contents
        with open(self.csv_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        # Header + req1_requested + req1_acquired + req2_requested + req2_timed_out + req1_released = 6 lines
        self.assertEqual(len(lines), 6)
        self.assertIn("req-1,client-1,cart-item", lines[2])
        self.assertIn("acquired", lines[2])
        self.assertIn("timed_out", lines[4])
        self.assertIn("released", lines[5])
        self.assertIn("120", lines[5])  # hold_ms


if __name__ == "__main__":
    unittest.main()
