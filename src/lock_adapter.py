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

# Import the core locking functions from our lock_manager
try:
    from lock_manager import (
        acquire_lock as core_acquire,
        release_lock as core_release,
        get_lock_status as core_status,
        get_all_active_locks as core_list_active
    )
except ImportError:
    from src.lock_manager import (
        acquire_lock as core_acquire,
        release_lock as core_release,
        get_lock_status as core_status,
        get_all_active_locks as core_list_active
    )

# Optional FastAPI integration for the web dashboard and REST API
try:
    from fastapi import FastAPI, Query
    from fastapi.staticfiles import StaticFiles
    from pathlib import Path
    FASTAPI_AVAILABLE = True
except ImportError:
    FastAPI = None
    StaticFiles = None
    Path = None
    FASTAPI_AVAILABLE = False


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
