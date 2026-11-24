"""
src/analysis.py
Backend B: Analytics and Metrics Calculation for Mini ZooKeeper
"""

import csv
import math
from pathlib import Path


def read_logs(filepath="data/locks.csv"):
    """
    Reads the CSV log file and returns a list of row dictionaries.
    Handles missing or empty files gracefully.
    """
    csv_file = Path(filepath)
    if not csv_file.exists() or csv_file.stat().st_size == 0:
        return []

    records = []
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def calculate_metrics(logs):
    """
    Calculates summary metrics from the list of log records:
    - Total requests
    - Acquisitions, releases, timeouts
    - Timeout rate
    - Average, median, and 95th percentile waiting times
    - Average holding time
    """
    if not logs:
        return {
            "total_requests": 0,
            "successful_acquisitions": 0,
            "released_locks": 0,
            "timed_out_requests": 0,
            "timeout_rate_pct": 0.0,
            "avg_wait_ms": 0.0,
            "median_wait_ms": 0.0,
            "p95_wait_ms": 0.0,
            "avg_hold_ms": 0.0,
        }

    # Count unique requests if request_id is present, otherwise total records
    unique_request_ids = {r["request_id"] for r in logs if r.get("request_id")}
    total_requests = len(unique_request_ids) if unique_request_ids else len(logs)

    # Count occurrences by status
    successful_acquisitions = sum(1 for r in logs if r.get("status") == "acquired")
    released_locks = sum(1 for r in logs if r.get("status") == "released")
    timed_out_requests = sum(1 for r in logs if r.get("status") == "timed_out")

    # Timeout rate (percentage of requests that timed out)
    if total_requests > 0:
        timeout_rate_pct = round((timed_out_requests / total_requests) * 100, 2)
    else:
        timeout_rate_pct = 0.0

    # Extract wait times (in milliseconds)
    wait_times = []
    for r in logs:
        # Ignore released rows without an explicit wait time
        if r.get("status") == "released" and r.get("wait_ms") in ("", None):
            continue
        val = r.get("wait_ms")
        if val not in ("", None):
            try:
                wait_times.append(int(float(val)))
            except (ValueError, TypeError):
                pass

    # Extract hold times (only for released locks)
    hold_times = []
    for r in logs:
        if r.get("status") == "released":
            val = r.get("hold_ms")
            if val not in ("", None):
                try:
                    hold_times.append(int(float(val)))
                except (ValueError, TypeError):
                    pass

    # Calculate wait time statistics
    if wait_times:
        avg_wait_ms = round(sum(wait_times) / len(wait_times), 2)
        sorted_waits = sorted(wait_times)
        n = len(sorted_waits)

        # Median calculation
        mid = n // 2
        if n % 2 == 1:
            median_wait_ms = float(sorted_waits[mid])
        else:
            median_wait_ms = round((sorted_waits[mid - 1] + sorted_waits[mid]) / 2.0, 2)

        # 95th Percentile calculation
        # Index corresponding to 95% of data
        p95_idx = min(n - 1, math.ceil(0.95 * n) - 1)
        p95_wait_ms = float(sorted_waits[p95_idx])
    else:
        avg_wait_ms = 0.0
        median_wait_ms = 0.0
        p95_wait_ms = 0.0

    # Calculate hold time statistics
    if hold_times:
        avg_hold_ms = round(sum(hold_times) / len(hold_times), 2)
    else:
        avg_hold_ms = 0.0

    return {
        "total_requests": total_requests,
        "successful_acquisitions": successful_acquisitions,
        "released_locks": released_locks,
        "timed_out_requests": timed_out_requests,
        "timeout_rate_pct": timeout_rate_pct,
        "avg_wait_ms": avg_wait_ms,
        "median_wait_ms": median_wait_ms,
        "p95_wait_ms": p95_wait_ms,
        "avg_hold_ms": avg_hold_ms,
    }


def analyze_logs(filepath="data/locks.csv"):
    """Convenience helper to read logs and calculate metrics in one call."""
    logs = read_logs(filepath)
    return calculate_metrics(logs)


