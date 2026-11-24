"""
src/lock_manager.py
Core Locking System for Mini ZooKeeper (Backend A).

Features:
- OS-level file locking via fcntl.flock (atomic, crash-safe)
- Input validation (resource name safety, path traversal prevention)
- Configurable waiting timeout
- Unique request IDs (uuid)
- Client ID & resource ownership tracking
- Secure lock handles (bearer tokens)
- Unauthorized release protection
- Safe file descriptor cleanup to prevent leaks
- Graceful crash recovery handled by the OS kernel
"""

import os
import time
import uuid

# On Unix/Linux/macOS, standard library 'fcntl' provides kernel-level file locking.
try:
    import fcntl
except ImportError:
    fcntl = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCKS_DIR = os.path.join(BASE_DIR, "..", "locks_data")
os.makedirs(LOCKS_DIR, exist_ok=True)


# In-memory dictionary tracking locks held by this process.
# Format:
# {
#     "resource_name": {
#         "client_id": "client_alice",
#         "lock_handle": "handle_abc12345",
#         "file_object": <file object>,
#         "acquired_at": 1700000000.0
#     }
# }
HELD_LOCKS = {}


def validate_resource_name(resource_name):
    """
    Validates that a resource name is safe to use as a file on disk.

    Rules:
    - Must be a non-empty string.
    - Cannot contain path separators ('/' or '\\') or path traversal ('..').
    - Only allows letters, numbers, hyphens, underscores, and dots.

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not isinstance(resource_name, str):
        return False, "Resource name must be a string."

    trimmed = resource_name.strip()
    if not trimmed:
        return False, "Resource name cannot be empty or only spaces."

    if "/" in trimmed or "\\" in trimmed:
        return False, "Resource name cannot contain directory separators ('/' or '\\')."

    if ".." in trimmed:
        return False, "Resource name cannot contain path traversal ('..')."

    # Check for valid characters
    for ch in trimmed:
        if not (ch.isalnum() or ch in ("_", "-", ".")):
            return False, f"Resource name contains invalid character: '{ch}'."

    return True, None


def validate_client_id(client_id):
    """
    Validates that a client ID is a non-empty string.

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not isinstance(client_id, str):
        return False, "Client ID must be a string."

    trimmed = client_id.strip()
    if not trimmed:
        return False, "Client ID cannot be empty or only spaces."

    return True, None


def _get_lock_file_path(resource_name):
    """
    Returns the absolute path to the lock file for a resource.
    """
    return os.path.join(LOCKS_DIR, f"{resource_name}.lock")


