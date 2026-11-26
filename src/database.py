"""
src/database.py
Database layer for Mini ZooKeeper — Event Ticket Booking Platform (Phase 2).

Entities:
- Users (ORGANIZER, CUSTOMER)
- Events (Dates, Venue, Price, Total Seats, Status)
- Seats (AVAILABLE, RESERVED, SOLD)
- Bookings (PENDING, CONFIRMED, CANCELLED, EXPIRED)
- BookingSeats (Mapping of seats in a booking with reservation timeouts)
- Payments (Payment verification, amount, status)

Guarantees:
- ACID Transactions
- Foreign key constraints enabled (including SQLite PRAGMA foreign_keys=ON)
- High concurrency with Write-Ahead Logging (WAL mode)
- Price calculation computed from DB authority (never trusted from frontend)
- Prevention of duplicate bookings and negative availability
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Text,
    event as sa_event
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# Base directory & default database path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Default to SQLite with WAL mode for zero-ops local concurrency,
# or use PostgreSQL if DATABASE_URL environment variable is provided.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'minizookeeper.db'}")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False
)

# Enable Foreign Keys and WAL Mode on SQLite for high-throughput concurrency
if DATABASE_URL.startswith("sqlite"):
    @sa_event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============================================================================
# Database Models
# ============================================================================

class User(Base):
    """Represents an application user (ORGANIZER or CUSTOMER)."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    google_id = Column(String(100), unique=True, index=True, nullable=True)
    role = Column(String(20), default="CUSTOMER", nullable=False)  # "ORGANIZER" or "CUSTOMER"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    bookings = relationship("Booking", back_populates="user", cascade="all, delete-orphan")


class Event(Base):
    """Represents an event created by an organizer."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    poster = Column(String(255), nullable=True)  # URL or relative file path to poster
    venue = Column(String(200), nullable=False)
    event_date = Column(DateTime, nullable=False)
    ticket_price = Column(Float, nullable=False)  # Authoritative ticket price
    total_seats = Column(Integer, nullable=False)
    status = Column(String(20), default="DRAFT", nullable=False)  # "DRAFT", "PUBLISHED", "CANCELLED"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    seats = relationship("Seat", back_populates="event", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="event", cascade="all, delete-orphan")


class Seat(Base):
    """
    Represents an individual seat for an event.
    Status can be: AVAILABLE, RESERVED, SOLD.
    """
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_number = Column(String(20), nullable=False)  # e.g. "A1", "A2", "B1"
    status = Column(String(20), default="AVAILABLE", nullable=False)  # "AVAILABLE", "RESERVED", "SOLD"

    event = relationship("Event", back_populates="seats")
    booking_seats = relationship("BookingSeat", back_populates="seat", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("event_id", "seat_number", name="uq_event_seat_number"),
    )


class Booking(Base):
    """Represents a customer ticket booking reservation or purchase."""
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_reference = Column(String(32), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    booking_status = Column(String(20), default="PENDING", nullable=False)  # "PENDING", "CONFIRMED", "CANCELLED", "EXPIRED"
    payment_status = Column(String(20), default="PENDING", nullable=False)  # "PENDING", "SUCCESS", "FAILED"
    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="bookings")
    event = relationship("Event", back_populates="bookings")
    booking_seats = relationship("BookingSeat", back_populates="booking", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")


class BookingSeat(Base):
    """Mapping between a Booking and an individual reserved/sold Seat."""
    __tablename__ = "booking_seats"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_id = Column(Integer, ForeignKey("seats.id", ondelete="CASCADE"), nullable=False, index=True)
    reserved_until = Column(DateTime, nullable=True)

    booking = relationship("Booking", back_populates="booking_seats")
    seat = relationship("Seat", back_populates="booking_seats")

    __table_args__ = (
        UniqueConstraint("booking_id", "seat_id", name="uq_booking_seat_item"),
    )


class Payment(Base):
    """Records payment transactions for a booking."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    payment_reference = Column(String(64), unique=True, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)  # "PENDING", "SUCCESS", "FAILED"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    booking = relationship("Booking", back_populates="payments")


