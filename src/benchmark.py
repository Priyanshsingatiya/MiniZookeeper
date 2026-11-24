"""
src/benchmark.py
Backend B: Performance Benchmarking and Chart Generation for Mini ZooKeeper
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set writable cache directory for Matplotlib in restricted environments
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

import csv
import multiprocessing
import random
import time
from pathlib import Path

import matplotlib.pyplot as plt

from src.analysis import analyze_logs
from src.telemetry import emit_event


def worker_task(process_id, attempts, lock_file, log_file, hold_seconds=0.03, timeout_seconds=0.15):
    """
    Worker process simulation:
    Tries to acquire the atomic lock using os.O_CREAT | os.O_EXCL.
    Logs wait times, timeouts, and hold times using telemetry.
    """
    for i in range(attempts):
        request_id = f"p{process_id}-req{i}"
        client_id = f"process-{process_id}"
        resource_name = "flash_sale_product"

        start_time = time.time()
        acquired = False
        fd = None

        # Attempt to acquire lock until timeout
        while (time.time() - start_time) < timeout_seconds:
            try:
                # Atomic lock acquisition using OS syscall
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                acquired = True
                break
            except FileExistsError:
                # Lock is currently held by another process; wait briefly and retry
                time.sleep(0.005)

        wait_ms = int((time.time() - start_time) * 1000)

        if acquired:
            # 1. Log acquisition
            emit_event(
                request_id=request_id,
                client_id=client_id,
                resource_name=resource_name,
                status="acquired",
                wait_ms=wait_ms,
                filepath=log_file,
            )

            # Hold the lock while doing simulated work
            time.sleep(hold_seconds)
            hold_ms = int(hold_seconds * 1000)

            # Release the lock by closing and deleting the file
            try:
                os.close(fd)
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except OSError:
                pass

            # 2. Log release
            emit_event(
                request_id=request_id,
                client_id=client_id,
                resource_name=resource_name,
                status="released",
                hold_ms=hold_ms,
                filepath=log_file,
            )
        else:
            # 3. Log timeout
            emit_event(
                request_id=request_id,
                client_id=client_id,
                resource_name=resource_name,
                status="timed_out",
                wait_ms=wait_ms,
                filepath=log_file,
            )

        # Brief random sleep between requests to simulate realistic client arrival
        time.sleep(random.uniform(0.005, 0.02))


def run_benchmark_for_processes(num_processes, attempts_per_proc=5, output_dir="data"):
    """
    Runs benchmark with a given number of concurrent processes and records metrics.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    log_file = str(out_path / f"benchmark_p{num_processes}.csv")
    lock_file = str(out_path / f"benchmark_p{num_processes}.lock")

    # Clean up previous run files if present
    if os.path.exists(log_file):
        os.remove(log_file)
    if os.path.exists(lock_file):
        os.remove(lock_file)

    processes = []
    for pid in range(num_processes):
        p = multiprocessing.Process(
            target=worker_task,
            args=(pid, attempts_per_proc, lock_file, log_file),
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    # Clean up lock file if leftover
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except OSError:
            pass

    # Analyze recorded data
    metrics = analyze_logs(log_file)
    return metrics


def generate_charts(results, output_dir="data"):
    """
    Generates 3 separate Matplotlib charts and 1 unified dashboard.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    procs = [r["processes"] for r in results]
    avg_waits = [r["avg_wait_ms"] for r in results]
    timeouts = [r["timeout_count"] for r in results]
    avg_holds = [r["avg_hold_ms"] for r in results]

    # Chart 1: Number of processes vs Average Waiting Time
    plt.figure(figsize=(7, 4.5))
    plt.plot(procs, avg_waits, marker="o", color="#2563EB", linewidth=2.5, markersize=8)
    plt.title("Contention: Processes vs Average Waiting Time", fontsize=13, fontweight="bold")
    plt.xlabel("Number of Processes", fontsize=11)
    plt.ylabel("Average Wait Time (ms)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.xticks(procs)
    chart1_path = out_path / "chart_wait_time.png"
    plt.tight_layout()
    plt.savefig(chart1_path, dpi=150)
    plt.close()

    # Chart 2: Number of processes vs Timeout Count
    plt.figure(figsize=(7, 4.5))
    plt.bar([str(p) for p in procs], timeouts, color="#DC2626", width=0.5)
    plt.title("Contention: Processes vs Timeout Count", fontsize=13, fontweight="bold")
    plt.xlabel("Number of Processes", fontsize=11)
    plt.ylabel("Timeout Count", fontsize=11)
    plt.grid(axis="y", linestyle="--", alpha=0.6)
    chart2_path = out_path / "chart_timeouts.png"
    plt.tight_layout()
    plt.savefig(chart2_path, dpi=150)
    plt.close()

    # Chart 3: Number of processes vs Average Holding Time
    plt.figure(figsize=(7, 4.5))
    plt.plot(procs, avg_holds, marker="s", color="#16A34A", linewidth=2.5, markersize=8)
    plt.title("Stability: Processes vs Average Holding Time", fontsize=13, fontweight="bold")
    plt.xlabel("Number of Processes", fontsize=11)
    plt.ylabel("Average Hold Time (ms)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.xticks(procs)
    chart3_path = out_path / "chart_hold_time.png"
    plt.tight_layout()
    plt.savefig(chart3_path, dpi=150)
    plt.close()

    # Unified 3-in-1 Dashboard
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.5))

    ax1.plot(procs, avg_waits, marker="o", color="#2563EB", linewidth=2)
    ax1.set_title("Processes vs Avg Wait Time (ms)")
    ax1.set_xlabel("Processes")
    ax1.set_ylabel("ms")
    ax1.set_xticks(procs)
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2.bar([str(p) for p in procs], timeouts, color="#DC2626", width=0.5)
    ax2.set_title("Processes vs Timeouts")
    ax2.set_xlabel("Processes")
    ax2.set_ylabel("Count")
    ax2.grid(axis="y", linestyle="--", alpha=0.5)

    ax3.plot(procs, avg_holds, marker="s", color="#16A34A", linewidth=2)
    ax3.set_title("Processes vs Avg Hold Time (ms)")
    ax3.set_xlabel("Processes")
    ax3.set_ylabel("ms")
    ax3.set_xticks(procs)
    ax3.grid(True, linestyle="--", alpha=0.5)

    plt.suptitle("Mini ZooKeeper: Performance Benchmark Dashboard", fontsize=14, fontweight="bold")
    plt.tight_layout()
    dashboard_path = out_path / "benchmark_dashboard.png"
    plt.savefig(dashboard_path, dpi=150)
    plt.close()

    return {
        "chart_wait_time": str(chart1_path),
        "chart_timeouts": str(chart2_path),
        "chart_hold_time": str(chart3_path),
        "benchmark_dashboard": str(dashboard_path),
    }


def run_all_benchmarks():
    """Runs tests for 1, 2, 4, 8 processes and outputs summary and charts."""
    process_counts = [1, 2, 4, 8]
    results = []

    print("Running Mini ZooKeeper Benchmarks (1, 2, 4, 8 processes)...")
    for n in process_counts:
        print(f" -> Running benchmark with {n} process(es)...")
        metrics = run_benchmark_for_processes(n, attempts_per_proc=5)
        results.append({
            "processes": n,
            "total_requests": metrics["total_requests"],
            "successful_acquisitions": metrics["successful_acquisitions"],
            "timeout_count": metrics["timed_out_requests"],
            "avg_wait_ms": metrics["avg_wait_ms"],
            "median_wait_ms": metrics["median_wait_ms"],
            "p95_wait_ms": metrics["p95_wait_ms"],
            "avg_hold_ms": metrics["avg_hold_ms"],
        })

    # Save summary CSV
    summary_path = Path("data/benchmark_summary.csv")
    with open(summary_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"Benchmark summary saved to {summary_path}")

    # Generate charts
    charts = generate_charts(results)
    print("Generated charts:")
    for name, path in charts.items():
        print(f" - {name}: {path}")

    return results, charts


if __name__ == "__main__":
    run_all_benchmarks()
