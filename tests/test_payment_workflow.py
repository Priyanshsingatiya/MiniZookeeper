"""
tests/test_payment_workflow.py
Phase 6: Verification of Booking Confirmation, Payment Verification, QR Code Ticket Generation,
and Organizer Analytics.
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

from database import Base, get_db, Event, Seat, User
from lock_adapter import app


class TestPaymentWorkflow(unittest.TestCase):
    def setUp(self):
        self.db_path = f"/tmp/test_payment_{uuid.uuid4().hex}.db"
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

        # Seed data
        db = self.TestSessionLocal()
        user = User(name="Alice Walker", email="alice@example.com", role="CUSTOMER")
        db.add(user)
        db.commit()

        event = Event(
            title="Global AI Summit 2026",
            venue="Grand Theatre",
            event_date=datetime.now(timezone.utc) + timedelta(days=15),
            ticket_price=120.0,
            total_seats=10,
            status="PUBLISHED"
        )
        db.add(event)
        db.flush()

        self.seats = []
        for i in range(1, 11):
            s = Seat(event_id=event.id, seat_number=f"S{i}", status="AVAILABLE")
            db.add(s)
            db.flush()
            self.seats.append(s.id)

        db.commit()
        self.user_id = user.id
        self.event_id = event.id
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

    def test_complete_booking_payment_and_qr_flow(self):
        """Tests reserving seats, verifying payment, and retrieving QR code ticket."""
        # 1. Reserve seats
        reserve_res = self.client.post("/api/bookings/reserve", json={
            "user_id": self.user_id,
            "event_id": self.event_id,
            "seat_ids": [self.seats[0], self.seats[1]],
            "reservation_duration_minutes": 5
        })
        self.assertEqual(reserve_res.status_code, 200)
        res_data = reserve_res.json()
        self.assertTrue(res_data["success"])
        booking_id = res_data["booking_id"]
        self.assertEqual(res_data["total_amount"], 240.0)

        # 2. Before payment, QR code should return 400
        qr_pre = self.client.get(f"/api/bookings/{booking_id}/ticket-qr")
        self.assertEqual(qr_pre.status_code, 400)

        # 3. Pay for booking
        pay_res = self.client.post(f"/api/bookings/{booking_id}/pay", json={
            "payment_reference": "PAY_RZP_TEST_998877",
            "status": "SUCCESS"
        })
        self.assertEqual(pay_res.status_code, 200)
        pay_data = pay_res.json()
        self.assertTrue(pay_data["success"])
        self.assertEqual(pay_data["booking_status"], "CONFIRMED")
        self.assertEqual(pay_data["payment_status"], "SUCCESS")

        # 4. Seats must now be marked SOLD in database
        db = self.TestSessionLocal()
        s1 = db.query(Seat).filter(Seat.id == self.seats[0]).first()
        s2 = db.query(Seat).filter(Seat.id == self.seats[1]).first()
        self.assertEqual(s1.status, "SOLD")
        self.assertEqual(s2.status, "SOLD")
        db.close()

        # 5. After confirmation, QR code must return image/png
        qr_post = self.client.get(f"/api/bookings/{booking_id}/ticket-qr")
        self.assertEqual(qr_post.status_code, 200)
        self.assertEqual(qr_post.headers["content-type"], "image/png")
        self.assertTrue(len(qr_post.content) > 100)

        # 6. Customer booking history
        history_res = self.client.get(f"/api/users/{self.user_id}/bookings")
        self.assertEqual(history_res.status_code, 200)
        history = history_res.json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["booking_status"], "CONFIRMED")
        self.assertIn("ticket-qr", history[0]["ticket_qr_url"])

        # 7. Organizer analytics
        analytics_res = self.client.get("/api/organizer/analytics")
        self.assertEqual(analytics_res.status_code, 200)
        analytics = analytics_res.json()
        self.assertEqual(analytics["sold_seats"], 2)
        self.assertEqual(analytics["total_revenue"], 240.0)
        self.assertEqual(analytics["confirmed_bookings_count"], 1)


if __name__ == "__main__":
    unittest.main()