# ============================================================================
# Database Initialization & Dependency
# ============================================================================

def init_db():
    """Initializes all database tables and seeds sample events if empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_sample_events(db)
    finally:
        db.close()


def get_db():
    """FastAPI database session generator dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Service Layer Operations (CRUD & Atomic Inventory Coordination)
# ============================================================================

def create_or_get_user(db: Session, email: str, name: str, google_id: str = None, role: str = "CUSTOMER") -> User:
    """Finds an existing user by email or creates a new one."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user:
        user = User(
            email=email.strip().lower(),
            name=name.strip(),
            google_id=google_id,
            role=role.upper()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update google_id or role if newly provided
        updated = False
        if google_id and user.google_id != google_id:
            user.google_id = google_id
            updated = True
        if role and user.role != role.upper():
            user.role = role.upper()
            updated = True
        if updated:
            db.commit()
            db.refresh(user)
    return user


def create_event(
    db: Session,
    title: str,
    description: str,
    venue: str,
    event_date: datetime,
    ticket_price: float,
    total_seats: int,
    poster: str = None,
    status: str = "PUBLISHED",
    seat_labels: list = None
) -> Event:
    """
    Creates an event and automatically seeds all its individual seats in one transaction.
    """
    if ticket_price < 0:
        raise ValueError("Ticket price cannot be negative.")
    if total_seats <= 0:
        raise ValueError("Total seats must be greater than zero.")

    event = Event(
        title=title.strip(),
        description=description.strip() if description else "",
        venue=venue.strip(),
        event_date=event_date,
        ticket_price=float(ticket_price),
        total_seats=int(total_seats),
        poster=poster,
        status=status.upper()
    )
    db.add(event)
    db.flush()  # Flush to acquire event.id

    # Generate seat numbers: e.g. A1, A2, A3... or use custom seat_labels
    if seat_labels and len(seat_labels) == total_seats:
        labels = seat_labels
    else:
        # Generate grid labels: Rows A, B, C... with 10 seats per row
        labels = []
        for i in range(total_seats):
            row_char = chr(ord('A') + (i // 10))
            seat_num = (i % 10) + 1
            labels.append(f"{row_char}{seat_num}")

    seats = [
        Seat(event_id=event.id, seat_number=label, status="AVAILABLE")
        for label in labels
    ]
    db.add_all(seats)
    db.commit()
    db.refresh(event)
    return event


def get_event_with_seat_counts(db: Session, event_id: int):
    """Returns event details with current availability breakdown."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        return None

    # Count seats by status
    total = len(event.seats)
    available = sum(1 for s in event.seats if s.status == "AVAILABLE")
    reserved = sum(1 for s in event.seats if s.status == "RESERVED")
    sold = sum(1 for s in event.seats if s.status == "SOLD")

    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "venue": event.venue,
        "event_date": event.event_date.isoformat(),
        "ticket_price": event.ticket_price,
        "poster": event.poster,
        "status": event.status,
        "total_seats": total,
        "available_seats": available,
        "reserved_seats": reserved,
        "sold_seats": sold
    }


