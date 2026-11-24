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
├── frontend/
│   ├── activity.html       # Frontend B: Live Activity Logs page
│   ├── analytics.html      # Frontend B: Analytics & Performance Dashboard
│   ├── css/
│   │   └── style.css       # Shared styling, color-coded badges & cards
│   └── js/
│       ├── activity.js     # Live activity log fetching & table rendering
│       └── analytics.js    # Metric card updates & Matplotlib chart display
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

# Frontend B: Activity Logs & Analytics Dashboard

Frontend B provides responsive, framework-free web pages using pure HTML5, CSS3, and modern JavaScript:

### 1. Web Pages
- **Activity Logs (`/frontend/activity.html`)**: Real-time audit table showing all 9 fields (`request_id`, `client_id`, `resource_name`, `requested_at`, `acquired_at`, `released_at`, `status`, `wait_ms`, `hold_ms`) with color-coded status badges, empty states, error handling, and a refresh button.
- **Analytics Dashboard (`/frontend/analytics.html`)**: Displays 7 KPI summary cards (`Total Requests`, `Acquisitions`, `Released`, `Timeouts`, `Timeout Rate %`, `Avg Wait Time`, `Avg Hold Time`), a college viva reference guide explaining each metric, and 3 embedded Matplotlib benchmark charts.

### 2. Viewing the Dashboard
Start the unified FastAPI server:
```bash
python3 -m uvicorn src.lock_adapter:app --reload --port 8000
```
Then open in your browser:
- **Activity Logs:** `http://localhost:8000/frontend/activity.html`
- **Analytics Dashboard:** `http://localhost:8000/frontend/analytics.html`
- **API Documentation:** `http://localhost:8000/docs`

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

---

# Frontend A: Main Dashboard & Lock Management Interface

Frontend A provides a clean, responsive, and beginner-friendly web dashboard for real-time lock management. Built purely with semantic HTML5, modern vanilla CSS, and standard JavaScript `fetch()`.

### 1. File Structure
```
frontend/
├── index.html        # Clean HTML5 dashboard structure
├── css/
│   └── style.css     # Responsive CSS styling, cards, flexbox/grid layout
└── js/
    └── dashboard.js  # Vanilla JavaScript DOM handling, fetch() calls, and auto-polling
```

### 2. Core UI Components
1. **Navigation Bar**: Displays project branding, active tab navigation, and live backend connection health (`● Backend Connected` / `● Backend Offline`).
2. **KPI Stat Cards**: Real-time counter of Active Locks Held, Total Lifetime Requests, and System Health.
3. **Acquire Lock Card**: Form to request an exclusive lock with Resource Name, Client ID, and optional Wait Timeout.
4. **Release Lock Card**: Form to release an active lock using Client ID and secret `lock_handle` (with automatic handle pre-fill upon acquisition).
5. **Quick Resource Status Inspector**: Allows users to check whether any resource is currently `FREE` or `LOCKED` before attempting acquisition.
6. **Active Locks Table**: Real-time table displaying currently held locks, owners, timestamps, and quick-release action buttons.
7. **Automated Live Polling**: Automatically refreshes active locks and system summary every 3 seconds via `setInterval()`, keeping multiple browser windows synchronized without WebSockets.
8. **Recent Activity Feed**: Real-time chronological audit trail of recent lock events.

### 3. How to Launch and View
1. Start the unified FastAPI backend:
   ```bash
   python3 -m uvicorn src.lock_adapter:app --reload --port 8000
   ```
2. Open your web browser and navigate to:
   ```
   http://localhost:8000/frontend/index.html
   ```
Interactive API docs are also available at `http://localhost:8000/docs`.

Interactive Swagger docs: `http://localhost:8000/docs`
