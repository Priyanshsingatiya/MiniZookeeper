"""
tests/test_e2e_booking_platform.py
Phase 9: Comprehensive End-to-End Integration Test for the Entire Event Ticket Booking Platform.

Workflow tested:
1. Approved Organizer logs in -> acquires ORGANIZER JWT session.
2. Organizer creates a new event ("AI Breakthrough Summit 2026") with 10 seats.
3. Organizer uploads an event poster.
4. Customer 1 logs in -> acquires CUSTOMER JWT session.
5. Customer 1 views published events catalog and seats layout.
6. Customer 1 locks and reserves Seat A1.
7. Customer 2 logs in and attempts to reserve Seat A1 simultaneously -> REJECTED.
8. Customer 2 reserves Seat A2 -> SUCCEEDS.
9. Customer 1 proceeds to checkout and completes payment -> Seat A1 marked SOLD.
10. Customer 1 accesses QR Code ticket -> verified PNG image.
11. Expired reservation cleanup is executed -> Seat A2 is returned to AVAILABLE.
12. Organizer checks live dashboard analytics -> verifies revenue, sold count, and available seats.
"""

import unittest
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from database import Base, get_db, BookingSeat
from lock_adapter import app


class TestE2EBookingPlatform(unittest.TestCase):
    def setUp(self):
        self.db_path = f"/tmp/test_e2e_{uuid.uuid4().hex}.db"
        self.test_engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False}
        )
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

    def tearDown(self):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.test_engine)
        self.test_engine.dispose()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    def test_complete_platform_lifecycle(self):
        # 1. Organizer Login
        org_login_res = self.client.post("/api/auth/login", json={
            "email": "kapilpoddar99999@gmail.com",
            "name": "Kapil Poddar (Organizer)"
        })
        self.assertEqual(org_login_res.status_code, 200)
        org_data = org_login_res.json()
        self.assertEqual(org_data["user"]["role"], "ORGANIZER")
        org_token = org_data["access_token"]
        org_headers = {"Authorization": f"Bearer {org_token}"}

        # 2. Organizer Creates an Event
        create_event_res = self.client.post("/api/events", json={
            "title": "AI Breakthrough Summit 2026",
            "description": "Annual deep learning and robotics keynote.",
            "venue": "San Jose Convention Center",
            "event_date": (datetime.now(timezone.utc) + timedelta(days=20)).isoformat(),
            "ticket_price": 250.00,
            "total_seats": 10,
            "status": "PUBLISHED"
        }, headers=org_headers)
        self.assertEqual(create_event_res.status_code, 200)
        event_data = create_event_res.json()
        event_id = event_data["id"]
        self.assertEqual(event_data["available_seats"], 10)
        self.assertEqual(event_data["sold_seats"], 0)

        # 3. Organizer Uploads Event Poster
        fake_poster = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        upload_res = self.client.post(
            f"/api/events/{event_id}/poster",
            files={"file": ("poster.png", fake_poster, "image/png")},
            headers=org_headers
        )
        self.assertEqual(upload_res.status_code, 200)
        self.assertTrue(upload_res.json()["success"])

        # 4. Customer 1 Logs In
        c1_login = self.client.post("/api/auth/login", json={
            "email": "customer1@college.edu",
            "name": "Customer One"
        })
        self.assertEqual(c1_login.status_code, 200)
        c1_data = c1_login.json()
        self.assertEqual(c1_data["user"]["role"], "CUSTOMER")
        c1_id = c1_data["user"]["id"]
        c1_headers = {"Authorization": f"Bearer {c1_data['access_token']}"}

        # 5. Customer 1 fetches seats layout
        seats_res = self.client.get(f"/api/events/{event_id}/seats")
        self.assertEqual(seats_res.status_code, 200)
        seats = seats_res.json()
        self.assertEqual(len(seats), 10)
        seat_a1 = seats[0]["id"]
        seat_a2 = seats[1]["id"]

        # 6. Customer 1 Reserves Seat A1
        c1_reserve = self.client.post("/api/bookings/reserve", json={
            "user_id": c1_id,
            "event_id": event_id,
            "seat_ids": [seat_a1],
            "reservation_duration_minutes": 5
        }, headers=c1_headers)
        self.assertEqual(c1_reserve.status_code, 200)
        booking1_id = c1_reserve.json()["booking_id"]
        self.assertEqual(c1_reserve.json()["total_amount"], 250.00)

        # 7. Customer 2 Logs in and attempts to reserve the exact same Seat A1 -> Rejected
        c2_login = self.client.post("/api/auth/login", json={
            "email": "customer2@college.edu",
            "name": "Customer Two"
        })
        c2_id = c2_login.json()["user"]["id"]
        c2_headers = {"Authorization": f"Bearer {c2_login.json()['access_token']}"}

        c2_conflict = self.client.post("/api/bookings/reserve", json={
            "user_id": c2_id,
            "event_id": event_id,
            "seat_ids": [seat_a1],
            "reservation_duration_minutes": 5
        }, headers=c2_headers)
        self.assertIn(c2_conflict.status_code, (400, 409))

        # 8. Customer 2 Reserves Seat A2 instead -> Succeeds
        c2_reserve = self.client.post("/api/bookings/reserve", json={
            "user_id": c2_id,
            "event_id": event_id,
            "seat_ids": [seat_a2],
            "reservation_duration_minutes": 5
        }, headers=c2_headers)
        self.assertEqual(c2_reserve.status_code, 200)
        booking2_id = c2_reserve.json()["booking_id"]

        # 9. Customer 1 Pays for Booking 1 -> Marked SOLD
        pay_res = self.client.post(f"/api/bookings/{booking1_id}/pay", json={
            "payment_reference": "PAY_RZP_SUCCESS_CUST1",
            "status": "SUCCESS"
        }, headers=c1_headers)
        self.assertEqual(pay_res.status_code, 200)
        self.assertEqual(pay_res.json()["booking_status"], "CONFIRMED")

        # 10. Customer 1 accesses QR Code Ticket
        qr_res = self.client.get(f"/api/bookings/{booking1_id}/ticket-qr")
        self.assertEqual(qr_res.status_code, 200)
        self.assertEqual(qr_res.headers["content-type"], "image/png")
        self.assertTrue(len(qr_res.content) > 100)

        # 11. Customer 2's reservation expires (simulate time passage)
        db = self.TestSessionLocal()
        b2_seat = db.query(BookingSeat).filter(BookingSeat.booking_id == booking2_id).first()
        b2_seat.reserved_until = datetime.now(timezone.utc) - timedelta(minutes=10)
        db.commit()
        db.close()

        cleanup_res = self.client.post("/api/bookings/cleanup-expired")
        self.assertEqual(cleanup_res.status_code, 200)
        self.assertGreaterEqual(cleanup_res.json()["released_seats_count"], 1)

        # 12. Organizer checks Live Analytics
        analytics_res = self.client.get("/api/organizer/analytics", headers=org_headers)
        self.assertEqual(analytics_res.status_code, 200)
        analytics = analytics_res.json()
        self.assertEqual(analytics["sold_seats"], 1)
        self.assertEqual(analytics["total_revenue"], 250.00)
        self.assertEqual(analytics["confirmed_bookings_count"], 1)
        self.assertEqual(analytics["reserved_seats"], 0)  # Expired hold released


if __name__ == "__main__":
    unittest.main()
