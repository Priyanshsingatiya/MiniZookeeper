"""
tests/test_benchmark.py
Tests for src/benchmark.py
"""

import os
import shutil
import unittest
from pathlib import Path

from src.benchmark import generate_charts, run_benchmark_for_processes


class TestBenchmark(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_benchmark")
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_run_benchmark_single_process(self):
        metrics = run_benchmark_for_processes(
            num_processes=1, attempts_per_proc=2, output_dir=str(self.test_dir)
        )
        self.assertEqual(metrics["total_requests"], 2)
        self.assertEqual(metrics["successful_acquisitions"], 2)
        self.assertEqual(metrics["timed_out_requests"], 0)

    def test_chart_generation(self):
        sample_results = [
            {
                "processes": 1,
                "total_requests": 5,
                "successful_acquisitions": 5,
                "timeout_count": 0,
                "avg_wait_ms": 5.0,
                "avg_hold_ms": 30.0,
            },
            {
                "processes": 2,
                "total_requests": 10,
                "successful_acquisitions": 10,
                "timeout_count": 1,
                "avg_wait_ms": 15.0,
                "avg_hold_ms": 30.0,
            },
        ]
        charts = generate_charts(sample_results, output_dir=str(self.test_dir))
        self.assertTrue(Path(charts["chart_wait_time"]).exists())
        self.assertTrue(Path(charts["chart_timeouts"]).exists())
        self.assertTrue(Path(charts["chart_hold_time"]).exists())
        self.assertTrue(Path(charts["benchmark_dashboard"]).exists())


if __name__ == "__main__":
    unittest.main()
