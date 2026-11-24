"""
tests/test_analysis.py
Tests for src/analysis.py
"""

import shutil
import unittest
from pathlib import Path

from src.analysis import analyze_logs, calculate_metrics, read_logs
from src.telemetry import record_event


class TestAnalysis(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_analysis")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = str(self.test_dir / "test_analysis.csv")

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_empty_or_missing_file(self):
        # Non-existent file
        metrics = analyze_logs("non_existent_file.csv")
        self.assertEqual(metrics["total_requests"], 0)
        self.assertEqual(metrics["avg_wait_ms"], 0.0)

        # Empty file
        empty_path = self.test_dir / "empty.csv"
        empty_path.touch()
        metrics_empty = analyze_logs(str(empty_path))
        self.assertEqual(metrics_empty["total_requests"], 0)
        self.assertEqual(metrics_empty["timeout_rate_pct"], 0.0)

    def test_metrics_calculation(self):
        # 4 total requests:
        # req-1: acquired (wait: 10ms), released (hold: 100ms)
        # req-2: acquired (wait: 20ms), released (hold: 200ms)
        # req-3: acquired (wait: 30ms), released (hold: 300ms)
        # req-4: timed_out (wait: 40ms)
        events = [
            {"request_id": "req-1", "status": "acquired", "wait_ms": 10},
            {"request_id": "req-1", "status": "released", "hold_ms": 100},
            {"request_id": "req-2", "status": "acquired", "wait_ms": 20},
            {"request_id": "req-2", "status": "released", "hold_ms": 200},
            {"request_id": "req-3", "status": "acquired", "wait_ms": 30},
            {"request_id": "req-3", "status": "released", "hold_ms": 300},
            {"request_id": "req-4", "status": "timed_out", "wait_ms": 40},
        ]

        for e in events:
            record_event(e, filepath=self.csv_path)

        metrics = analyze_logs(self.csv_path)

        self.assertEqual(metrics["total_requests"], 4)
        self.assertEqual(metrics["successful_acquisitions"], 3)
        self.assertEqual(metrics["released_locks"], 3)
        self.assertEqual(metrics["timed_out_requests"], 1)
        self.assertEqual(metrics["timeout_rate_pct"], 25.0)

        # Wait times: [10, 20, 30, 40]
        # Avg = (10+20+30+40)/4 = 25.0
        # Median = (20+30)/2 = 25.0
        # P95 = 40.0
        self.assertEqual(metrics["avg_wait_ms"], 25.0)
        self.assertEqual(metrics["median_wait_ms"], 25.0)
        self.assertEqual(metrics["p95_wait_ms"], 40.0)

        # Hold times: [100, 200, 300]
        # Avg = (100+200+300)/3 = 200.0
        self.assertEqual(metrics["avg_hold_ms"], 200.0)


if __name__ == "__main__":
    unittest.main()
