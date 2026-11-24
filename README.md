# Mutex.io: Distributed Lock Service

**Founding Team:** Priyansh Singatiya & Kapil Poddar  
**Domain:** Distributed Systems & Infrastructure  

Mutex.io is a lightweight, zero-ops distributed lock service built for high-throughput e-commerce flash sales and data engineering pipelines. This MVP guarantees atomic mutual exclusion to prevent double-booking and cron job collisions, delivering crash-safe coordination without the heavy infrastructure footprint of Apache Zookeeper.

---

# The Problem We Solve
In distributed systems, if a server crashes while holding a lock, the entire application queue freezes. Mutex.io solves the classic "deadlock" and "split-brain" problems by enforcing strict mathematical coordination at the OS level, combined with automated failover handling.

---

# Core Capabilities

1. **Atomic Mutual Exclusion:** Leverages OS-level `fcntl.flock` and `os.O_CREAT | os.O_EXCL` syscalls to guarantee mathematically that no two processes can acquire the lock simultaneously.
2. **Automated Crash Recovery:** When a process crashes or terminates unexpectedly, the operating system kernel closes the open file descriptor, releasing the lock instantly.
3. **Enterprise Telemetry Pipeline:** Ships with an out-of-the-box analytics engine that tracks queue wait times, hold durations, and system contention in real-time.

---

# Tech Stack
- **Core Lock Engine (Backend A):** Python 3 (`os`, `fcntl`, `time`, `pathlib`)
- **Telemetry & Analytics (Backend B):** Python 3 (`csv`, `json`, `pathlib`), Pandas, Matplotlib
- **API & REST Layer:** FastAPI, Uvicorn
- **Demo UI:** Bootstrap 5
- **Phase 2 Architecture Roadmap:** Go, gRPC, HashiCorp Raft

---

# Architecture Overview

```
MiniZookeeper/
├── src/
│   ├── lock_manager.py     # Backend A: Core OS-level locking engine (fcntl.flock, crash recovery)
│   ├── lock_adapter.py     # Backend A: Safe API adapter & FastAPI endpoints
│   ├── telemetry.py        # Backend B: Process-safe event logging & JSON export
│   ├── analysis.py         # Backend B: Metrics calculation & Analytics API router
│   └── benchmark.py        # Backend B: Performance stress-testing & chart generation
├── data/
│   ├── locks.csv           # Telemetry log file
│   ├── locks.json          # Exported JSON logs
│   ├── benchmark_summary.csv # Benchmark metrics (1, 2, 4, 8 processes)
│   └── *.png               # Generated Matplotlib charts
└── tests/
    ├── test_core_locking.py           # Backend A: Core required viva scenarios
    ├── test_basic_locking.py          # Backend A: Basic acquire/release checks
    ├── test_timeout_and_ownership.py  # Backend A: Timeouts and token security
    ├── test_reliability.py           # Backend A: Crash recovery & input validation
    ├── test_lock_adapter.py           # Backend A: Adapter & REST API tests
    ├── test_telemetry.py              # Backend B: CSV & concurrency tests
    ├── test_analysis.py               # Backend B: Metrics & percentiles tests
    ├── test_benchmark.py              # Backend B: Benchmark & chart tests
    ├── test_api.py                    # Backend B: Analytics API endpoints
    └── test_integration.py            # End-to-end integration test
```

---

# Backend A: Core Locking System & API

### Shared API Contract
| Method | Endpoint | Description | Request Payload | Response Sample |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/lock/acquire` | Acquire a lock | `{"resource_name": "seat_12", "client_id": "alice", "timeout_seconds": 2.0}` | `{"success": true, "lock_handle": "handle_abc123", "request_id": "req_1", "message": "Lock acquired successfully."}` |
| `POST` | `/api/lock/release` | Release a lock | `{"resource_name": "seat_12", "client_id": "alice", "lock_handle": "handle_abc123"}` | `{"success": true, "resource_name": "seat_12", "message": "Lock released successfully."}` |
| `GET` | `/api/lock/status` | Inspect lock state | `?resource_name=seat_12` | `{"resource_name": "seat_12", "is_locked": true, "owner": "alice", "acquired_at": 1700000000.0, "error": null}` |
| `GET` | `/api/locks` | List active locks | *(None)* | `{"active_locks": [...], "total_count": 1}` |

---

# Backend B: Telemetry, Analytics & Benchmarking

### 1. Analytics & Telemetry API Endpoints
When mounted into FastAPI (`app.include_router(analytics_router)`):
| Method | Endpoint | Query Params | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/analytics/logs` | `limit` (default: 20) | Recent activity logs (newest first) |
| `GET` | `/analytics/summary` | *(None)* | Summary statistics (total requests, timeout rate, avg/median/P95 wait time, avg hold time) |
| `GET` | `/analytics/performance` | *(None)* | Benchmark comparison across 1, 2, 4, and 8 processes |
| `GET` | `/analytics/charts` | *(None)* | List available charts, metadata, and image URLs |
| `GET` | `/analytics/charts/{chart_name}` | *(None)* | Serves actual PNG chart images for HTML `<img>` tags |

### 2. Generating Performance Benchmarks & Charts
Run the multi-process benchmark suite:
```bash
python3 src/benchmark.py
```
This generates:
- `data/benchmark_summary.csv`
- `data/chart_wait_time.png` (Processes vs Average Waiting Time)
- `data/chart_timeouts.png` (Processes vs Timeout Count)
- `data/chart_hold_time.png` (Processes vs Average Holding Time)
- `data/benchmark_dashboard.png` (3-in-1 consolidated dashboard)

---

# Running All Tests

Run all unit, integration, and reliability tests across Backend A and Backend B:
```bash
python3 -m unittest discover tests -v
```

To run the FastAPI server locally:
```bash
python3 -m uvicorn src.lock_adapter:app --reload --port 8000
```
Interactive Swagger docs: `http://localhost:8000/docs`
