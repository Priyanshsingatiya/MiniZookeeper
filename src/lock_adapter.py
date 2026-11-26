"""
src/lock_adapter.py
Safe API Adapter Layer for Mini ZooKeeper (Backend A).

Connects the core locking engine (lock_manager) to Backend B and the web API/frontend.
Guarantees:
- Safe data translation (JSON-serializable Python dictionaries).
- Internal OS file descriptors and file objects are NEVER exposed to the frontend or browser.
- Simple, beginner-friendly endpoints for acquire, release, status, and active locks list.
"""

from typing import Optional
from pydantic import BaseModel, Field

# Directory where uploaded shared resource files are kept
import os
from datetime import datetime, timezone, timedelta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "..", "uploaded_resources")
POSTER_DIR = os.path.join(BASE_DIR, "..", "uploaded_resources", "posters")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(POSTER_DIR, exist_ok=True)

# Import the core locking functions from our lock_manager
try:
    from lock_manager import (
        acquire_lock as core_acquire,
        release_lock as core_release,
        get_lock_status as core_status,
        get_all_active_locks as core_list_active,
        validate_resource_name,
        HELD_LOCKS
    )
except ImportError:
    from src.lock_manager import (
        acquire_lock as core_acquire,
        release_lock as core_release,
        get_lock_status as core_status,
        get_all_active_locks as core_list_active,
        validate_resource_name,
        HELD_LOCKS
    )

# Optional FastAPI integration for the web dashboard and REST API
try:
    from fastapi import FastAPI, Query, File, UploadFile, HTTPException, Depends, Security
    from fastapi.responses import FileResponse, Response, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from pathlib import Path
    FASTAPI_AVAILABLE = True
except ImportError:
    FastAPI = None
    StaticFiles = None
    Path = None
    File = None
    UploadFile = None
    HTTPException = None
    Depends = None
    Security = None
    FileResponse = None
    Response = None
    RedirectResponse = None
    FASTAPI_AVAILABLE = False

# Import Database Models and Services (Phase 2 & Phase 4)
try:
    from database import (
        init_db,
        get_db,
        Session,
        SessionLocal,
        User,
        Event,
        Seat,
        Booking,
        BookingSeat,
        Payment,
        create_or_get_user,
        create_event as db_create_event,
        get_event_with_seat_counts,
        create_pending_reservation,
        confirm_booking_payment,
        release_expired_reservations,
        update_event as db_update_event,
        seed_sample_events
    )
except ImportError:
    from src.database import (
        init_db,
        get_db,
        Session,
        SessionLocal,
        User,
        Event,
        Seat,
        Booking,
        BookingSeat,
        Payment,
        create_or_get_user,
        create_event as db_create_event,
        get_event_with_seat_counts,
        create_pending_reservation,
        confirm_booking_payment,
        release_expired_reservations,
        update_event as db_update_event,
        seed_sample_events
    )

# Import Auth & Roles (Phase 3)
try:
    from auth import (
        determine_user_role,
        create_access_token,
        get_current_user,
        require_organizer,
        require_customer,
        get_approved_organizers
    )
except ImportError:
    from src.auth import (
        determine_user_role,
        create_access_token,
        get_current_user,
        require_organizer,
        require_customer,
        get_approved_organizers
    )


# ============================================================================
# Pure Adapter Functions (Can be called directly by Backend B or any script)
# ============================================================================

def api_acquire(resource_name: str, client_id: str, timeout_seconds: float = 0.0) -> dict:
    """
    Adapter function to request a lock.
    Translates input, calls core locking engine, and guarantees safe response dictionary.
    """
    result = core_acquire(
        resource_name=resource_name,
        client_id=client_id,
        timeout_seconds=timeout_seconds
    )
    # Ensure response dictionary only contains safe fields
    return {
        "success": bool(result.get("success", False)),
        "lock_handle": result.get("lock_handle"),
        "request_id": result.get("request_id"),
        "resource_name": result.get("resource_name"),
        "client_id": result.get("client_id"),
        "message": result.get("message", "")
    }


