# Mutex.io: Distributed Lock Service

Founding Team:Priyansh Singatiya & Kapil Poddar
Domain: Distributed Systems & Infrastructure  

Mutex.io is a lightweight, zero-ops distributed lock service built for high-throughput e-commerce flash sales and data engineering pipelines. This MVP guarantees atomic mutual exclusion to prevent double-booking and cron job collisions, delivering crash-safe coordination without the heavy infrastructure footprint of Apache Zookeeper.

#The Problem We Solve
In distributed systems, if a server crashes while holding a lock, the entire application queue freezes. Mutex.io solves the classic "deadlock" and "split-brain" problems by enforcing strict mathematical coordination at the OS level, combined with automated failover handling.

#Core Capabilities

1. Atomic Mutual Exclusion:** Leverages OS-level `os.O_CREAT | os.O_EXCL` syscalls to guarantee mathematically that no two processes can acquire the lock simultaneously.
   
2. Automated Crash Recovery:** Implements strict TTL (Time-To-Live) leases and heartbeat monitoring to automatically detect terminated workers and safely hand over the lock within seconds.
   
3. Enterprise Telemetry Pipeline:** Ships with an out-of-the-box analytics engine that tracks queue wait times, hold durations, and system contention in real-time.

#Tech Stack
- Core Lock Engine:** Python 3 (`os`, `time`, `csv`)
- Telemetry Pipeline:** Pandas, Matplotlib
- Demo UI:** Bootstrap 5
- Phase 2 Architecture Roadmap:** Go, gRPC, HashiCorp Raft

# Running the Simulation & Backend B Telemetry

### 1. Telemetry & Analytics Modules (Backend B)
- **`src/telemetry.py`**: Safe, multi-process event logger writing to `data/locks.csv` with automatic file locking (`fcntl.flock`) and JSON export capability.
- **`src/analysis.py`**: Metrics engine calculating total requests, successful acquisitions, timeouts, timeout rate, average/median/P95 waiting times, and holding times. Also exports `analytics_router` for FastAPI.
- **`src/benchmark.py`**: Stress test simulation across 1, 2, 4, and 8 concurrent processes generating Matplotlib performance charts in `data/`.

### 2. Running Tests
Run the comprehensive test suite (17 tests covering CSV, JSON, concurrency, metrics, and API endpoints):
```bash
python3 -m unittest discover tests
```

### 3. Running Benchmarks & Generating Charts
Run the multi-process benchmark to generate simulation metrics and visual charts:
```bash
python3 src/benchmark.py
```
Output files produced in `data/`:
- `data/benchmark_summary.csv`
- `data/chart_wait_time.png` (Processes vs Average Wait Time)
- `data/chart_timeouts.png` (Processes vs Timeout Count)
- `data/chart_hold_time.png` (Processes vs Average Hold Time)
- `data/benchmark_dashboard.png` (3-in-1 consolidated dashboard)

### 4. Integrating with Backend A's FastAPI App
Attach the analytics router directly into your FastAPI application:
```python
from fastapi import FastAPI
from src.analysis import analytics_router

app = FastAPI(title="Mini ZooKeeper")
app.include_router(analytics_router)
```

Available endpoints:
- `GET /analytics/logs?limit=20`: Recent activity logs
- `GET /analytics/summary`: Summary metrics (Total requests, timeout rate, avg/median/P95 wait time, avg hold time)
- `GET /analytics/performance`: Benchmark results for 1, 2, 4, 8 processes
- `GET /analytics/charts`: List available charts and URLs
- `GET /analytics/charts/{chart_name}`: Serve PNG chart images for HTML `<img>` tags

