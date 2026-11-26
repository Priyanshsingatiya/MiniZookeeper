"""
tests/test_events_phase4.py
Unit and Integration Tests for Phase 4: Event Management & Sample Events.
"""

import unittest
import os
import sys
import io
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from database import Base, get_db
from lock_adapter import app


class TestEventsPhase4(unittest.TestCase):
    def setUp(self):
        # Create a temp file SQLite database with WAL mode for isolated testing
        self.db_path = f"/tmp/test_phase4_{uuid.uuid4().hex}.db"
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

    def test_auth_login_roles(self):
        """Tests that approved organizer emails receive ORGANIZER role and others receive CUSTOMER."""
        # Organizer login
        res_org = self.client.post("/api/auth/login", json={
            "email": "kapilpoddar99999@gmail.com",
            "name": "Kapil Poddar"
        })
        self.assertEqual(res_org.status_code, 200)
        data_org = res_org.json()
        self.assertTrue(data_org["success"])
        self.assertEqual(data_org["user"]["role"], "ORGANIZER")
        self.assertIn("organizer.html", data_org["redirect_url"])
        self.assertTrue(len(data_org["access_token"]) > 20)

        # Customer login
        res_cust = self.client.post("/api/auth/login", json={
            "email": "student_jane@college.edu",
            "name": "Jane Student"
        })
        self.assertEqual(res_cust.status_code, 200)
        data_cust = res_cust.json()
        self.assertTrue(data_cust["success"])
        self.assertEqual(data_cust["user"]["role"], "CUSTOMER")
        self.assertIn("events.html", data_cust["redirect_url"])

    def test_seed_sample_events(self):
        """Tests seeding sample events and retrieving published events."""
        res = self.client.post("/api/events/seed")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 4)

        # Verify listing published events
        list_res = self.client.get("/api/events")
        self.assertEqual(list_res.status_code, 200)
        events = list_res.json()
        self.assertEqual(len(events), 4)

        first_event = events[0]
        self.assertEqual(first_event["title"], "Google Developer Conference 2026")
        self.assertEqual(first_event["total_seats"], 30)
        self.assertEqual(first_event["available_seats"], 30)

    def test_create_and_update_event(self):
        """Tests creating a new event, editing its details, and toggling status."""
        event_payload = {
            "title": "Quantum Computing Symposium",
            "description": "Hardware and algorithm breakthroughs.",
            "venue": "MIT Kresge Auditorium, Cambridge",
            "event_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "ticket_price": 149.50,
            "total_seats": 20,
            "status": "DRAFT"
        }
        create_res = self.client.post("/api/events", json=event_payload)
        self.assertEqual(create_res.status_code, 200)
        event = create_res.json()
        event_id = event["id"]
        self.assertEqual(event["status"], "DRAFT")
        self.assertEqual(event["total_seats"], 20)

        # Update event metadata
        update_res = self.client.put(f"/api/events/{event_id}", json={
            "title": "Advanced Quantum Computing Symposium 2026",
            "ticket_price": 175.00
        })
        self.assertEqual(update_res.status_code, 200)
        updated_event = update_res.json()
        self.assertEqual(updated_event["title"], "Advanced Quantum Computing Symposium 2026")
        self.assertEqual(updated_event["ticket_price"], 175.00)

        # Publish event
        status_res = self.client.patch(f"/api/events/{event_id}/status", json={"status": "PUBLISHED"})
        self.assertEqual(status_res.status_code, 200)
        self.assertEqual(status_res.json()["status"], "PUBLISHED")

    def test_poster_upload_and_retrieval(self):
        """Tests uploading an event poster and retrieving it."""
        # Create an event first
        event_res = self.client.post("/api/events", json={
            "title": "Poster Test Event",
            "venue": "Hall A",
            "event_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
            "ticket_price": 50.0,
            "total_seats": 10,
            "status": "PUBLISHED"
        })
        event_id = event_res.json()["id"]

        # Upload poster
        fake_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        upload_res = self.client.post(
            f"/api/events/{event_id}/poster",
            files={"file": ("sample_poster.png", fake_image_bytes, "image/png")}
        )
        self.assertEqual(upload_res.status_code, 200)
        upload_data = upload_res.json()
        self.assertTrue(upload_data["success"])
        self.assertIn("poster", upload_data["poster_url"])

        # Retrieve poster
        get_poster_res = self.client.get(f"/api/events/{event_id}/poster")
        self.assertEqual(get_poster_res.status_code, 200)
        self.assertEqual(get_poster_res.content, fake_image_bytes)


if __name__ == "__main__":
    unittest.main()