def api_release(resource_name: str, client_id: str, lock_handle: str) -> dict:
    """
    Adapter function to release a lock.
    Verifies ownership and returns a safe response dictionary.
    """
    result = core_release(
        resource_name=resource_name,
        client_id=client_id,
        lock_handle=lock_handle
    )
    return {
        "success": bool(result.get("success", False)),
        "resource_name": resource_name,
        "message": result.get("message", "")
    }


def api_status(resource_name: str) -> dict:
    """
    Adapter function to check resource status.
    Guarantees no internal lock handles or file handles are leaked.
    """
    status_info = core_status(resource_name=resource_name)
    return {
        "resource_name": status_info.get("resource_name"),
        "is_locked": bool(status_info.get("is_locked", False)),
        "owner": status_info.get("owner"),
        "acquired_at": status_info.get("acquired_at"),
        "error": status_info.get("error")
    }


def api_list_locks() -> dict:
    """
    Adapter function to list all active locks.
    Used by dashboard UI to display the current system state.
    """
    active_locks = core_list_active()
    return {
        "active_locks": active_locks,
        "total_count": len(active_locks)
    }


# ============================================================================
# FastAPI Web Application & API Contract with Backend B
# ============================================================================

# Request Models (Beginner-friendly Pydantic schemas)
class AcquireRequest(BaseModel):
    resource_name: str = Field(..., description="The name of the resource to lock (e.g. 'flight_seat_12A')")
    client_id: str = Field(..., description="The identity of the client requesting the lock")
    timeout_seconds: Optional[float] = Field(default=0.0, description="Max seconds to wait (0.0 = non-blocking)")


class ReleaseRequest(BaseModel):
    resource_name: str = Field(..., description="The name of the resource to unlock")
    client_id: str = Field(..., description="The identity of the lock owner")
    lock_handle: str = Field(..., description="The secret lock handle received during acquisition")


class SaveResourceRequest(BaseModel):
    content: str = Field(..., description="Updated text content of the file")
    client_id: str = Field(..., description="Identity of client holding the lock")
    lock_handle: str = Field(..., description="Secret lock handle required to edit")


class CreateUserRequest(BaseModel):
    name: str = Field(..., description="Full name of user")
    email: str = Field(..., description="Email address")
    role: Optional[str] = Field(default="CUSTOMER", description="ORGANIZER or CUSTOMER")
    google_id: Optional[str] = Field(default=None, description="Google OAuth subject ID")


class CreateEventRequest(BaseModel):
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(default="", description="Event description")
    venue: str = Field(..., description="Event venue")
    event_date: str = Field(..., description="Event datetime in ISO format")
    ticket_price: float = Field(..., ge=0, description="Ticket price per seat")
    total_seats: int = Field(..., gt=0, description="Total number of seats")
    poster: Optional[str] = Field(default=None, description="Poster URL or path")
    status: Optional[str] = Field(default="PUBLISHED", description="PUBLISHED or DRAFT")


class CreateReservationRequest(BaseModel):
    user_id: int = Field(..., description="User ID making the booking")
    event_id: int = Field(..., description="Event ID")
    seat_ids: list = Field(..., min_length=1, description="List of seat IDs")
    reservation_duration_minutes: Optional[int] = Field(default=5, description="Minutes to hold seats")


class ConfirmPaymentRequest(BaseModel):
    payment_reference: str = Field(..., description="Payment transaction reference")
    status: Optional[str] = Field(default="SUCCESS", description="SUCCESS or FAILED")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User Google email address")
    name: Optional[str] = Field(default="User", description="Display name")
    google_id: Optional[str] = Field(default=None, description="Google OAuth subject ID")
    google_token: Optional[str] = Field(default=None, description="Google OAuth credential token")


class UpdateEventRequest(BaseModel):
    title: Optional[str] = Field(default=None, description="Event title")
    description: Optional[str] = Field(default=None, description="Event description")
    venue: Optional[str] = Field(default=None, description="Event venue")
    event_date: Optional[str] = Field(default=None, description="Event datetime in ISO format")
    ticket_price: Optional[float] = Field(default=None, ge=0, description="Ticket price per seat")
    status: Optional[str] = Field(default=None, description="PUBLISHED, DRAFT, or UNPUBLISHED")
    poster: Optional[str] = Field(default=None, description="Poster URL or path")


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., description="PUBLISHED, DRAFT, or UNPUBLISHED")