def acquire_lock(resource_name, client_id, timeout_seconds=0.0):
    """
    Attempts to acquire an exclusive lock on a resource for a client.

    Parameters:
        resource_name (str): The resource identifier (e.g. 'inventory_item_42').
        client_id (str): The client identity (e.g. 'worker_1').
        timeout_seconds (float): Max seconds to wait. 0.0 means immediate check.

    Returns:
        dict:
            - 'success' (bool): True if acquired, False otherwise.
            - 'lock_handle' (str or None): Secret ticket needed to release the lock.
            - 'request_id' (str): Unique request identifier.
            - 'resource_name' (str): Target resource.
            - 'client_id' (str): Requesting client.
            - 'message' (str): Descriptive outcome.
    """
    request_id = f"req_{uuid.uuid4().hex[:8]}"

    # Step 1: Validate resource name
    is_valid_res, res_err = validate_resource_name(resource_name)
    if not is_valid_res:
        return {
            "success": False,
            "lock_handle": None,
            "request_id": request_id,
            "resource_name": str(resource_name),
            "client_id": str(client_id),
            "message": f"Invalid resource name: {res_err}"
        }

    # Step 2: Validate client ID
    is_valid_client, client_err = validate_client_id(client_id)
    if not is_valid_client:
        return {
            "success": False,
            "lock_handle": None,
            "request_id": request_id,
            "resource_name": resource_name,
            "client_id": str(client_id),
            "message": f"Invalid client ID: {client_err}"
        }

    # Step 3: Platform check (Linux/Unix support)
    if fcntl is None:
        return {
            "success": False,
            "lock_handle": None,
            "request_id": request_id,
            "resource_name": resource_name,
            "client_id": client_id,
            "message": "OS-level locking (fcntl) is supported on Linux/macOS. Not available on this system."
        }

    # Step 4: Ensure timeout is a valid non-negative number
    try:
        timeout_seconds = float(timeout_seconds)
        if timeout_seconds < 0.0:
            timeout_seconds = 0.0
    except (ValueError, TypeError):
        timeout_seconds = 0.0

    # Step 5: Check if this process already recorded this lock
    if resource_name in HELD_LOCKS:
        current_owner = HELD_LOCKS[resource_name]["client_id"]
        if current_owner == client_id:
            return {
                "success": True,
                "lock_handle": HELD_LOCKS[resource_name]["lock_handle"],
                "request_id": request_id,
                "resource_name": resource_name,
                "client_id": client_id,
                "message": "Lock is already held by this client."
            }
        elif timeout_seconds <= 0.0:
            return {
                "success": False,
                "lock_handle": None,
                "request_id": request_id,
                "resource_name": resource_name,
                "client_id": client_id,
                "message": f"Lock is currently held by '{current_owner}'."
            }

    lock_file_path = _get_lock_file_path(resource_name)

    # Step 6: Open the lock file safely
    try:
        file_object = open(lock_file_path, "a")
    except Exception as err:
        return {
            "success": False,
            "lock_handle": None,
            "request_id": request_id,
            "resource_name": resource_name,
            "client_id": client_id,
            "message": f"Failed to open lock file: {str(err)}"
        }

    fd = file_object.fileno()
    lock_flags = fcntl.LOCK_EX | fcntl.LOCK_NB
    start_time = time.time()

    # Step 7: Wait loop with timeout
    while True:
        try:
            # Request exclusive lock from OS kernel
            fcntl.flock(fd, lock_flags)

            # Acquired! Generate secret handle and record ownership
            lock_handle = f"handle_{uuid.uuid4().hex[:12]}"
            HELD_LOCKS[resource_name] = {
                "client_id": client_id,
                "lock_handle": lock_handle,
                "file_object": file_object,
                "acquired_at": time.time()
            }

            return {
                "success": True,
                "lock_handle": lock_handle,
                "request_id": request_id,
                "resource_name": resource_name,
                "client_id": client_id,
                "message": "Lock acquired successfully."
            }

        except (BlockingIOError, OSError):
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout_seconds:
                # Timeout expired: close file to avoid descriptor leak
                file_object.close()
                return {
                    "success": False,
                    "lock_handle": None,
                    "request_id": request_id,
                    "resource_name": resource_name,
                    "client_id": client_id,
                    "message": f"Lock acquisition timed out after {timeout_seconds} seconds."
                }

            time.sleep(0.05)

        except Exception as unexpected_err:
            # Catch any unexpected system error, close file, and report cleanly
            file_object.close()
            return {
                "success": False,
                "lock_handle": None,
                "request_id": request_id,
                "resource_name": resource_name,
                "client_id": client_id,
                "message": f"Unexpected error while acquiring lock: {str(unexpected_err)}"
            }


