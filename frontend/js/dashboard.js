/**
 * frontend/js/dashboard.js
 * Mini ZooKeeper — Main Dashboard & Lock Management JavaScript
 * 
 * Features:
 * - Simple vanilla JavaScript (no complex frameworks).
 * - Real-time polling via setInterval (every 3 seconds).
 * - Shows free vs locked resources, ownership, waiting states, and timeouts.
 * - Robust error handling (never fake backend success).
 */

// Global configuration
const API_BASE_URL = "";
const POLL_INTERVAL_MS = 3000; // Poll backend every 3 seconds
let pollingTimerId = null;

// ============================================================================
// 1. Alert Banner & Activity Feed Functions
// ============================================================================

/**
 * Displays a dismissible colored message banner at the top of the dashboard.
 * @param {string} message - The text to display.
 * @param {string} type - 'success', 'danger', 'warning', or 'info'.
 */
function showAlert(message, type = "info") {
  const alertBanner = document.getElementById("alert-banner");
  const alertMessage = document.getElementById("alert-message");
  const alertIcon = document.getElementById("alert-icon");

  if (!alertBanner || !alertMessage) return;

  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  if (type === "danger") icon = "❌";
  if (type === "warning") icon = "⚠️";

  alertIcon.textContent = icon;
  alertMessage.textContent = message;
  alertBanner.className = `alert-banner alert-${type}`;
}

/**
 * Hides the alert banner.
 */
function hideAlert() {
  const alertBanner = document.getElementById("alert-banner");
  if (alertBanner) {
    alertBanner.className = "alert-banner hidden";
  }
}

/**
 * Adds an entry to the "Recent Activity Feed".
 * @param {string} text - Description of the activity.
 * @param {string} badgeType - 'success', 'danger', 'warning', 'info', or 'neutral'.
 */
function logActivity(text, badgeType = "info") {
  const activityList = document.getElementById("activity-list");
  if (!activityList) return;

  const listItem = document.createElement("li");
  listItem.className = "activity-item";

  const badge = document.createElement("span");
  badge.className = `activity-badge badge-${badgeType}`;
  badge.textContent = new Date().toLocaleTimeString();

  const textSpan = document.createElement("span");
  textSpan.className = "activity-text";
  textSpan.textContent = text;

  listItem.appendChild(badge);
  listItem.appendChild(textSpan);

  // Prepend to top of activity list
  activityList.insertBefore(listItem, activityList.firstChild);

  // Keep max 10 items
  while (activityList.children.length > 10) {
    activityList.removeChild(activityList.lastChild);
  }
}

// ============================================================================
// 2. Lock Acquisition Handler (Phase 3, 4, 5)
// ============================================================================

/**
 * Handles the Acquire Lock form submission.
 * @param {Event} event - The form submission event.
 */
