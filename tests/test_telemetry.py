"""
tests/test_telemetry.py
Tests for src/telemetry.py
"""

import os
import shutil
import unittest
from multiprocessing import Process
from pathlib import Path

from src.telemetry import export_to_json, record_event


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_data")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.test_dir / "test_locks.csv"
        self.json_path = self.test_dir / "test_locks.json"

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_record_single_event(self):
        event = {
            "request_id": "req-1",
            "client_id": "worker-1",
            "resource_name": "cart",
            "requested_at": "2026-11-24T14:00:00",
            "acquired_at": "2026-11-24T14:00:01",
            "released_at": "2026-11-24T14:00:02",
            "status": "released",
            "wait_ms": 1000,
            "hold_ms": 1000,
        }
        record = record_event(event, filepath=str(self.csv_path))
        self.assertEqual(record["request_id"], "req-1")
        self.assertEqual(record["wait_ms"], 1000)
        self.assertEqual(record["hold_ms"], 1000)

        # Check CSV content
        with open(self.csv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)  # header + 1 row
        self.assertIn("request_id,client_id,resource_name", lines[0])
        self.assertIn("req-1,worker-1,cart", lines[1])

    def test_wait_ms_never_negative(self):
        event = {
            "request_id": "req-2",
            "client_id": "worker-1",
            "status": "acquired",
            "wait_ms": -50,
        }
        record = record_event(event, filepath=str(self.csv_path))
        self.assertEqual(record["wait_ms"], 0)

    def test_hold_ms_only_for_released(self):
        # Event with status 'timed_out' should not keep hold_ms
        event = {
            "request_id": "req-3",
            "client_id": "worker-2",
            "status": "timed_out",
            "wait_ms": 500,
            "hold_ms": 200,  # should be cleared
        }
        record = record_event(event, filepath=str(self.csv_path))
        self.assertEqual(record["hold_ms"], "")

    def test_missing_timestamps(self):
        event = {
            "request_id": "req-4",
            "client_id": "worker-3",
            "status": "failed",
        }
        record = record_event(event, filepath=str(self.csv_path))
        self.assertEqual(record["requested_at"], "")
        self.assertEqual(record["acquired_at"], "")
        self.assertEqual(record["released_at"], "")

    def test_export_to_json(self):
        record_event(
            {"request_id": "req-5", "status": "requested", "wait_ms": 10},
            filepath=str(self.csv_path),
        )
        record_event(
            {"request_id": "req-6", "status": "released", "wait_ms": 20, "hold_ms": 30},
            filepath=str(self.csv_path),
        )

        records = export_to_json(str(self.csv_path), str(self.json_path))
        self.assertEqual(len(records), 2)
        self.assertTrue(self.json_path.exists())
        self.assertEqual(records[0]["request_id"], "req-5")
        self.assertEqual(records[1]["hold_ms"], 30)


def _worker_log(proc_id, count, csv_path):
    for i in range(count):
        record_event(
            {
                "request_id": f"proc-{proc_id}-req-{i}",
                "client_id": f"worker-{proc_id}",
                "resource_name": "db_lock",
                "status": "released",
                "wait_ms": 10,
                "hold_ms": 20,
            },
            filepath=csv_path,
        )


class TestConcurrentLogging(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_concurrent")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = str(self.test_dir / "concurrent_locks.csv")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_multi_process_logging(self):
        num_processes = 4
        records_per_proc = 25
        procs = []
        for pid in range(num_processes):
            p = Process(target=_worker_log, args=(pid, records_per_proc, self.csv_path))
            procs.append(p)
            p.start()

        for p in procs:
            p.join()

        # Verify all records were written without corruption
        with open(self.csv_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        # 1 header + 4 * 25 = 101 lines
        self.assertEqual(len(lines), 1 + (num_processes * records_per_proc))


if __name__ == "__main__":
    unittest.main()