def release_lock(resource_name, client_id, lock_handle):
    """
    Releases a held lock with safety and authorization checks.

    Parameters:
        resource_name (str): Resource to unlock.
        client_id (str): Client attempting release.
        lock_handle (str): Secret handle from acquire_lock.

    Returns:
        dict:
            - 'success' (bool): True if successfully released, False otherwise.
            - 'message' (str): Details about the operation.
    """
    # Validation checks
    is_valid_res, res_err = validate_resource_name(resource_name)
    if not is_valid_res:
        return {"success": False, "message": f"Invalid resource name: {res_err}"}

    if not isinstance(lock_handle, str) or not lock_handle.strip():
        return {"success": False, "message": "Invalid lock handle: handle must be a non-empty string."}

    if fcntl is None:
        return {"success": False, "message": "OS-level locking is not supported on this platform."}

    # Check if lock exists in our process registry
    if resource_name not in HELD_LOCKS:
        return {
            "success": False,
            "message": f"Resource '{resource_name}' is not currently locked by this process."
        }

    current_lock = HELD_LOCKS[resource_name]

    # Verify client ID
    if current_lock["client_id"] != client_id:
        return {
            "success": False,
            "message": f"Unauthorized: Client '{client_id}' does not own the lock on '{resource_name}'."
        }

    # Verify secret lock handle
    if current_lock["lock_handle"] != lock_handle:
        return {
            "success": False,
            "message": "Unauthorized: Invalid lock handle provided."
        }

    file_object = current_lock["file_object"]
    fd = file_object.fileno()

    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except Exception as err:
        return {
            "success": False,
            "message": f"Error releasing OS lock: {str(err)}"
        }
    finally:
        # Guarantee file descriptor closure and state cleanup
        try:
            file_object.close()
        except Exception:
            pass
        if resource_name in HELD_LOCKS:
            del HELD_LOCKS[resource_name]

    return {
        "success": True,
        "message": f"Lock on '{resource_name}' released successfully."
    }


def get_lock_status(resource_name):
    """
    Inspects whether a resource is currently locked.
    Does not expose sensitive lock handles or open file objects.
    """
    is_valid_res, res_err = validate_resource_name(resource_name)
    if not is_valid_res:
        return {
            "resource_name": str(resource_name),
            "is_locked": False,
            "owner": None,
            "acquired_at": None,
            "error": f"Invalid resource name: {res_err}"
        }

    # If held by this process
    if resource_name in HELD_LOCKS:
        lock_info = HELD_LOCKS[resource_name]
        return {
            "resource_name": resource_name,
            "is_locked": True,
            "owner": lock_info["client_id"],
            "acquired_at": lock_info["acquired_at"],
            "error": None
        }

    lock_file_path = _get_lock_file_path(resource_name)
    if not os.path.exists(lock_file_path):
        return {
            "resource_name": resource_name,
            "is_locked": False,
            "owner": None,
            "acquired_at": None,
            "error": None
        }

    if fcntl is None:
        return {
            "resource_name": resource_name,
            "is_locked": False,
            "owner": None,
            "acquired_at": None,
            "error": "fcntl not supported"
        }

    try:
        test_file = open(lock_file_path, "a")
        fcntl.flock(test_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Succeeded: not locked by anyone
        fcntl.flock(test_file.fileno(), fcntl.LOCK_UN)
        test_file.close()
        return {
            "resource_name": resource_name,
            "is_locked": False,
            "owner": None,
            "acquired_at": None,
            "error": None
        }
    except (BlockingIOError, OSError):
        # File descriptor must be closed
        try:
            test_file.close()
        except Exception:
            pass
        return {
            "resource_name": resource_name,
            "is_locked": True,
            "owner": "external_process",
            "acquired_at": None,
            "error": None
        }
    except Exception as err:
        return {
            "resource_name": resource_name,
            "is_locked": False,
            "owner": None,
            "acquired_at": None,
            "error": f"Unexpected error: {str(err)}"
        }


def get_all_active_locks():
    """
    Returns a list of all currently held locks in this process.
    Safe for API display: does not expose lock handles or file descriptors.

    Returns:
        list of dict: Each item contains 'resource_name', 'owner', 'acquired_at'.
    """
    active_list = []
    for res_name, info in list(HELD_LOCKS.items()):
        active_list.append({
            "resource_name": res_name,
            "owner": info["client_id"],
            "acquired_at": info["acquired_at"]
        })
    return active_list

