"""
src/telemetry.py
Backend B: Logging and Telemetry for Mini ZooKeeper
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path

# Try to import fcntl for process-safe file locking (standard on macOS and Linux)
try:
    import fcntl
except ImportError:
    fcntl = None

# The exact 9 fields agreed upon for the CSV log
FIELDNAMES = [
    "request_id",
    "client_id",
    "resource_name",
    "requested_at",
    "acquired_at",
    "released_at",
    "status",
    "wait_ms",
    "hold_ms",
]

# Allowed event statuses
VALID_STATUSES = {"requested", "acquired", "released", "timed_out", "failed"}


def record_event(event_dict, filepath="data/locks.csv"):
    """
    Appends a single telemetry event to the CSV log file safely.
    Handles process-safety, validation rules, and missing timestamps.
    """
    # 1. Validate status
    status = event_dict.get("status", "failed")
    if status not in VALID_STATUSES:
        status = "failed"

    # 2. Rule: wait_ms must never be negative
    raw_wait = event_dict.get("wait_ms")
    if raw_wait in ("", None):
        wait_ms = "" if status == "released" else 0
    else:
        try:
            wait_ms = max(0, int(raw_wait))
        except (ValueError, TypeError):
            wait_ms = 0

    # 3. Rule: hold_ms should only be recorded for successfully released locks
    raw_hold = event_dict.get("hold_ms", "")
    if status == "released" and raw_hold not in ("", None):
        try:
            hold_ms = max(0, int(raw_hold))
        except (ValueError, TypeError):
            hold_ms = 0
    else:
        hold_ms = ""  # Empty for non-released events

    # 4. Handle missing timestamps gracefully (default to empty string "")
    row = {
        "request_id": str(event_dict.get("request_id", "")),
        "client_id": str(event_dict.get("client_id", "")),
        "resource_name": str(event_dict.get("resource_name", "")),
        "requested_at": str(event_dict.get("requested_at") or ""),
        "acquired_at": str(event_dict.get("acquired_at") or ""),
        "released_at": str(event_dict.get("released_at") or ""),
        "status": status,
        "wait_ms": wait_ms,
        "hold_ms": hold_ms,
    }

    # 5. Ensure directory exists
    file_path = Path(filepath)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 6. Open file and use file locking to prevent corrupt writes across processes
    with open(file_path, mode="a", newline="", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Acquire exclusive lock
        try:
            # Check current end-of-file position after acquiring the lock
            f.seek(0, os.SEEK_END)
            write_header = f.tell() == 0
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
            f.flush()  # Ensure data is written to disk
        finally:
            if fcntl:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock

    return row


def export_to_json(csv_path="data/locks.csv", json_path="data/locks.json"):
    """
    Reads the CSV log and saves the data as a clean JSON file.
    Returns the list of records.
    """
    records = []
    csv_file = Path(csv_path)

    if csv_file.exists():
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numbers back to int where appropriate
                if row.get("wait_ms") not in ("", None):
                    try:
                        row["wait_ms"] = int(row["wait_ms"])
                    except ValueError:
                        pass
                if row.get("hold_ms") not in ("", None):
                    try:
                        row["hold_ms"] = int(row["hold_ms"])
                    except ValueError:
                        pass
                records.append(row)

    json_file = Path(json_path)
    json_file.parent.mkdir(parents=True, exist_ok=True)
    with open(json_file, mode="w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    return records


def emit_event(
    request_id,
    client_id,
    resource_name,
    status,
    wait_ms=0,
    hold_ms=0,
    requested_at=None,
    acquired_at=None,
    released_at=None,
    filepath="data/locks.csv",
):
    """
    Convenience function for Backend A to emit events with minimal boilerplate.
    Automatically assigns ISO timestamps when not explicitly provided.
    """
    now_iso = datetime.now().isoformat()
    if requested_at is None and status == "requested":
        requested_at = now_iso
    elif acquired_at is None and status == "acquired":
        acquired_at = now_iso
    elif released_at is None and status == "released":
        released_at = now_iso

    event_dict = {
        "request_id": request_id,
        "client_id": client_id,
        "resource_name": resource_name,
        "status": status,
        "wait_ms": wait_ms,
        "hold_ms": hold_ms,
        "requested_at": requested_at,
        "acquired_at": acquired_at,
        "released_at": released_at,
    }
    return record_event(event_dict, filepath=filepath)