function handleAcquireLock(event) {
  event.preventDefault();

  const resourceInput = document.getElementById("acquire-resource-name");
  const clientInput = document.getElementById("acquire-client-id");
  const timeoutInput = document.getElementById("acquire-timeout");
  const submitBtn = document.getElementById("acquire-submit-btn");
  const btnText = document.getElementById("acquire-btn-text");

  const resourceName = resourceInput.value.trim();
  const clientId = clientInput.value.trim();
  const timeoutSeconds = parseFloat(timeoutInput.value) || 0.0;

  // Validation
  if (!resourceName || !clientId) {
    showAlert("Please enter both Resource Name and Client ID.", "warning");
    return;
  }

  // Visual feedback: waiting state
  submitBtn.disabled = true;
  if (timeoutSeconds > 0) {
    btnText.textContent = `⏳ Waiting for lock (up to ${timeoutSeconds}s)...`;
    showAlert(`Request submitted. Waiting for lock on '${resourceName}'...`, "warning");
    logActivity(`WAITING: '${clientId}' waiting for '${resourceName}' (up to ${timeoutSeconds}s)`, "warning");
  } else {
    btnText.textContent = "⏳ Requesting lock...";
  }

  const payload = {
    resource_name: resourceName,
    client_id: clientId,
    timeout_seconds: timeoutSeconds
  };

  fetch(`${API_BASE_URL}/api/lock/acquire`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(async function(response) {
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const errorMsg = (data && data.detail) ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `Server returned status ${response.status}`;
        throw new Error(errorMsg);
      }
      return data;
    })
    .then(function(data) {
      if (data.success) {
        // Lock acquired successfully!
        showAlert(`Lock acquired successfully on '${resourceName}'! Handle: ${data.lock_handle}`, "success");
        logActivity(`ACQUIRE: '${clientId}' locked '${resourceName}' (Handle: ${data.lock_handle.substring(0, 12)}...)`, "success");

        // Automatically populate release form for user convenience
        document.getElementById("release-resource-name").value = resourceName;
        document.getElementById("release-client-id").value = clientId;
        document.getElementById("release-lock-handle").value = data.lock_handle;

        // Immediately refresh active locks table and stats
        loadActiveLocks();
        loadSystemSummary();
      } else {
        // Did not acquire lock (busy or timed out)
        if (data.message && data.message.includes("timed out")) {
          showAlert(`Request timed out: Lock on '${resourceName}' was not released in time.`, "danger");
          logActivity(`TIMEOUT: '${clientId}' timed out waiting for '${resourceName}'`, "danger");
        } else if (data.message && data.message.includes("currently held")) {
          showAlert(`Resource '${resourceName}' is already locked by another client.`, "warning");
          logActivity(`BUSY: '${clientId}' rejected; '${resourceName}' is already held`, "warning");
        } else {
          showAlert(`Request failed: ${data.message}`, "danger");
          logActivity(`FAILED: Lock attempt on '${resourceName}' failed (${data.message})`, "danger");
        }
      }
    })
    .catch(function(error) {
      setBackendStatus(false);
      showAlert(`Backend Connection Error: ${error.message}. Is FastAPI server running?`, "danger");
      logActivity(`ERROR: Could not reach backend (${error.message})`, "danger");
    })
    .finally(function() {
      // Re-enable button
      submitBtn.disabled = false;
      btnText.textContent = "🔒 Request Lock";
    });
}

// ============================================================================
// 3. Lock Release Handler (Connected to POST /api/lock/release)
// ============================================================================

/**
 * Handles the Release Lock form submission.
 * @param {Event} event - The form submission event.
 */
function handleReleaseLock(event) {
  event.preventDefault();

  const resourceInput = document.getElementById("release-resource-name");
  const clientInput = document.getElementById("release-client-id");
  const handleInput = document.getElementById("release-lock-handle");
  const submitBtn = document.getElementById("release-submit-btn");
  const btnText = document.getElementById("release-btn-text");

  const resourceName = resourceInput.value.trim();
  const clientId = clientInput.value.trim();
  const lockHandle = handleInput.value.trim();

  if (!resourceName || !clientId || !lockHandle) {
    showAlert("Please enter Resource Name, Client ID, and Lock Handle to release.", "warning");
    return;
  }

  submitBtn.disabled = true;
  btnText.textContent = "⏳ Releasing...";

  const payload = {
    resource_name: resourceName,
    client_id: clientId,
    lock_handle: lockHandle
  };

  fetch(`${API_BASE_URL}/api/lock/release`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(async function(response) {
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const errorMsg = (data && data.detail) ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `Server returned status ${response.status}`;
        throw new Error(errorMsg);
      }
      return data;
    })
    .then(function(data) {
      if (data.success) {
        showAlert(`Lock released successfully on '${resourceName}'.`, "success");
        logActivity(`RELEASE: '${clientId}' released lock on '${resourceName}'`, "success");

        // Clear release handle input
        handleInput.value = "";

        // Immediately refresh active locks table and stats
        loadActiveLocks();
        loadSystemSummary();
      } else {
        showAlert(`Release rejected: ${data.message}`, "danger");
        logActivity(`REJECTED: Release for '${resourceName}' failed (${data.message})`, "danger");
      }
    })
    .catch(function(error) {
      setBackendStatus(false);
      showAlert(`Backend Connection Error: ${error.message}. Is FastAPI server running?`, "danger");
      logActivity(`ERROR: Release failed due to network error (${error.message})`, "danger");
    })
    .finally(function() {
      submitBtn.disabled = false;
      btnText.textContent = "🔓 Release Lock";
    });
}

