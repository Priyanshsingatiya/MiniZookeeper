"""
tests/test_auth.py
Verification tests for Phase 3: Google Auth & Role-Based Authorization.
"""

import unittest
from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base, User, get_db, create_or_get_user
from src.auth import (
    determine_user_role,
    create_access_token,
    decode_access_token,
    get_current_user,
    require_organizer,
    require_customer
)


class TestAuthPhase3(unittest.TestCase):

    def setUp(self):
        # In-memory test DB with check_same_thread disabled for Starlette async threads
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, echo=False)
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Dummy FastAPI app to test role dependencies
        self.app = FastAPI()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        self.app.dependency_overrides[get_db] = override_get_db

        @self.app.get("/test/public")
        def route_public():
            return {"status": "ok"}

        @self.app.get("/test/customer-only")
        def route_customer(user: User = Depends(require_customer)):
            return {"user": user.email, "role": user.role}

        @self.app.get("/test/organizer-only")
        def route_organizer(user: User = Depends(require_organizer)):
            return {"user": user.email, "role": user.role}

        self.client = TestClient(self.app)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_role_determination(self):
        """Verify role is strictly assigned based on approved whitelist or full name 'zookeeper'."""
        self.assertEqual(determine_user_role("kapilpoddar99999@gmail.com"), "ORGANIZER")
        self.assertEqual(determine_user_role("admin@zookeeper.com"), "ORGANIZER")
        self.assertEqual(determine_user_role("random.customer@gmail.com"), "CUSTOMER")
        self.assertEqual(determine_user_role("student@college.edu"), "CUSTOMER")
        # Name or password "zookeeper" grants ORGANIZER regardless of email domain
        self.assertEqual(determine_user_role("anyone@gmail.com", name="zookeeper"), "ORGANIZER")
        self.assertEqual(determine_user_role("test@college.edu", name="ZooKeeper"), "ORGANIZER")
        self.assertEqual(determine_user_role("student@test.com", name="ZOOKEEPER"), "ORGANIZER")
        self.assertEqual(determine_user_role("anyone@gmail.com", password="zookeeper"), "ORGANIZER")
        self.assertEqual(determine_user_role("guest@gmail.com", password="ZOOKEEPER"), "ORGANIZER")
        self.assertEqual(determine_user_role("customer@test.com", name="Alice Customer", password="secret"), "CUSTOMER")

    def test_token_creation_and_validation(self):
        """Verify valid JWT tokens decode and invalid tokens reject."""
        token = create_access_token(user_id=42, email="alice@test.com", role="CUSTOMER")
        self.assertIsInstance(token, str)

        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["email"], "alice@test.com")
        self.assertEqual(payload["role"], "CUSTOMER")

    def test_unauthenticated_request_blocked(self):
        """Verify endpoints requiring login return 401 Unauthorized without token."""
        resp = self.client.get("/test/customer-only")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Authentication required", resp.json()["detail"])

    def test_customer_allowed_on_customer_endpoints(self):
        """Verify customer can access customer-allowed routes."""
        customer = create_or_get_user(self.db, "bob@customer.com", "Bob Customer", role="CUSTOMER")
        token = create_access_token(customer.id, customer.email, customer.role)

        headers = {"Authorization": f"Bearer {token}"}
        resp = self.client.get("/test/customer-only", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["role"], "CUSTOMER")

    def test_customer_forbidden_from_organizer_endpoints(self):
        """CRITICAL SECURITY TEST: Customer attempting to access organizer endpoint must get 403 Forbidden."""
        customer = create_or_get_user(self.db, "eve@customer.com", "Eve Hacker", role="CUSTOMER")
        token = create_access_token(customer.id, customer.email, customer.role)

        headers = {"Authorization": f"Bearer {token}"}
        resp = self.client.get("/test/organizer-only", headers=headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Organizer privileges required", resp.json()["detail"])

    def test_organizer_allowed_on_organizer_endpoints(self):
        """Verify approved organizer is granted access."""
        organizer = create_or_get_user(self.db, "kapilpoddar99999@gmail.com", "Kapil Organizer", role="ORGANIZER")
        token = create_access_token(organizer.id, organizer.email, organizer.role)

        headers = {"Authorization": f"Bearer {token}"}
        resp = self.client.get("/test/organizer-only", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["role"], "ORGANIZER")


if __name__ == "__main__":
    unittest.main()
