"""
tests/test_lock_adapter.py
Verification tests for Phase 5:
- Adapter translation functions
- Protection against leaking OS file descriptors or file handles
- FastAPI REST endpoints for Frontend & Backend B integration
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from lock_manager import HELD_LOCKS, release_lock as core_release
from lock_adapter import (
    api_acquire,
    api_release,
    api_status,
    api_list_locks,
    app,
    FASTAPI_AVAILABLE
)

if FASTAPI_AVAILABLE:
    from fastapi.testclient import TestClient


class TestLockAdapter(unittest.TestCase):

    def setUp(self):
        # Reset state before each test
        for res in list(HELD_LOCKS.keys()):
            info = HELD_LOCKS[res]
            core_release(res, info["client_id"], info["lock_handle"])

    def test_adapter_functions_no_fd_leaks(self):
        """Verify adapter functions return clean data and never expose file descriptors."""
        res_name = "adapter_res_1"
        client = "client_web_1"

        # Acquire lock via adapter
        result = api_acquire(res_name, client, timeout_seconds=0.0)
        self.assertTrue(result["success"])
        self.assertIn("lock_handle", result)

        # CRITICAL SAFETY CHECK: Ensure no file descriptor or file object is in the response!
        self.assertNotIn("file_object", result)
        self.assertNotIn("fd", result)
        self.assertNotIn("fileno", result)

        # Check status via adapter
        status = api_status(res_name)
        self.assertTrue(status["is_locked"])
        self.assertEqual(status["owner"], client)
        self.assertNotIn("lock_handle", status, "Status must never reveal secret lock handle")
        self.assertNotIn("file_object", status)

        # Check list active locks
        active = api_list_locks()
        self.assertEqual(active["total_count"], 1)
        self.assertEqual(active["active_locks"][0]["resource_name"], res_name)

        # Release lock via adapter
        rel = api_release(res_name, client, result["lock_handle"])
        self.assertTrue(rel["success"])
        self.assertNotIn("file_object", rel)

    def test_fastapi_endpoints(self):
        """Verify FastAPI REST endpoints match the shared API contract."""
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI not available")

        client = TestClient(app)

        # 1. Health check
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "online")

        # 2. Acquire lock endpoint
        acquire_payload = {
            "resource_name": "seat_14B",
            "client_id": "booking_user_42",
            "timeout_seconds": 0.0
        }
        resp = client.post("/api/lock/acquire", json=acquire_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        lock_handle = data["lock_handle"]
        self.assertIsNotNone(lock_handle)

        # 3. Status endpoint
        resp = client.get("/api/lock/status?resource_name=seat_14B")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_locked"])
        self.assertEqual(resp.json()["owner"], "booking_user_42")

        # 4. Active locks dashboard endpoint
        resp = client.get("/api/locks")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total_count"], 1)

        # 5. Unauthorized release attempt via API
        unauth_payload = {
            "resource_name": "seat_14B",
            "client_id": "hacker_bob",
            "lock_handle": lock_handle
        }
        resp = client.post("/api/lock/release", json=unauth_payload)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["success"])

        # 6. Authorized release via API
        auth_payload = {
            "resource_name": "seat_14B",
            "client_id": "booking_user_42",
            "lock_handle": lock_handle
        }
        resp = client.post("/api/lock/release", json=auth_payload)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])

        # 7. Verify status is now unlocked
        resp = client.get("/api/lock/status?resource_name=seat_14B")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["is_locked"])

    def test_frontend_static_serving(self):
        """Verify frontend static files are properly served by FastAPI."""
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI not available")

        client = TestClient(app)

        # Check index.html
        resp_html = client.get("/frontend/index.html")
        self.assertEqual(resp_html.status_code, 200)
        self.assertIn("Mini ZooKeeper", resp_html.text)

        # Check style.css
        resp_css = client.get("/frontend/css/style.css")
        self.assertEqual(resp_css.status_code, 200)
        self.assertIn("--primary-color", resp_css.text)

        # Check dashboard.js
        resp_js = client.get("/frontend/js/dashboard.js")
        self.assertEqual(resp_js.status_code, 200)
        self.assertIn("handleAcquireLock", resp_js.text)


if __name__ == "__main__":
    unittest.main()
