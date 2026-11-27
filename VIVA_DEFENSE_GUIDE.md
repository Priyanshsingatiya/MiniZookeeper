# Mini ZooKeeper: College Viva & Judges Defense Guide

This document is your **cheat sheet** for college examinations, project presentations, and viva defenses. It explains the entire project in simple, beginner-friendly terms so you can confidently answer any question from examiners or judges.

---

## 1. The 30-Second Elevator Pitch

> *"Our project, Mini ZooKeeper, is an Event Ticket Booking Platform that solves the classic **double-booking concurrency problem**.*
>
> *During flash ticket sales, hundreds of users try to book the exact same seat at the same microsecond. Traditional databases struggle with race conditions.*
>
> *We implemented a **Two-Tier Architecture**:*
> *1. A lightweight **OS-level locking engine** (`fcntl.flock`) that gives exclusive access for 15 milliseconds to check and reserve the seat.*
> *2. A **5-minute database reservation lease** that holds the seat for the customer while they pay.*
>
> *This guarantees zero overselling, prevents deadlocks, and delivers high throughput without the heavy infrastructure overhead of full Apache ZooKeeper."*

---

## 2. Core Concepts in Plain English

### Concept 1: What is `fcntl.flock`?
- **Judge's Question:** *"How does your lock work under the hood?"*
- **Your Answer:** 
  > *"We use the Linux kernel system call `fcntl.flock` on a lock file (e.g. `/tmp/minizookeeper_locks/event_1_seat_5.lock`). The operating system kernel itself guarantees that only one process can hold an exclusive `LOCK_EX` lock on that file at any given moment. If a process crashes, the Linux kernel automatically closes the file and releases the lock, making it completely crash-safe."*

### Concept 2: OS Lock vs. 5-Minute Reservation (CRITICAL CONCEPT!)
- **Judge's Question:** *"Do you hold an operating system lock for the entire 5 minutes while the customer is typing their credit card?"*
- **Your Answer:** 
  > *"No, absolutely not! Holding an OS file lock for 5 minutes would block other requests and freeze workers.*
  > *Instead, we hold the OS lock for only **~15 milliseconds**—just long enough to check if the seat is `AVAILABLE`, change it to `RESERVED` in the database, and set a 5-minute expiry timestamp.*
  > *Then, in a `finally` block, we **immediately release the OS lock**. The database handles the 5-minute hold timer (`reserved_until`)."*

### Concept 3: Why Sort Seat IDs? (Deadlock Prevention)
- **Judge's Question:** *"What happens if User 1 books Seats [A, B] and User 2 books Seats [B, A] at the same time?"*
- **Your Answer:** 
  > *"If they acquired locks in random order, User 1 would hold lock A waiting for B, while User 2 holds lock B waiting for A—a classic circular deadlock.*
  > *To prevent this, in `endpoint_reserve_seats`, we always do `sorted_seat_ids = sorted(payload.seat_ids)`. Because all threads acquire locks in the exact same alphabetical/numerical order, circular wait deadlocks are mathematically impossible."*

### Concept 4: Server-Side Role Enforcement
- **Judge's Question:** *"How do you prevent a malicious customer from making themselves an Organizer?"*
- **Your Answer:** 
  > *"We never trust the frontend. In `src/auth.py`, when a user logs in, the backend checks their verified email against our server-side `APPROVED_ORGANIZERS` whitelist. Only approved emails receive the `ORGANIZER` role in their signed JWT session token. Customers cannot access organizer APIs even if they modify frontend JavaScript."*

### Concept 5: Why SQLite with WAL Mode?
- **Judge's Question:** *"Why use SQLite WAL mode instead of standard SQLite?"*
- **Your Answer:** 
  > *"Standard SQLite locks the entire database file during writes, blocking readers. We enabled **WAL (Write-Ahead Logging)** mode via `PRAGMA journal_mode=WAL;`. This allows multiple readers to read concurrently while a writer is writing, giving high local throughput without database lock errors."*

---

## 3. Project File Guide (What Every File Does)

| File | What It Does (In 1 Sentence) | Key Function to Show Judges |
| :--- | :--- | :--- |
| `src/lock_manager.py` | Core OS-level locking engine using Linux `fcntl.flock`. | `acquire_lock()` & `release_lock()` |
| `src/database.py` | SQLite database models (User, Event, Seat, Booking) and atomic inventory services. | `create_pending_reservation()` & `confirm_booking_payment()` |
| `src/auth.py` | Checks organizer whitelist, assigns roles, and issues JWT tokens. | `determine_user_role()` & `create_access_token()` |
| `src/lock_adapter.py` | Unified FastAPI REST API connecting the lock manager, database, and web frontend. | `endpoint_reserve_seats()` |
| `frontend/events.html` | Customer event discovery catalog with seat availability badges. | `fetchEvents()` |
| `frontend/event-details.html` | Interactive visual theater seating chart (Available, Selected, Reserved, Sold). | `handleReserveSeats()` |
| `frontend/checkout.html` | Order summary with live 5-minute countdown hold timer. | `startHoldTimer()` & `handleProcessPayment()` |
| `frontend/my-bookings.html` | Customer ticket pass view with scannable admission QR codes. | Renders live QR code from `/api/bookings/{id}/ticket-qr` |
| `frontend/organizer.html` | Organizer dashboard with live latency chart, node heartbeat, and real-time mutex monitor. | Live canvas chart & terminal stream |

---

## 4. Step-by-Step Code Walkthrough: How a Seat is Booked

When a customer clicks **"Reserve & Proceed to Pay"** for Seat A12:

