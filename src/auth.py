"""
src/auth.py
Authentication & Role-Based Authorization for Mini ZooKeeper (Phase 3).

Features:
- Google OAuth 2.0 token verification
- Approved organizer email whitelist
- Server-side role assignment:
  - Approved emails -> ORGANIZER
  - All other authenticated users -> CUSTOMER
- Cryptographic session tokens (JWT)
- Role protection dependencies (require_organizer, require_authenticated_user)
- Dev/Viva demo login support (for offline evaluation)
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Set

import jwt
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

try:
    from database import User, get_db, create_or_get_user
except ImportError:
    from src.database import User, get_db, create_or_get_user


# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "minizookeeper-super-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Google OAuth Credentials (configured via environment)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Configurable Approved Organizer Whitelist
# Any email in this set gets ORGANIZER permissions; all other authenticated users are CUSTOMER
DEFAULT_APPROVED_ORGANIZERS = {
    "kapilpoddar99999@gmail.com",
    "priyanshsingatiya07@gmail.com",
    "admin@zookeeper.com",
    "organizer@example.com"
}

def get_approved_organizers() -> Set[str]:
    """Retrieves the list of approved organizer emails from env or defaults."""
    env_organizers = os.getenv("APPROVED_ORGANIZERS", "")
    if env_organizers:
        emails = {e.strip().lower() for e in env_organizers.split(",") if e.strip()}
        return emails | DEFAULT_APPROVED_ORGANIZERS
    return DEFAULT_APPROVED_ORGANIZERS


# Bearer token extractor for FastAPI
security_bearer = HTTPBearer(auto_error=False)


# ============================================================================
# Token Creation & Verification
# ============================================================================

def create_access_token(user_id: int, email: str, role: str) -> str:
    """Creates a signed JWT session token."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "email": email.lower(),
        "role": role.upper(),
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp())
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodes and validates a signed JWT session token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please sign in again."
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )


# ============================================================================
# Role Assignment Logic
# ============================================================================

def determine_user_role(email: str) -> str:
    """
    CRITICAL SECURITY RULE:
    Role is strictly decided server-side based on verified email.
    Never trust roles provided by frontend input.
    """
    normalized_email = email.strip().lower()
    if normalized_email in get_approved_organizers():
        return "ORGANIZER"
    return "CUSTOMER"


# ============================================================================
# FastAPI Dependencies for Role Protection
# ============================================================================

def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency to extract and verify the current authenticated user."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with Google."
        )

    payload = decode_access_token(auth.credentials)
    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found."
        )
    return user


def require_organizer(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency restricting endpoint access to ORGANIZER role only."""
    if current_user.role != "ORGANIZER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Organizer privileges required."
        )
    return current_user


def require_customer(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency ensuring user is authenticated."""
    return current_user