// ============================================================================
// 4. Quick Resource Status Inspector (Free vs Locked)
// ============================================================================

/**
 * Inspects the status of a specific named resource.
 */
function handleInspectStatus() {
  const input = document.getElementById("inspect-resource-name");
  const resultContainer = document.getElementById("inspector-result");
  const resultName = document.getElementById("inspect-result-name");
  const resultStatus = document.getElementById("inspect-result-status");
  const resultOwner = document.getElementById("inspect-result-owner");

  const resourceName = input.value.trim();
  if (!resourceName) {
    showAlert("Please enter a resource name to inspect.", "warning");
    return;
  }

  fetch(`${API_BASE_URL}/api/lock/status?resource_name=${encodeURIComponent(resourceName)}`)
    .then(async function(response) {
      if (!response.ok) throw new Error("HTTP error " + response.status);
      return response.json();
    })
    .then(function(data) {
      setBackendStatus(true);
      resultContainer.className = "inspector-result";
      resultName.textContent = data.resource_name;

      if (data.is_locked) {
        // Explicitly shows resource is LOCKED and which client owns it
        resultStatus.className = "badge badge-locked";
        resultStatus.textContent = "LOCKED";
        resultOwner.textContent = data.owner || "external_process";
      } else {
        // Explicitly shows resource is FREE
        resultStatus.className = "badge badge-free";
        resultStatus.textContent = "FREE";
        resultOwner.textContent = "None (Available to lock)";
      }
    })
    .catch(function(error) {
      setBackendStatus(false);
      showAlert(`Status check failed: Cannot reach backend (${error.message})`, "danger");
    });
}

// ============================================================================
// 5. Active Locks Table & Automated Live Polling (Phase 5)
// ============================================================================

/**
 * Loads currently held locks from /api/locks and updates the table.
 */
function loadActiveLocks() {
  fetch(`${API_BASE_URL}/api/locks`)
    .then(async function(response) {
      if (!response.ok) throw new Error("HTTP error " + response.status);
      return response.json();
    })
    .then(function(data) {
      setBackendStatus(true);
      const activeLocks = data.active_locks || [];
      const tbody = document.getElementById("active-locks-tbody");
      const statActive = document.getElementById("stat-active-locks");

      if (statActive) {
        statActive.textContent = activeLocks.length;
      }

      if (!tbody) return;
      tbody.innerHTML = "";

      if (activeLocks.length === 0) {
        tbody.innerHTML = `
          <tr class="empty-row">
            <td colspan="4">No locks are currently held. All resources free!</td>
          </tr>
        `;
        return;
      }

      // Populate table with real backend data
      activeLocks.forEach(function(item) {
        const row = document.createElement("tr");

        const dateStr = item.acquired_at 
          ? new Date(item.acquired_at * 1000).toLocaleTimeString() 
          : "Active";

        row.innerHTML = `
          <td><strong>${item.resource_name}</strong> <span class="badge badge-locked" style="font-size: 0.65rem; margin-left: 4px;">LOCKED</span></td>
          <td><span class="badge badge-neutral">${item.owner}</span></td>
          <td>${dateStr}</td>
          <td>
            <button 
              type="button" 
              class="btn btn-sm btn-outline select-release-btn"
              data-resource="${item.resource_name}"
              data-owner="${item.owner}"
            >
              Select for Release
            </button>
          </td>
        `;

        tbody.appendChild(row);
      });

      // Attach event listeners to "Select for Release" buttons
      const releaseButtons = tbody.querySelectorAll(".select-release-btn");
      releaseButtons.forEach(function(btn) {
        btn.addEventListener("click", function() {
          const res = this.getAttribute("data-resource");
          const owner = this.getAttribute("data-owner");
          document.getElementById("release-resource-name").value = res;
          document.getElementById("release-client-id").value = owner;
          document.getElementById("release-lock-handle").focus();
          showAlert(`Selected '${res}' for release. Enter lock handle to proceed.`, "info");
        });
      });
    })
    .catch(function(error) {
      setBackendStatus(false);
      console.warn("Could not load active locks from backend:", error);
    });
}