# Create FastAPI application instance
if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Mini ZooKeeper - Distributed Lock Service API",
        description="Backend A Core Locking System API",
        version="1.0.0"
    )

    # Enable CORS for frontend dashboards and web requests
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include Backend B Telemetry & Analytics Router
    try:
        from analysis import analytics_router
    except ImportError:
        try:
            from src.analysis import analytics_router
        except ImportError:
            analytics_router = None

    if analytics_router:
        app.include_router(analytics_router)

    # Mount frontend static directory so pages are accessible directly from FastAPI
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles

    frontend_path = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_path.exists():
        app.mount("/frontend", StaticFiles(directory=str(frontend_path), html=True), name="frontend")



    @app.get("/")
    def root():
        """Root endpoint verifying API health."""
        return {
            "service": "Mini ZooKeeper - Distributed Lock Service",
            "status": "online",
            "version": "1.0.0"
        }

    @app.post("/api/lock/acquire")
    def endpoint_acquire(payload: AcquireRequest):
        """API operation to acquire a lock."""
        return api_acquire(
            resource_name=payload.resource_name,
            client_id=payload.client_id,
            timeout_seconds=payload.timeout_seconds
        )

    @app.post("/api/lock/release")
    def endpoint_release(payload: ReleaseRequest):
        """API operation to release a lock."""
        return api_release(
            resource_name=payload.resource_name,
            client_id=payload.client_id,
            lock_handle=payload.lock_handle
        )

    @app.get("/api/lock/status")
    def endpoint_status(resource_name: str = Query(..., description="Resource name to inspect")):
        """API operation to check lock status of a resource."""
        return api_status(resource_name=resource_name)

    @app.get("/api/locks")
    def endpoint_list_locks():
        """API operation to list all active locks for web dashboard."""
        return api_list_locks()

    # -------------------------------------------------------------------------
    # Uploaded Shared Resource Files Endpoints
    # -------------------------------------------------------------------------

    @app.post("/api/resources/upload")
    async def endpoint_upload_resource(file: UploadFile = File(...)):
        """Uploads a file to act as a shared resource in the lock system."""
        safe_name = os.path.basename(file.filename).strip()
        is_valid, err = validate_resource_name(safe_name)
        if not is_valid:
            safe_name = "".join(c if (c.isalnum() or c in ("_", "-", ".")) else "_" for c in safe_name)
            if not safe_name:
                safe_name = "uploaded_resource.txt"

        dest_path = os.path.join(UPLOAD_DIR, safe_name)
        content_bytes = await file.read()
        with open(dest_path, "wb") as f:
            f.write(content_bytes)

        return {
            "success": True,
            "filename": safe_name,
            "size_bytes": len(content_bytes),
            "message": f"Resource file '{safe_name}' uploaded successfully."
        }

    @app.get("/api/resources")
    def endpoint_list_resources():
        """Lists all uploaded shared resource files and their current lock states."""
        files = []
        if os.path.exists(UPLOAD_DIR):
            for name in sorted(os.listdir(UPLOAD_DIR)):
                full_path = os.path.join(UPLOAD_DIR, name)
                if os.path.isfile(full_path):
                    status = core_status(name)
                    files.append({
                        "filename": name,
                        "size_bytes": os.path.getsize(full_path),
                        "is_locked": status["is_locked"],
                        "owner": status["owner"]
                    })
        return {"resources": files, "count": len(files)}

    @app.get("/api/resources/{filename}/content")
    def endpoint_get_resource_content(filename: str):
        """Reads the content of an uploaded resource file for preview or editing."""
        safe_name = os.path.basename(filename)
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Resource file not found.")

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text_content = f.read()
        except Exception as e:
            text_content = f"Error reading file: {str(e)}"

        status = core_status(safe_name)
        return {
            "filename": safe_name,
            "content": text_content,
            "is_locked": status["is_locked"],
            "owner": status["owner"]
        }

    @app.post("/api/resources/{filename}/save")
    def endpoint_save_resource_content(filename: str, payload: SaveResourceRequest):
        """
        Saves changes to an uploaded resource file.
        SECURITY: Requires that the client holds the active OS lock handle!
        """
        safe_name = os.path.basename(filename)
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Resource file not found.")

        # Check if resource is currently held by this client
        if safe_name not in HELD_LOCKS:
            return {
                "success": False,
                "message": f"Access Denied: Resource '{safe_name}' is not currently locked. You must acquire the lock before modifying it."
            }

        current_lock = HELD_LOCKS[safe_name]
        if current_lock["client_id"] != payload.client_id:
            return {
                "success": False,
                "message": f"Access Denied: Client '{payload.client_id}' does not own the lock on '{safe_name}'."
            }

        if current_lock["lock_handle"] != payload.lock_handle:
            return {
                "success": False,
                "message": "Access Denied: Invalid lock handle provided. Only the lock owner can save changes."
            }

        # Authorized! Write changes to disk safely under lock protection
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(payload.content)
            return {
                "success": True,
                "filename": safe_name,
                "size_bytes": os.path.getsize(file_path),
                "message": f"Changes saved successfully to '{safe_name}' under active mutual exclusion lock!"
            }
        except Exception as err:
            return {
                "success": False,
                "message": f"Failed to save file: {str(err)}"
            }

    # Initialize Database Tables & Auto-Seed Sample Events
    @app.on_event("startup")
    def on_startup():
        try:
            init_db()
            db = SessionLocal()
            try:
                seed_sample_events(db)
            finally:
                db.close()
        except Exception as e:
            print(f"Warning during startup initialization: {e}")

    try:
        init_db()
    except Exception as e:
        print(f"Warning: could not initialize database: {e}")

    # -------------------------------------------------------------------------
    # Authentication & User Management (Phase 3)
    # -------------------------------------------------------------------------

    @app.post("/api/auth/login")
    def endpoint_auth_login(payload: LoginRequest, db: Session = Depends(get_db)):
        """
        Google OAuth / Sign-in authentication endpoint.
        Server verifies email against approved organizer whitelist:
        - Approved email -> ORGANIZER
        - All others -> CUSTOMER
        Issues cryptographically signed JWT session token.
        """
        role = determine_user_role(payload.email)
        user = create_or_get_user(
            db=db,
            email=payload.email,
            name=payload.name or "User",
            google_id=payload.google_id,
            role=role
        )
        token = create_access_token(user_id=user.id, email=user.email, role=user.role)
        redirect_url = "/frontend/organizer.html" if user.role == "ORGANIZER" else "/frontend/events.html"
        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role
            },
            "redirect_url": redirect_url
        }

    @app.get("/api/auth/me")
    def endpoint_auth_me(current_user: User = Depends(get_current_user)):
        """Returns the currently authenticated user profile."""
        return {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "role": current_user.role,
            "google_id": current_user.google_id
        }

    @app.get("/api/auth/organizers")
    def endpoint_auth_organizers():
        """Lists approved organizer emails."""
        return {"approved_organizers": sorted(list(get_approved_organizers()))}

    @app.post("/api/users")
    def endpoint_create_or_get_user(payload: CreateUserRequest, db: Session = Depends(get_db)):
        """Creates or fetches a user with role (ORGANIZER or CUSTOMER)."""
        user = create_or_get_user(
            db=db,
            email=payload.email,
            name=payload.name,
            google_id=payload.google_id,
            role=payload.role
        )
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "google_id": user.google_id
        }

    # -------------------------------------------------------------------------
    # Event Management Endpoints (Phase 4)
    # -------------------------------------------------------------------------

    @app.post("/api/events")
    def endpoint_create_event(payload: CreateEventRequest, db: Session = Depends(get_db)):
        """Creates an event and automatically generates seat rows."""
        try:
            event_dt = datetime.fromisoformat(payload.event_date.replace("Z", "+00:00"))
        except Exception:
            event_dt = datetime.now(timezone.utc) + timedelta(days=7)

        event = db_create_event(
            db=db,
            title=payload.title,
            description=payload.description,
            venue=payload.venue,
            event_date=event_dt,
            ticket_price=payload.ticket_price,
            total_seats=payload.total_seats,
            poster=payload.poster,
            status=payload.status
        )
        return get_event_with_seat_counts(db, event.id)

    @app.get("/api/events")
    def endpoint_list_events(status: Optional[str] = None, db: Session = Depends(get_db)):
        """
        Lists events with seat availability summary.
        If status is None, returns PUBLISHED events by default.
        If status is 'ALL', returns all events regardless of status.
        """
        query = db.query(Event)
        if status and status.upper() != "ALL":
            query = query.filter(Event.status == status.upper())
        elif not status:
            query = query.filter(Event.status == "PUBLISHED")
        events = query.all()
        return [get_event_with_seat_counts(db, e.id) for e in events]

    @app.get("/api/events/{event_id}")
    def endpoint_get_event(event_id: int, db: Session = Depends(get_db)):
        """Gets full event details with real-time seat availability counts."""
        event_data = get_event_with_seat_counts(db, event_id)
        if not event_data:
            raise HTTPException(status_code=404, detail="Event not found.")
        return event_data

    @app.put("/api/events/{event_id}")
    def endpoint_update_event(
        event_id: int,
        payload: UpdateEventRequest,
        db: Session = Depends(get_db)
    ):
        """Updates event metadata (title, venue, price, status, poster)."""
        event_dt = None
        if payload.event_date:
            try:
                event_dt = datetime.fromisoformat(payload.event_date.replace("Z", "+00:00"))
            except Exception:
                pass

        event = db_update_event(
            db=db,
            event_id=event_id,
            title=payload.title,
            description=payload.description,
            venue=payload.venue,
            event_date=event_dt,
            ticket_price=payload.ticket_price,
            status=payload.status,
            poster=payload.poster
        )
        if not event:
            raise HTTPException(status_code=404, detail="Event not found.")
        return get_event_with_seat_counts(db, event_id)

    @app.patch("/api/events/{event_id}/status")
    def endpoint_update_event_status(
        event_id: int,
        payload: UpdateStatusRequest,
        db: Session = Depends(get_db)
    ):
        """Toggles or sets event status (PUBLISHED, DRAFT, UNPUBLISHED)."""
        event = db_update_event(db=db, event_id=event_id, status=payload.status)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found.")
        return get_event_with_seat_counts(db, event_id)

    @app.post("/api/events/{event_id}/poster")
    async def endpoint_upload_poster(
        event_id: int,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
    ):
        """Uploads an event poster image file and associates it with the event."""
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found.")

        ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
        safe_filename = f"event_{event_id}_poster{ext}"
        dest_path = os.path.join(POSTER_DIR, safe_filename)

        content = await file.read()
        with open(dest_path, "wb") as f:
            f.write(content)

        poster_url = f"/api/events/{event_id}/poster"
        event.poster = poster_url
        db.commit()
        db.refresh(event)

        return {
            "success": True,
            "event_id": event_id,
            "poster_url": poster_url,
            "filename": safe_filename,
            "size_bytes": len(content)
        }

    @app.get("/api/events/{event_id}/poster")
    def endpoint_get_poster(event_id: int, db: Session = Depends(get_db)):
        """Serves the poster image for an event."""
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found.")

        # Check local poster file
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            path = os.path.join(POSTER_DIR, f"event_{event_id}_poster{ext}")
            if os.path.exists(path):
                return FileResponse(path)

        if event.poster:
            if event.poster.startswith("http://") or event.poster.startswith("https://"):
                return RedirectResponse(event.poster)

        raise HTTPException(status_code=404, detail="Poster image not found for this event.")

    @app.get("/api/events/{event_id}/seats")
    def endpoint_get_event_seats(event_id: int, db: Session = Depends(get_db)):
        """Gets the seat layout grid for an event (AVAILABLE, RESERVED, SOLD)."""
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found.")
        return [
            {"id": s.id, "seat_number": s.seat_number, "status": s.status}
            for s in event.seats
        ]

    @app.post("/api/events/seed")
    def endpoint_seed_sample_events(db: Session = Depends(get_db)):
        """Seeds realistic sample events into the database."""
        seed_sample_events(db)
        events = db.query(Event).all()
        return {
            "success": True,
            "count": len(events),
            "events": [get_event_with_seat_counts(db, e.id) for e in events]
        }

    # -------------------------------------------------------------------------
    # Seat Booking & Mini ZooKeeper Locking Engine (Phase 5)
    # -------------------------------------------------------------------------

    @app.post("/api/bookings/reserve")
    def endpoint_reserve_seats(payload: CreateReservationRequest, db: Session = Depends(get_db)):
        """
        PHASE 5: Mini ZooKeeper Seat Locking Engine Integration.

        Guarantees:
        - Centralized Mini ZooKeeper OS-level file locking.
        - Deadlock prevention via sorted seat IDs.
        - Lock held ONLY during the short critical section (DB check + state change to RESERVED).
        - Prevents simultaneous double-booking of any seat.
        - Released immediately so subsequent requests see the updated RESERVED state.
        """
        import uuid

        sorted_seat_ids = sorted(payload.seat_ids)
        acquired_locks = []
        lock_client_id = f"cust_{payload.user_id}_{uuid.uuid4().hex[:6]}"

        try:
            # 1. Acquire Mini ZooKeeper lock for each seat in sorted order
            for s_id in sorted_seat_ids:
                resource_name = f"event_{payload.event_id}_seat_{s_id}"
                lock_res = core_acquire(
                    resource_name=resource_name,
                    client_id=lock_client_id,
                    timeout_seconds=1.5
                )
                if not lock_res.get("success"):
                    raise HTTPException(
                        status_code=409,
                        detail=f"Lock contention: Seat ID {s_id} is currently being reserved by another customer. Please choose another seat."
                    )
                acquired_locks.append((resource_name, lock_res.get("lock_handle")))

            # 2. Inside the protected critical section: execute atomic DB reservation
            result = create_pending_reservation(
                db=db,
                user_id=payload.user_id,
                event_id=payload.event_id,
                seat_ids=payload.seat_ids,
                reservation_duration_minutes=payload.reservation_duration_minutes or 5
            )
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("message"))
            return result
        finally:
            # 3. Always release Mini ZooKeeper OS locks immediately after reservation operation
            for res_name, handle in acquired_locks:
                try:
                    core_release(
                        resource_name=res_name,
                        client_id=lock_client_id,
                        lock_handle=handle
                    )
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # Booking Management & Payment Workflow (Phase 6)
    # -------------------------------------------------------------------------

    @app.post("/api/bookings/{booking_id}/pay")
    def endpoint_confirm_payment(booking_id: int, payload: ConfirmPaymentRequest, db: Session = Depends(get_db)):
        """Verifies payment confirmation and permanently marks seats as SOLD."""
        result = confirm_booking_payment(
            db=db,
            booking_id=booking_id,
            payment_reference=payload.payment_reference,
            status=payload.status
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result

    @app.get("/api/bookings/{booking_id}")
    def endpoint_get_booking(booking_id: int, db: Session = Depends(get_db)):
        """Fetches booking record and reserved/sold seat list."""
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found.")
        return {
            "id": booking.id,
            "booking_reference": booking.booking_reference,
            "user_id": booking.user_id,
            "event_id": booking.event_id,
            "event_title": booking.event.title if booking.event else None,
            "total_amount": booking.total_amount,
            "booking_status": booking.booking_status,
            "payment_status": booking.payment_status,
            "seats": [bs.seat.seat_number for bs in booking.booking_seats],
            "created_at": booking.created_at.isoformat(),
            "ticket_qr_url": f"/api/bookings/{booking.id}/ticket-qr" if booking.booking_status == "CONFIRMED" else None
        }

    @app.get("/api/bookings/{booking_id}/ticket-qr")
    def endpoint_booking_ticket_qr(booking_id: int, db: Session = Depends(get_db)):
        """
        Generates and returns a PNG QR code ticket for confirmed bookings.
        Encodes booking reference, event title, venue, seats, holder, and status.
        """
        import io
        import qrcode

        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found.")

        if booking.booking_status != "CONFIRMED":
            raise HTTPException(
                status_code=400,
                detail="Ticket QR code is only generated for confirmed and paid bookings."
            )

        seat_list = ", ".join(bs.seat.seat_number for bs in booking.booking_seats)
        event_title = booking.event.title if booking.event else "Event"
        user_name = booking.user.name if booking.user else "Customer"

        qr_text = (
            f"MINIZOOKEEPER TICKET\n"
            f"Ref: {booking.booking_reference}\n"
            f"Event: {event_title}\n"
            f"Venue: {booking.event.venue if booking.event else 'N/A'}\n"
            f"Seats: {seat_list}\n"
            f"Holder: {user_name}\n"
            f"Total Paid: ${booking.total_amount:.2f}\n"
            f"Status: {booking.payment_status}"
        )

        qr_img = qrcode.make(qr_text)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")

    @app.get("/api/users/{user_id}/bookings")
    def endpoint_user_bookings(user_id: int, db: Session = Depends(get_db)):
        """Fetches booking history for a specific customer."""
        bookings = (
            db.query(Booking)
            .filter(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
            .all()
        )
        return [
            {
                "id": b.id,
                "booking_reference": b.booking_reference,
                "event_id": b.event_id,
                "event_title": b.event.title if b.event else None,
                "venue": b.event.venue if b.event else None,
                "event_date": b.event.event_date.isoformat() if b.event else None,
                "poster": b.event.poster if b.event else None,
                "total_amount": b.total_amount,
                "booking_status": b.booking_status,
                "payment_status": b.payment_status,
                "seats": [bs.seat.seat_number for bs in b.booking_seats],
                "created_at": b.created_at.isoformat(),
                "ticket_qr_url": f"/api/bookings/{b.id}/ticket-qr" if b.booking_status == "CONFIRMED" else None
            }
            for b in bookings
        ]

    @app.get("/api/organizer/analytics")
    def endpoint_organizer_analytics(db: Session = Depends(get_db)):
        """Provides organizer dashboard metrics, sales, revenue, and active locks."""
        total_events = db.query(Event).count()
        total_seats = db.query(Seat).count()
        sold_seats = db.query(Seat).filter(Seat.status == "SOLD").count()
        reserved_seats = db.query(Seat).filter(Seat.status == "RESERVED").count()
        available_seats = db.query(Seat).filter(Seat.status == "AVAILABLE").count()

        confirmed_bookings = db.query(Booking).filter(Booking.booking_status == "CONFIRMED").all()
        total_revenue = round(sum(b.total_amount for b in confirmed_bookings), 2)

        active_locks_info = api_list_locks()

        recent_bookings = (
            db.query(Booking)
            .order_by(Booking.created_at.desc())
            .limit(10)
            .all()
        )

        return {
            "total_events": total_events,
            "total_seats": total_seats,
            "sold_seats": sold_seats,
            "reserved_seats": reserved_seats,
            "available_seats": available_seats,
            "occupancy_rate_percent": round((sold_seats / total_seats * 100), 1) if total_seats > 0 else 0.0,
            "total_revenue": total_revenue,
            "confirmed_bookings_count": len(confirmed_bookings),
            "active_locks_count": active_locks_info["total_count"],
            "active_locks": active_locks_info["active_locks"],
            "recent_bookings": [
                {
                    "id": b.id,
                    "booking_reference": b.booking_reference,
                    "event_title": b.event.title if b.event else None,
                    "user_name": b.user.name if b.user else None,
                    "user_email": b.user.email if b.user else None,
                    "total_amount": b.total_amount,
                    "booking_status": b.booking_status,
                    "payment_status": b.payment_status,
                    "seats": [bs.seat.seat_number for bs in b.booking_seats],
                    "created_at": b.created_at.isoformat()
                }
                for b in recent_bookings
            ]
        }

    @app.post("/api/bookings/cleanup-expired")
    def endpoint_cleanup_expired(db: Session = Depends(get_db)):
        """Housekeeping endpoint to release seats for expired reservations."""
        count = release_expired_reservations(db)
        return {"success": True, "released_seats_count": count}

    # Mount Backend B's analytics & telemetry router into the unified FastAPI app
    try:
        from analysis import analytics_router
        if analytics_router:
            app.include_router(analytics_router)
    except ImportError:
        try:
            from src.analysis import analytics_router
            if analytics_router:
                app.include_router(analytics_router)
        except ImportError:
            pass

    # Mount frontend static files directory
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    app = None