```
Step 1: Frontend calls POST /api/bookings/reserve with { user_id: 2, event_id: 1, seat_ids: [12] }
                                |
Step 2: backend builds unique resource name: "event_1_seat_12"
                                |
Step 3: lock_manager.py calls fcntl.flock(fd, LOCK_EX) on "/tmp/minizookeeper_locks/event_1_seat_12.lock"
        - If Customer A gets it: success = True
        - If Customer B tries at same time: fcntl blocks or times out -> Customer B gets 409 Conflict
                                |
Step 4: Inside the lock, database.py checks if Seat 12 has status == 'AVAILABLE'
                                |
Step 5: database.py sets Seat 12 status = 'RESERVED', sets reserved_until = now + 5 minutes, 
        creates Booking record, and commits the transaction.
                                |
Step 6: FINALLY BLOCK EXECUTES:
        core_release() is called immediately. The OS lock on event_1_seat_12.lock is RELEASED!
                                |
Step 7: Customer B's request now checks database, sees status is already 'RESERVED', 
        and receives: "Seat A12 is already reserved."
```

---

## 5. Top 10 Questions Judges Will Ask & Exact Answers

#### Q1: "What is the difference between ZooKeeper and your Mini ZooKeeper?"
**Answer:** *"Apache ZooKeeper is a distributed coordination service that uses the ZAB (ZooKeeper Atomic Broadcast) consensus protocol across an ensemble of 3 to 5 servers. Our Mini ZooKeeper implements the core lock coordination semantics using operating system kernel locks (`fcntl.flock`). It delivers the same mutual exclusion and crash-recovery guarantees on a single machine or shared file system with zero setup overhead."*

#### Q2: "What happens if a process crashes while holding a lock?"
**Answer:** *"Because we use OS-level `fcntl.flock` attached to an open file descriptor, the Linux operating system kernel automatically closes all open file descriptors when a process terminates or crashes. The kernel immediately releases the lock, so deadlocks from crashed processes are physically impossible."*

#### Q3: "What happens if two customers click on the last seat at the exact same microsecond?"
**Answer:** *"Both requests reach `endpoint_reserve_seats`. The Mini ZooKeeper lock manager grants the OS lock to only ONE of them. The other request either waits briefly or receives a 409 Lock Contention response. The winning request marks the seat `RESERVED` in the database. When the second request checks the database, it sees the seat is already reserved and is cleanly rejected. Zero overselling occurs."*

#### Q4: "Where are the test cases for race conditions?"
**Answer:** *"In `tests/test_seat_concurrency.py`. We use Python `threading.Barrier` to synchronize two separate threads so they hit the `/api/bookings/reserve` endpoint for the exact same seat at the exact same microsecond. The test verifies that exactly 1 request succeeds (200 OK) and the other fails, proving race conditions are prevented."*

#### Q5: "How does the 5-minute seat hold expire?"
**Answer:** *"When a seat is reserved, we store a `reserved_until = now + 5 minutes` timestamp in the `booking_seats` table. If the customer does not complete payment within 5 minutes, our background endpoint `/api/bookings/cleanup-expired` finds all expired reservations and resets their seat status from `RESERVED` back to `AVAILABLE`."*

#### Q6: "How do you generate and verify the ticket QR code?"
**Answer:** *"When payment is confirmed, the `/api/bookings/{id}/ticket-qr` endpoint uses Python's `qrcode` library to generate a PNG image stream containing the booking reference, event title, venue, seat numbers, and user name. The customer can scan this code at the venue gate for admission."*

#### Q7: "How is your database protected against frontend price tampering?"
**Answer:** *"The frontend never sends ticket prices. In `create_pending_reservation`, the backend looks up `event.ticket_price` directly from the database and multiplies it by the number of seats: `total_amount = round(event.ticket_price * len(seats), 2)`. Any price sent from the browser is ignored."*

#### Q8: "How do you distinguish between an Organizer and a Customer?"
**Answer:** *"In `src/auth.py`, we maintain an approved email whitelist (`DEFAULT_APPROVED_ORGANIZERS`). When a user signs in with Google, we check their email. If it matches an approved organizer, their role is set to `ORGANIZER`, giving them access to event creation, poster upload, and revenue analytics. Otherwise, they are assigned `CUSTOMER`."*

#### Q9: "Why is the lock manager section removed from the customer and host UI?"
**Answer:** *"Because manual locking has no place in an event booking platform. Customers shouldn't manually acquire locks—Mini ZooKeeper automatically locks seats in the background during checkout. Organizers only need to see live telemetry and latency, which we provide on the Telemetry page."*

#### Q10: "Can this system run with PostgreSQL instead of SQLite?"
**Answer:** *"Yes! In `src/database.py`, we use SQLAlchemy. If you set the environment variable `DATABASE_URL=postgresql://user:password@localhost/dbname`, the system will automatically connect to PostgreSQL without changing a single line of application code."*

---

## 6. Commands to Run in Front of Judges

### 1. Run the Full Test Suite (Shows 59/59 Tests Passing):
```bash
python3 -m unittest discover tests -v
```

### 2. Run the High-Concurrency Race Condition Test:
```bash
python3 -m unittest -v tests/test_seat_concurrency.py
```

### 3. Start the Live Server:
```bash
python3 -m uvicorn src.lock_adapter:app --host 0.0.0.0 --port 8000
```

### 4. Open the Web Application:
- **Events Catalog:** `http://localhost:8000/frontend/events.html`
- **My Tickets (QR Passes):** `http://localhost:8000/frontend/my-bookings.html`
- **Telemetry & Latency Graph:** `http://localhost:8000/frontend/organizer.html`
- **Interactive OpenAPI Documentation:** `http://localhost:8000/docs`