def print_summary(metrics):
    """Prints a clean, formatted report of the metrics to the console."""
    print("=" * 45)
    print("       MINI ZOOKEEPER - METRICS REPORT       ")
    print("=" * 45)
    print(f"Total Requests:           {metrics['total_requests']}")
    print(f"Successful Acquisitions:  {metrics['successful_acquisitions']}")
    print(f"Released Locks:           {metrics['released_locks']}")
    print(f"Timed-out Requests:       {metrics['timed_out_requests']}")
    print(f"Timeout Rate:             {metrics['timeout_rate_pct']}%")
    print("-" * 45)
    print(f"Average Wait Time:        {metrics['avg_wait_ms']} ms")
    print(f"Median Wait Time:         {metrics['median_wait_ms']} ms")
    print(f"95th Percentile Wait:     {metrics['p95_wait_ms']} ms")
    print(f"Average Hold Time:        {metrics['avg_hold_ms']} ms")
    print("=" * 45)


# =====================================================================
# Frontend & API Support Functions
# =====================================================================

def get_recent_logs(limit=20, filepath="data/locks.csv"):
    """Returns the most recent N log records (newest first)."""
    logs = read_logs(filepath)
    return logs[-limit:][::-1]


def get_summary(filepath="data/locks.csv"):
    """Returns a dictionary of summary metrics."""
    return analyze_logs(filepath)


def get_performance_summary(filepath="data/benchmark_summary.csv"):
    """Reads the benchmark summary CSV and returns a list of dictionaries."""
    csv_file = Path(filepath)
    if not csv_file.exists():
        return []
    records = []
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed = {}
            for k, v in row.items():
                try:
                    parsed[k] = float(v) if "." in v else int(v)
                except ValueError:
                    parsed[k] = v
            records.append(parsed)
    return records


def get_charts_info(data_dir="data"):
    """Returns paths and descriptions for generated benchmark charts."""
    folder = Path(data_dir)
    chart_files = {
        "chart_wait_time.png": "Number of processes vs Average waiting time",
        "chart_timeouts.png": "Number of processes vs Timeout count",
        "chart_hold_time.png": "Number of processes vs Average holding time",
        "benchmark_dashboard.png": "Consolidated 3-in-1 Performance Dashboard",
    }
    available = []
    for filename, description in chart_files.items():
        file_path = folder / filename
        available.append({
            "name": filename,
            "description": description,
            "exists": file_path.exists(),
            "url": f"/analytics/charts/{filename}",
            "file_path": str(file_path),
        })
    return available


# =====================================================================
# FastAPI Router (Integrates directly into Backend A's shared FastAPI app)
# =====================================================================

try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import FileResponse

    analytics_router = APIRouter(prefix="/analytics", tags=["Analytics & Telemetry"])

    @analytics_router.get("/logs")
    def api_get_recent_logs(limit: int = 20):
        """API endpoint: Fetch recent lock activity logs."""
        return get_recent_logs(limit=limit)

    @analytics_router.get("/summary")
    def api_get_summary():
        """API endpoint: Fetch summary statistics."""
        return get_summary()

    @analytics_router.get("/performance")
    def api_get_performance():
        """API endpoint: Fetch benchmark performance results."""
        return get_performance_summary()

    @analytics_router.get("/charts")
    def api_list_charts():
        """API endpoint: List available benchmark chart paths and metadata."""
        return get_charts_info()

    @analytics_router.get("/charts/{chart_name}")
    def api_get_chart_image(chart_name: str):
        """API endpoint: Serve the actual PNG image for the frontend <img> tag."""
        valid_charts = {
            "chart_wait_time.png",
            "chart_timeouts.png",
            "chart_hold_time.png",
            "benchmark_dashboard.png",
        }
        if chart_name not in valid_charts:
            raise HTTPException(status_code=404, detail="Chart not found")

        chart_path = Path("data") / chart_name
        if not chart_path.exists():
            raise HTTPException(status_code=404, detail="Chart image file has not been generated yet")

        return FileResponse(str(chart_path), media_type="image/png")

except ImportError:
    analytics_router = None