/**
 * Loads system summary stats from /analytics/summary if available.
 */
function loadSystemSummary() {
  fetch(`${API_BASE_URL}/analytics/summary`)
    .then(function(response) {
      if (!response.ok) return null;
      return response.json();
    })
    .then(function(data) {
      if (data && document.getElementById("stat-total-requests")) {
        document.getElementById("stat-total-requests").textContent = data.total_requests || 0;
      }
    })
    .catch(function(err) {
      // Analytics may be empty initially, fail silently
    });
}

/**
 * Helper to update the top navigation backend status indicator.
 * @param {boolean} isOnline - Whether the backend is reachable.
 */
function setBackendStatus(isOnline) {
  const statusIndicator = document.getElementById("backend-status-indicator");
  const statusText = document.getElementById("backend-status-text");

  if (!statusIndicator || !statusText) return;

  if (isOnline) {
    statusIndicator.className = "status-dot connected";
    statusText.textContent = "Backend Connected";
  } else {
    statusIndicator.className = "status-dot offline";
    statusText.textContent = "Backend Offline";
  }
}

/**
 * Checks backend connectivity.
 */
function checkBackendHealth() {
  fetch(`${API_BASE_URL}/`)
    .then(function(response) {
      if (response.ok) {
        setBackendStatus(true);
      } else {
        setBackendStatus(false);
      }
    })
    .catch(function(error) {
      setBackendStatus(false);
      showAlert("Cannot connect to backend server. Is FastAPI running on port 8000?", "danger");
    });
}

// ============================================================================
// 6. Page Initialization & Live Polling (Phase 5)
// ============================================================================
document.addEventListener("DOMContentLoaded", function() {
  // 1. Initial health and data check
  checkBackendHealth();
  loadActiveLocks();
  loadSystemSummary();

  // 2. Set up automated live polling every 3 seconds (clean, beginner-friendly periodic refresh)
  // Agreed method with Backend A: Polls /api/locks without websockets or complex streams
  pollingTimerId = setInterval(function() {
    loadActiveLocks();
    loadSystemSummary();
  }, POLL_INTERVAL_MS);

  // 3. Bind form submissions
  const acquireForm = document.getElementById("acquire-lock-form");
  if (acquireForm) {
    acquireForm.addEventListener("submit", handleAcquireLock);
  }

  const releaseForm = document.getElementById("release-lock-form");
  if (releaseForm) {
    releaseForm.addEventListener("submit", handleReleaseLock);
  }

  // 4. Bind inspector
  const inspectBtn = document.getElementById("inspect-btn");
  if (inspectBtn) {
    inspectBtn.addEventListener("click", handleInspectStatus);
  }

  // 5. Bind manual refresh button (refreshes immediately without waiting for timer)
  const refreshBtn = document.getElementById("refresh-locks-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", function() {
      loadActiveLocks();
      loadSystemSummary();
      logActivity("Active locks refreshed manually.", "neutral");
    });
  }

  // 6. Bind alert close button
  const closeAlertBtn = document.getElementById("alert-close");
  if (closeAlertBtn) {
    closeAlertBtn.addEventListener("click", hideAlert);
  }

  logActivity("Live status polling active (every 3s).", "neutral");
});
