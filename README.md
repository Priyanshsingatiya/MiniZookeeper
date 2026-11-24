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

# Running the Simulation
(Instructions for running the local worker scripts will be added here during Week 2).*

---

# Backend A: Core Locking System & API Documentation

## 1. Overview & Architecture
Backend A is responsible for the core locking engine, crash recovery, and the safe API adapter for Mini ZooKeeper.

```
MiniZookeeper/
├── src/
│   ├── lock_manager.py   # Core OS-level locking engine (fcntl.flock, crash recovery)
│   └── lock_adapter.py   # Safe API bridge & FastAPI REST endpoints
└── tests/
    ├── test_core_locking.py           # 6 core required scenarios (viva showcase)
    ├── test_basic_locking.py          # Basic acquire/release checks
    ├── test_timeout_and_ownership.py  # Timeout expiration and token security
    ├── test_reliability.py           # Input validation and process crash recovery
    └── test_lock_adapter.py           # Adapter formatting & FastAPI endpoints
```

## 2. Core Modules

### `src/lock_manager.py` (Core Engine)
- **Atomic Mutual Exclusion**: Uses Linux OS kernel locking via `fcntl.flock` with `LOCK_EX` (exclusive) and `LOCK_NB` (non-blocking).
- **Crash Recovery**: When a process crashes or is killed (`kill -9`), the Linux kernel automatically closes all open file descriptors, instantly releasing the lock.
- **Configurable Timeouts**: Supports non-blocking attempts (`timeout_seconds=0.0`) or waiting loops.
- **Ownership Verification**: Issues unique `lock_handle` bearer tokens. Locks can only be unlocked when both `client_id` and `lock_handle` match.
- **Input Validation**: Sanitizes resource names to prevent directory traversal (`..`) and invalid characters.

### `src/lock_adapter.py` (API Adapter Layer)
- Bridges the low-level locking engine with Backend B and web clients.
- Translates responses into clean, JSON-serializable Python dictionaries.
- **Zero FD Leak Guarantee**: Server file descriptors (`fd`, `fileno`, `file_object`) are completely isolated and never exposed to the frontend.

## 3. Shared API Contract (Backend B & Frontend)

| Method | Endpoint | Description | Request Payload | Response Sample |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/lock/acquire` | Acquire a lock | `{"resource_name": "seat_12", "client_id": "alice", "timeout_seconds": 2.0}` | `{"success": true, "lock_handle": "handle_abc123", "request_id": "req_1", "message": "Lock acquired successfully."}` |
| `POST` | `/api/lock/release` | Release a lock | `{"resource_name": "seat_12", "client_id": "alice", "lock_handle": "handle_abc123"}` | `{"success": true, "resource_name": "seat_12", "message": "Lock released successfully."}` |
| `GET` | `/api/lock/status` | Inspect lock state | `?resource_name=seat_12` | `{"resource_name": "seat_12", "is_locked": true, "owner": "alice", "acquired_at": 1700000000.0, "error": null}` |
| `GET` | `/api/locks` | List active locks | *(None)* | `{"active_locks": [...], "total_count": 1}` |

## 4. Running the Tests

To run the 6 core scenarios with detailed output:
```bash
python3 -m unittest tests/test_core_locking.py -v
```

To run all 18 unit tests across the entire suite:
```bash
python3 -m unittest discover tests -v
```

To run the FastAPI server locally:
```bash
python3 -m uvicorn src.lock_adapter:app --reload --port 8000
```
Interactive API docs are then available at: `http://localhost:8000/docs`

