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

#Running the Simulation**
(Instructions for running the local worker scripts will be added here during Week 2).*
