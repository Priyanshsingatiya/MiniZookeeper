"""
tests/test_api.py
Tests for Analytics FastAPI endpoints
"""

import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.analysis import analytics_router


class TestAnalyticsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a shared FastAPI test app including our analytics router
        cls.app = FastAPI(title="Mini ZooKeeper Shared App")
        cls.app.include_router(analytics_router)
        cls.client = TestClient(cls.app)

    def test_get_logs_endpoint(self):
        response = self.client.get("/analytics/logs?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_get_summary_endpoint(self):
        response = self.client.get("/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_requests", data)
        self.assertIn("avg_wait_ms", data)
        self.assertIn("timeout_rate_pct", data)

    def test_get_performance_endpoint(self):
        response = self.client.get("/analytics/performance")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_get_charts_list(self):
        response = self.client.get("/analytics/charts")
        self.assertEqual(response.status_code, 200)
        charts = response.json()
        self.assertTrue(len(charts) >= 3)
        names = [c["name"] for c in charts]
        self.assertIn("chart_wait_time.png", names)

    def test_get_chart_image_existing(self):
        # Check that chart_wait_time.png returns an image
        if Path("data/chart_wait_time.png").exists():
            response = self.client.get("/analytics/charts/chart_wait_time.png")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/png")

    def test_get_chart_image_404(self):
        response = self.client.get("/analytics/charts/invalid_chart.png")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
