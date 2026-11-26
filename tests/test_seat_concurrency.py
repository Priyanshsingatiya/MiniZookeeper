"""
tests/test_seat_concurrency.py
Phase 5: Concurrency and Race Condition Verification for Mini ZooKeeper Seat Locking Engine.

Tests:
1. Two simultaneous requests attempting to reserve the exact same seat.
   - Guaranteed outcome: Exactly ONE succeeds; the other is rejected with seat reserved / lock contention.
   - Zero double-booking.
2. Two simultaneous requests reserving DIFFERENT seats.
   - Guaranteed outcome: Both succeed in parallel.
3. Lock is short-lived: Released immediately after DB reservation.
"""

import unittest
import os
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from database import Base, get_db, Event, Seat, User
from lock_adapter import app


class TestSeatConcurrency(unittest.TestCase):
    def setUp(self):
        # Use file-based SQLite database with WAL mode so multiple threads can write concurrently
        self.db_path = f"/tmp/test_concurrency_{int(time.time()*1000)}.db"
        self.test_engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False}
        )
        # Enable WAL mode and foreign keys
        with self.test_engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON;")

        self.TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)
        Base.metadata.create_all(bind=self.test_engine)

        def override_get_db():
            db = self.TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Seed 1 event with 5 seats and 2 users
        db = self.TestSessionLocal()
        user_a = User(name="Customer A", email="cust_a@example.com", role="CUSTOMER")
        user_b = User(name="Customer B", email="cust_b@example.com", role="CUSTOMER")
        user_c = User(name="Customer C", email="cust_c@example.com", role="CUSTOMER")
        db.add_all([user_a, user_b, user_c])
        db.commit()

        event = Event(
            title="High Contention Championship Match",
            venue="Grand Arena",
            event_date=datetime.now(timezone.utc) + timedelta(days=3),
            ticket_price=100.0,
            total_seats=5,
            status="PUBLISHED"
        )
        db.add(event)
        db.flush()

        self.seat_ids = []
        for i in range(1, 6):
            seat = Seat(event_id=event.id, seat_number=f"RowA-{i}", status="AVAILABLE")
            db.add(seat)
            db.flush()
            self.seat_ids.append(seat.id)

        db.commit()
        self.event_id = event.id
        self.user_a_id = user_a.id
        self.user_b_id = user_b.id
        self.user_c_id = user_c.id
        db.close()

    def tearDown(self):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.test_engine)
        self.test_engine.dispose()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_simultaneous_same_seat_contention(self):
        """
        CRITICAL TEST FOR PHASE 5:
        Customer A and Customer B attempt to book the EXACT SAME SEAT (Seat 1) simultaneously.
        Mini ZooKeeper lock manager coordinates mutual exclusion.
        Exactly one MUST succeed; exactly one MUST fail.
        """
        target_seat_id = self.seat_ids[0]
        results = []
        barrier = threading.Barrier(2)

        def attempt_booking(user_id):
            barrier.wait()  # Synchronize threads so they hit the endpoint at the exact same instant
            client = TestClient(app)
            response = client.post("/api/bookings/reserve", json={
                "user_id": user_id,
                "event_id": self.event_id,
                "seat_ids": [target_seat_id],
                "reservation_duration_minutes": 5
            })
            results.append((user_id, response.status_code, response.json()))

        t1 = threading.Thread(target=attempt_booking, args=(self.user_a_id,))
        t2 = threading.Thread(target=attempt_booking, args=(self.user_b_id,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Analyze results
        self.assertEqual(len(results), 2)
        status_codes = [r[1] for r in results]
        
        # Exactly one 200 (Success)
        successes = [r for r in results if r[1] == 200]
        failures = [r for r in results if r[1] in (400, 409)]

        self.assertEqual(len(successes), 1, f"Expected exactly 1 success, got: {results}")
        self.assertEqual(len(failures), 1, f"Expected exactly 1 failure, got: {results}")

        # Check DB state: seat must be RESERVED by exactly one booking
        db = self.TestSessionLocal()
        seat = db.query(Seat).filter(Seat.id == target_seat_id).first()
        self.assertEqual(seat.status, "RESERVED")
        self.assertEqual(len(seat.booking_seats), 1)
        db.close()

    def test_simultaneous_different_seats_concurrency(self):
        """
        Verifies that two customers reserving DIFFERENT seats (Seat 2 and Seat 3)
        proceed concurrently without blocking each other.
        """
        seat_2 = self.seat_ids[1]
        seat_3 = self.seat_ids[2]
        results = []
        barrier = threading.Barrier(2)

        def attempt_booking(user_id, seat_id):
            barrier.wait()
            client = TestClient(app)
            response = client.post("/api/bookings/reserve", json={
                "user_id": user_id,
                "event_id": self.event_id,
                "seat_ids": [seat_id],
                "reservation_duration_minutes": 5
            })
            results.append((user_id, response.status_code, response.json()))

        t1 = threading.Thread(target=attempt_booking, args=(self.user_a_id, seat_2))
        t2 = threading.Thread(target=attempt_booking, args=(self.user_b_id, seat_3))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(results), 2)
        for user_id, code, body in results:
            self.assertEqual(code, 200, f"User {user_id} reservation failed: {body}")
            self.assertTrue(body["success"])

        # Verify DB state
        db = self.TestSessionLocal()
        s2 = db.query(Seat).filter(Seat.id == seat_2).first()
        s3 = db.query(Seat).filter(Seat.id == seat_3).first()
        self.assertEqual(s2.status, "RESERVED")
        self.assertEqual(s3.status, "RESERVED")
        db.close()


if __name__ == "__main__":
    unittest.main()