def create_pending_reservation(
    db: Session,
    user_id: int,
    event_id: int,
    seat_ids: list,
    reservation_duration_minutes: int = 5
) -> dict:
    """
    Creates a pending reservation holding the requested seats.
    
    Guarantees:
    - Runs in an atomic transaction.
    - Prevents double-booking: Checks that every requested seat is currently 'AVAILABLE'.
    - Calculates total amount from event.ticket_price in DB (never trusts frontend input).
    - Sets an expiry timestamp on the temporary reservation.
    """
    if not seat_ids:
        return {"success": False, "message": "At least one seat must be selected."}

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        return {"success": False, "message": "Event not found."}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "User not found."}

    # Fetch and verify all requested seats
    seats = db.query(Seat).filter(Seat.id.in_(seat_ids), Seat.event_id == event_id).all()
    if len(seats) != len(seat_ids):
        return {"success": False, "message": "One or more selected seats do not exist for this event."}

    # Verify every seat is available
    for seat in seats:
        if seat.status != "AVAILABLE":
            return {
                "success": False,
                "message": f"Seat '{seat.seat_number}' is already {seat.status.lower()}."
            }

    # Compute authoritative price
    total_amount = round(event.ticket_price * len(seats), 2)
    booking_ref = f"BK_{uuid.uuid4().hex[:8].upper()}"
    expiry_time = datetime.now(timezone.utc) + timedelta(minutes=reservation_duration_minutes)

    try:
        # 1. Update seats to RESERVED
        for seat in seats:
            seat.status = "RESERVED"

        # 2. Create Booking record
        booking = Booking(
            booking_reference=booking_ref,
            user_id=user_id,
            event_id=event_id,
            booking_status="PENDING",
            payment_status="PENDING",
            total_amount=total_amount
        )
        db.add(booking)
        db.flush()

        # 3. Create BookingSeat mappings
        booking_seats = [
            BookingSeat(booking_id=booking.id, seat_id=seat.id, reserved_until=expiry_time)
            for seat in seats
        ]
        db.add_all(booking_seats)
        db.commit()

        return {
            "success": True,
            "booking_id": booking.id,
            "booking_reference": booking.booking_reference,
            "total_amount": booking.total_amount,
            "seats": [s.seat_number for s in seats],
            "expires_at": expiry_time.isoformat(),
            "message": "Seats temporarily reserved. Complete checkout before reservation expires."
        }
    except Exception as err:
        db.rollback()
        return {"success": False, "message": f"Reservation failed: {str(err)}"}


def confirm_booking_payment(
    db: Session,
    booking_id: int,
    payment_reference: str,
    status: str = "SUCCESS"
) -> dict:
    """
    Confirms payment for a booking.
    - If SUCCESS: Marks booking CONFIRMED and transitions all reserved seats to SOLD permanently.
    - If FAILED: Releases reserved seats back to AVAILABLE.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return {"success": False, "message": "Booking not found."}

    if booking.booking_status == "CONFIRMED":
        return {"success": True, "message": "Booking is already confirmed and paid."}

    # Prevent paying for expired reservations
    now = datetime.now(timezone.utc)
    for bs in booking.booking_seats:
        if bs.reserved_until and bs.reserved_until.tzinfo is None:
            # Normalize naive datetime from SQLite
            res_until = bs.reserved_until.replace(tzinfo=timezone.utc)
        else:
            res_until = bs.reserved_until

        if res_until and res_until < now and status == "SUCCESS":
            # Reservation has expired!
            booking.booking_status = "EXPIRED"
            booking.payment_status = "FAILED"
            for b_seat in booking.booking_seats:
                if b_seat.seat.status == "RESERVED":
                    b_seat.seat.status = "AVAILABLE"
            db.commit()
            return {"success": False, "message": "Reservation has expired. Seats have been released."}

    try:
        # Record payment entry
        payment = Payment(
            booking_id=booking.id,
            payment_reference=payment_reference,
            amount=booking.total_amount,
            status=status.upper()
        )
        db.add(payment)

        if status.upper() == "SUCCESS":
            booking.booking_status = "CONFIRMED"
            booking.payment_status = "SUCCESS"
            # Permanently mark seats as SOLD
            for bs in booking.booking_seats:
                bs.seat.status = "SOLD"
        else:
            booking.booking_status = "CANCELLED"
            booking.payment_status = "FAILED"
            # Release seats back to AVAILABLE
            for bs in booking.booking_seats:
                if bs.seat.status == "RESERVED":
                    bs.seat.status = "AVAILABLE"

        db.commit()
        return {
            "success": True,
            "booking_reference": booking.booking_reference,
            "booking_status": booking.booking_status,
            "payment_status": booking.payment_status,
            "seats": [bs.seat.seat_number for bs in booking.booking_seats],
            "message": "Payment verified and booking confirmed!" if status.upper() == "SUCCESS" else "Payment failed; seats released."
        }
    except Exception as err:
        db.rollback()
        return {"success": False, "message": f"Payment processing error: {str(err)}"}


def release_expired_reservations(db: Session) -> int:
    """
    Background cleaner: Finds all PENDING bookings with expired reservations and releases their seats.
    Returns the count of seats freed.
    """
    now = datetime.now(timezone.utc)
    expired_seats_count = 0

    expired_booking_seats = (
        db.query(BookingSeat)
        .join(Booking)
        .filter(Booking.booking_status == "PENDING", BookingSeat.reserved_until < now)
        .all()
    )

    for bs in expired_booking_seats:
        if bs.seat.status == "RESERVED":
            bs.seat.status = "AVAILABLE"
            expired_seats_count += 1
        bs.booking.booking_status = "EXPIRED"

    if expired_seats_count > 0:
        db.commit()

    return expired_seats_count


def update_event(
    db: Session,
    event_id: int,
    title: str = None,
    description: str = None,
    venue: str = None,
    event_date: datetime = None,
    ticket_price: float = None,
    status: str = None,
    poster: str = None
):
    """Updates event metadata."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        return None
    if title is not None:
        event.title = title.strip()
    if description is not None:
        event.description = description.strip()
    if venue is not None:
        event.venue = venue.strip()
    if event_date is not None:
        event.event_date = event_date
    if ticket_price is not None:
        if ticket_price < 0:
            raise ValueError("Ticket price cannot be negative.")
        event.ticket_price = float(ticket_price)
    if status is not None:
        event.status = status.upper()
    if poster is not None:
        event.poster = poster

    db.commit()
    db.refresh(event)
    return event


