"""
tests/test_database.py
Comprehensive tests for Phase 2: Database entities, constraints, and transactions.
"""

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import (
    Base,
    User,
    Event,
    Seat,
    Booking,
    BookingSeat,
    Payment,
    create_or_get_user,
    create_event,
    get_event_with_seat_counts,
    create_pending_reservation,
    confirm_booking_payment,
    release_expired_reservations
)


class TestDatabasePhase2(unittest.TestCase):

    def setUp(self):
        # Use an in-memory SQLite database for test isolation
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_user_creation_and_roles(self):
        """Verify user creation with roles (CUSTOMER vs ORGANIZER)."""
        customer = create_or_get_user(self.db, "alice@example.com", "Alice Smith", role="CUSTOMER")
        self.assertEqual(customer.role, "CUSTOMER")
        self.assertEqual(customer.email, "alice@example.com")

        organizer = create_or_get_user(self.db, "admin@example.com", "Admin Organizer", role="ORGANIZER")
        self.assertEqual(organizer.role, "ORGANIZER")

        # Idempotent retrieval
        same_customer = create_or_get_user(self.db, "alice@example.com", "Alice New Name")
        self.assertEqual(same_customer.id, customer.id)

    def test_event_and_seat_generation(self):
        """Verify event creation automatically seeds seats with correct statuses."""
        event_date = datetime.now(timezone.utc) + timedelta(days=10)
        event = create_event(
            db=self.db,
            title="Google Tech Summit",
            description="Annual tech conference",
            venue="Grand Hall",
            event_date=event_date,
            ticket_price=150.0,
            total_seats=20,
            status="PUBLISHED"
        )

        self.assertEqual(event.title, "Google Tech Summit")
        self.assertEqual(len(event.seats), 20)
        self.assertTrue(all(s.status == "AVAILABLE" for s in event.seats))

        # Check breakdown
        breakdown = get_event_with_seat_counts(self.db, event.id)
        self.assertEqual(breakdown["total_seats"], 20)
        self.assertEqual(breakdown["available_seats"], 20)
        self.assertEqual(breakdown["reserved_seats"], 0)
        self.assertEqual(breakdown["sold_seats"], 0)

    def test_negative_price_and_seats_rejected(self):
        """Verify invalid price or zero seats raise validation errors."""
        event_date = datetime.now(timezone.utc) + timedelta(days=5)
        with self.assertRaises(ValueError):
            create_event(self.db, "Bad Event", "", "Hall", event_date, ticket_price=-50.0, total_seats=10)

        with self.assertRaises(ValueError):
            create_event(self.db, "Bad Event", "", "Hall", event_date, ticket_price=50.0, total_seats=0)

    def test_pending_reservation_and_authoritative_price(self):
        """Verify pending reservation transitions seats to RESERVED and uses DB ticket price."""
        user = create_or_get_user(self.db, "bob@example.com", "Bob Jones")
        event = create_event(
            self.db,
            title="AI Expo",
            description="AI Expo",
            venue="Tech Center",
            event_date=datetime.now(timezone.utc) + timedelta(days=3),
            ticket_price=75.50,
            total_seats=10
        )

        seat_ids = [event.seats[0].id, event.seats[1].id]
        res = create_pending_reservation(self.db, user.id, event.id, seat_ids, reservation_duration_minutes=5)

        self.assertTrue(res["success"])
        self.assertEqual(res["total_amount"], 151.0)  # 75.50 * 2 = 151.0
        self.assertEqual(len(res["seats"]), 2)

        # Verify seats in DB are now RESERVED
        s1 = self.db.query(Seat).filter(Seat.id == seat_ids[0]).first()
        s2 = self.db.query(Seat).filter(Seat.id == seat_ids[1]).first()
        self.assertEqual(s1.status, "RESERVED")
        self.assertEqual(s2.status, "RESERVED")

    def test_prevent_double_reservation(self):
        """Verify a second user cannot reserve an already reserved seat."""
        user1 = create_or_get_user(self.db, "user1@example.com", "User One")
        user2 = create_or_get_user(self.db, "user2@example.com", "User Two")

        event = create_event(
            self.db,
            title="Music Fest",
            description="",
            venue="Arena",
            event_date=datetime.now(timezone.utc) + timedelta(days=2),
            ticket_price=50.0,
            total_seats=5
        )

        target_seat_id = [event.seats[0].id]

        # User 1 reserves seat A1
        res1 = create_pending_reservation(self.db, user1.id, event.id, target_seat_id)
        self.assertTrue(res1["success"])

        # User 2 tries to reserve seat A1 -> Must be rejected!
        res2 = create_pending_reservation(self.db, user2.id, event.id, target_seat_id)
        self.assertFalse(res2["success"])
        self.assertIn("already reserved", res2["message"].lower())

    def test_payment_confirmation_transitions_to_sold(self):
        """Verify payment success permanently marks seats as SOLD."""
        user = create_or_get_user(self.db, "customer@example.com", "Customer")
        event = create_event(
            self.db, "Concert", "", "Stadium",
            datetime.now(timezone.utc) + timedelta(days=1),
            100.0, 5
        )

        res = create_pending_reservation(self.db, user.id, event.id, [event.seats[0].id])
        self.assertTrue(res["success"])
        booking_id = res["booking_id"]

        # Confirm payment
        pay_res = confirm_booking_payment(self.db, booking_id, "PAY_REF_9999", status="SUCCESS")
        self.assertTrue(pay_res["success"])
        self.assertEqual(pay_res["booking_status"], "CONFIRMED")
        self.assertEqual(pay_res["payment_status"], "SUCCESS")

        # Seat is now SOLD
        seat = self.db.query(Seat).filter(Seat.id == event.seats[0].id).first()
        self.assertEqual(seat.status, "SOLD")

    def test_payment_failure_releases_seats(self):
        """Verify payment failure transitions reserved seats back to AVAILABLE."""
        user = create_or_get_user(self.db, "fail_user@example.com", "Fail User")
        event = create_event(
            self.db, "Show", "", "Theater",
            datetime.now(timezone.utc) + timedelta(days=1),
            60.0, 5
        )

        res = create_pending_reservation(self.db, user.id, event.id, [event.seats[0].id])
        booking_id = res["booking_id"]

        # Payment fails
        pay_res = confirm_booking_payment(self.db, booking_id, "PAY_FAIL_123", status="FAILED")
        self.assertTrue(pay_res["success"])
        self.assertEqual(pay_res["booking_status"], "CANCELLED")

        # Seat is back to AVAILABLE!
        seat = self.db.query(Seat).filter(Seat.id == event.seats[0].id).first()
        self.assertEqual(seat.status, "AVAILABLE")

    def test_expired_reservation_cannot_be_paid(self):
        """Verify expired reservations cannot be paid and get cleaned up."""
        user = create_or_get_user(self.db, "slow_user@example.com", "Slow User")
        event = create_event(
            self.db, "Workshop", "", "Room 101",
            datetime.now(timezone.utc) + timedelta(days=1),
            40.0, 5
        )

        # Create reservation with negative minutes (already expired)
        res = create_pending_reservation(self.db, user.id, event.id, [event.seats[0].id], reservation_duration_minutes=-1)
        booking_id = res["booking_id"]

        # Attempt to confirm payment on expired reservation -> Rejected!
        pay_res = confirm_booking_payment(self.db, booking_id, "PAY_LATE_123", status="SUCCESS")
        self.assertFalse(pay_res["success"])
        self.assertIn("expired", pay_res["message"].lower())

        # Seat is freed back to AVAILABLE
        seat = self.db.query(Seat).filter(Seat.id == event.seats[0].id).first()
        self.assertEqual(seat.status, "AVAILABLE")


if __name__ == "__main__":
    unittest.main()