def seed_sample_events(db: Session):
    """
    Seeds 4 realistic sample events into the database if empty.
    """
    if db.query(Event).count() > 0:
        return  # Already seeded

    sample_data = [
        {
            "title": "Google Developer Conference 2026",
            "description": "Join developers, cloud architects, and engineers for keynote talks on Android, Gemini, and distributed cloud systems.",
            "venue": "Moscone Center West, San Francisco",
            "event_date": datetime.now(timezone.utc) + timedelta(days=14, hours=10),
            "ticket_price": 299.00,
            "total_seats": 30,
            "poster": "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800&auto=format&fit=crop&q=80",
            "status": "PUBLISHED"
        },
        {
            "title": "Technology Innovation Summit",
            "description": "The premier gathering for technology leaders, startups, and innovators shaping the next decade of software infrastructure.",
            "venue": "Metropolitan Convention Center, New York",
            "event_date": datetime.now(timezone.utc) + timedelta(days=21, hours=9),
            "ticket_price": 199.00,
            "total_seats": 25,
            "poster": "https://images.unsplash.com/photo-1505373877841-8d25f7d46678?w=800&auto=format&fit=crop&q=80",
            "status": "PUBLISHED"
        },
        {
            "title": "AI & Machine Learning World Congress",
            "description": "Deep dive into foundation models, LLM deployment, high-throughput model serving, and distributed GPU clusters.",
            "venue": "Boston Hynes Convention Center, Boston",
            "event_date": datetime.now(timezone.utc) + timedelta(days=28, hours=11),
            "ticket_price": 349.00,
            "total_seats": 40,
            "poster": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800&auto=format&fit=crop&q=80",
            "status": "PUBLISHED"
        },
        {
            "title": "Neon Lights Music & Arts Festival",
            "description": "Three days of live electronic music, experiential stage lighting, and digital art installations.",
            "venue": "Austin Open Park Grounds, Austin, TX",
            "event_date": datetime.now(timezone.utc) + timedelta(days=35, hours=17),
            "ticket_price": 89.00,
            "total_seats": 50,
            "poster": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=800&auto=format&fit=crop&q=80",
            "status": "PUBLISHED"
        }
    ]

    for item in sample_data:
        create_event(
            db=db,
            title=item["title"],
            description=item["description"],
            venue=item["venue"],
            event_date=item["event_date"],
            ticket_price=item["ticket_price"],
            total_seats=item["total_seats"],
            poster=item["poster"],
            status=item["status"]
        )
