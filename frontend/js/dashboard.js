/**
 * frontend/js/dashboard.js
 * Mini ZooKeeper — Main Dashboard & Lock Management JavaScript
 * 
 * Features:
 * - Simple vanilla JavaScript (no complex frameworks).
 * - Real-time polling via setInterval (every 3 seconds).
 * - File Resource Upload & Selection: Upload shared company files, select them from dropdowns.
 * - Lock-Protected Workspace: View file content; saving strictly requires holding the active OS lock.
 * - Robust error handling (never fake backend success).
 */

// Global configuration
const API_BASE_URL = "";
const POLL_INTERVAL_MS = 3000; // Poll backend every 3 seconds
let pollingTimerId = null;

// ============================================================================
// 1. Alert Banner & Activity Feed Functions
// ============================================================================

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

function hideAlert() {
  const alertBanner = document.getElementById("alert-banner");
  if (alertBanner) {
    alertBanner.className = "alert-banner hidden";
  }
}

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

  activityList.insertBefore(listItem, activityList.firstChild);

  while (activityList.children.length > 10) {
    activityList.removeChild(activityList.lastChild);
  }
}

// ============================================================================
// 2. Resource File Upload & Management
// ============================================================================

/**
 * Uploads a file to act as a shared resource in Mini ZooKeeper.
 */
function handleUploadFile() {
  const fileInput = document.getElementById("upload-file-input");
  const uploadBtn = document.getElementById("upload-file-btn");

  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    showAlert("Please select a file to upload as a shared resource.", "warning");
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  uploadBtn.disabled = true;
  uploadBtn.textContent = "⏳ Uploading...";

  fetch(`${API_BASE_URL}/api/resources/upload`, {
    method: "POST",
    body: formData
  })
    .then(async function(response) {
      if (!response.ok) throw new Error("Upload failed with status " + response.status);
      return response.json();
    })
    .then(function(data) {
      if (data.success) {
        showAlert(`File resource '${data.filename}' uploaded successfully (${data.size_bytes} bytes)!`, "success");
        logActivity(`UPLOAD: New resource file '${data.filename}' available`, "success");

        fileInput.value = "";
        // Refresh dropdowns and automatically select this uploaded file
        loadResourceFiles(data.filename);
      } else {
        showAlert(`Upload failed: ${data.message}`, "danger");
      }
    })
    .catch(function(error) {
      showAlert(`Upload error: ${error.message}`, "danger");
    })
    .finally(function() {
      uploadBtn.disabled = false;
      uploadBtn.textContent = "📤 Upload File as Resource";
    });
}

/**
 * Loads the list of uploaded resource files and populates dropdown selects.
 * @param {string|null} selectFilename - Optional filename to auto-select.
 */
function loadResourceFiles(selectFilename = null) {
  fetch(`${API_BASE_URL}/api/resources`)
    .then(function(response) {
      if (!response.ok) return null;
      return response.json();
    })
    .then(function(data) {
      if (!data || !data.resources) return;

      const acquireSelect = document.getElementById("acquire-resource-select");
      const workspaceSelect = document.getElementById("workspace-file-select");

      // Remember current selections
      const currentAcquireVal = selectFilename || (acquireSelect ? acquireSelect.value : "");
      const currentWorkspaceVal = selectFilename || (workspaceSelect ? workspaceSelect.value : "");

      // Rebuild acquire dropdown
      if (acquireSelect) {
        acquireSelect.innerHTML = '<option value="">-- Choose an uploaded file (or type custom below) --</option>';
        data.resources.forEach(function(r) {
          const opt = document.createElement("option");
          opt.value = r.filename;
          const statusText = r.is_locked ? `[LOCKED by ${r.owner}]` : "[FREE]";
          opt.textContent = `📄 ${r.filename} (${r.size_bytes} bytes) ${statusText}`;
          acquireSelect.appendChild(opt);
        });
        if (currentAcquireVal) acquireSelect.value = currentAcquireVal;
      }

      // Rebuild workspace dropdown
      if (workspaceSelect) {
        workspaceSelect.innerHTML = '<option value="">-- Select a resource file to view/work on --</option>';
        data.resources.forEach(function(r) {
          const opt = document.createElement("option");
          opt.value = r.filename;
          const statusText = r.is_locked ? `[LOCKED by ${r.owner}]` : "[FREE]";
          opt.textContent = `📄 ${r.filename} ${statusText}`;
          workspaceSelect.appendChild(opt);
        });
        if (currentWorkspaceVal) {
          workspaceSelect.value = currentWorkspaceVal;
        }
      }
    })
    .catch(function(err) {
      console.warn("Could not load resource files:", err);
    });
}

// ============================================================================
// 3. Lock-Protected Workspace (Work on Resource)
// ============================================================================

/**
 * Loads file content into the workspace textarea.
 */
function loadWorkspaceFileContent() {
  const select = document.getElementById("workspace-file-select");
  const textarea = document.getElementById("workspace-textarea");
  const lockBadge = document.getElementById("workspace-lock-badge");
  const hint = document.getElementById("workspace-hint");

  if (!select || !select.value) {
    showAlert("Please select a resource file to load from the dropdown.", "warning");
    return;
  }

  const filename = select.value;
  textarea.value = "⏳ Loading file content from backend...";

  fetch(`${API_BASE_URL}/api/resources/${encodeURIComponent(filename)}/content`)
    .then(async function(response) {
      if (!response.ok) throw new Error("Could not load file content: HTTP " + response.status);
      return response.json();
    })
    .then(function(data) {
      textarea.value = data.content || "";

      if (data.is_locked) {
        lockBadge.className = "badge badge-locked";
        lockBadge.textContent = `LOCKED by: ${data.owner}`;
        hint.textContent = `Resource is held by '${data.owner}'. Only the owner with the valid handle can save changes.`;
      } else {
        lockBadge.className = "badge badge-free";
        lockBadge.textContent = "FREE (Unlocked)";
        hint.textContent = "Resource is currently unlocked. Acquire the lock to edit and save changes.";
      }
      logActivity(`VIEW: Loaded file content for '${filename}'`, "info");
    })
    .catch(function(err) {
      textarea.value = `Error loading file: ${err.message}`;
      showAlert(err.message, "danger");
    });
}

/**
 * Saves changes to the resource file. STRICTLY requires active lock handle!
 */
function handleSaveWorkspaceFile() {
  const select = document.getElementById("workspace-file-select");
  const textarea = document.getElementById("workspace-textarea");
  const saveBtn = document.getElementById("workspace-save-btn");

  const releaseClientInput = document.getElementById("release-client-id");
  const releaseHandleInput = document.getElementById("release-lock-handle");

  if (!select || !select.value) {
    showAlert("Please select a resource file to save.", "warning");
    return;
  }

  const filename = select.value;
  const content = textarea.value;
  const clientId = releaseClientInput.value.trim();
  const lockHandle = releaseHandleInput.value.trim();

  if (!clientId || !lockHandle) {
    showAlert("Access Denied: You must acquire the lock on this file first (Client ID and Lock Handle required to save).", "danger");
    logActivity(`DENIED: Save attempt on '${filename}' blocked (no lock credentials)`, "danger");
    return;
  }

  saveBtn.disabled = true;
  saveBtn.textContent = "⏳ Verifying Lock & Saving...";

  const payload = {
    content: content,
    client_id: clientId,
    lock_handle: lockHandle
  };

  fetch(`${API_BASE_URL}/api/resources/${encodeURIComponent(filename)}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(async function(response) {
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = (data && data.detail) ? data.detail : `HTTP error ${response.status}`;
        throw new Error(detail);
      }
      return data;
    })
    .then(function(data) {
      if (data.success) {
        showAlert(`Saved successfully! File '${filename}' updated under active lock protection.`, "success");
        logActivity(`MODIFY: '${clientId}' updated '${filename}' under active lock`, "success");
        loadResourceFiles();
      } else {
        showAlert(data.message, "danger");
        logActivity(`BLOCKED: Save on '${filename}' failed (${data.message})`, "danger");
      }
    })
    .catch(function(err) {
      showAlert(`Save failed: ${err.message}`, "danger");
    })
    .finally(function() {
      saveBtn.disabled = false;
      saveBtn.textContent = "💾 Save Changes (Hold Lock)";
    });
}

// ============================================================================
// 4. Lock Acquisition Handler (Connected to POST /api/lock/acquire)
// ============================================================================

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

  if (!resourceName || !clientId) {
    showAlert("Please enter both Resource Name and Client ID.", "warning");
    return;
  }

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
        showAlert(`Lock acquired successfully on '${resourceName}'! Handle: ${data.lock_handle}`, "success");
        logActivity(`ACQUIRE: '${clientId}' locked '${resourceName}' (Handle: ${data.lock_handle.substring(0, 12)}...)`, "success");

        // Automatically populate release form for user convenience
        document.getElementById("release-resource-name").value = resourceName;
        document.getElementById("release-client-id").value = clientId;
        document.getElementById("release-lock-handle").value = data.lock_handle;

        // Automatically set workspace file dropdown to this resource and load content
        const wsSelect = document.getElementById("workspace-file-select");
        if (wsSelect) {
          wsSelect.value = resourceName;
          loadWorkspaceFileContent();
        }

        loadActiveLocks();
        loadSystemSummary();
        loadResourceFiles();
      } else {
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
      submitBtn.disabled = false;
      btnText.textContent = "🔒 Request Lock";
    });
}

// ============================================================================
// 5. Lock Release Handler (Connected to POST /api/lock/release)
// ============================================================================

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

        handleInput.value = "";

        loadActiveLocks();
        loadSystemSummary();
        loadResourceFiles();

        const wsSelect = document.getElementById("workspace-file-select");
        if (wsSelect && wsSelect.value === resourceName) {
          loadWorkspaceFileContent();
        }
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
// 6. Quick Resource Status Inspector
// ============================================================================

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
        resultStatus.className = "badge badge-locked";
        resultStatus.textContent = "LOCKED";
        resultOwner.textContent = data.owner || "external_process";
      } else {
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
// 7. Active Locks Table & Live Polling
// ============================================================================

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
// 8. Page Initialization & Event Listener Binding
// ============================================================================
document.addEventListener("DOMContentLoaded", function() {
  // 1. Initial health and data check
  checkBackendHealth();
  loadActiveLocks();
  loadSystemSummary();
  loadResourceFiles();

  // 2. Set up automated live polling every 3 seconds
  pollingTimerId = setInterval(function() {
    loadActiveLocks();
    loadSystemSummary();
    loadResourceFiles();
  }, POLL_INTERVAL_MS);

  // 3. File upload button listener
  const uploadBtn = document.getElementById("upload-file-btn");
  if (uploadBtn) {
    uploadBtn.addEventListener("click", handleUploadFile);
  }

  // 4. Dropdown change listener in Acquire Lock form
  const acquireSelect = document.getElementById("acquire-resource-select");
  if (acquireSelect) {
    acquireSelect.addEventListener("change", function() {
      if (this.value) {
        document.getElementById("acquire-resource-name").value = this.value;
        const wsSelect = document.getElementById("workspace-file-select");
        if (wsSelect) {
          wsSelect.value = this.value;
          loadWorkspaceFileContent();
        }
      }
    });
  }

  // 5. Workspace file selection and buttons
  const wsSelect = document.getElementById("workspace-file-select");
  if (wsSelect) {
    wsSelect.addEventListener("change", loadWorkspaceFileContent);
  }

  const wsLoadBtn = document.getElementById("workspace-load-btn");
  if (wsLoadBtn) {
    wsLoadBtn.addEventListener("click", loadWorkspaceFileContent);
  }

  const wsSaveBtn = document.getElementById("workspace-save-btn");
  if (wsSaveBtn) {
    wsSaveBtn.addEventListener("click", handleSaveWorkspaceFile);
  }

  // 6. Form submissions
  const acquireForm = document.getElementById("acquire-lock-form");
  if (acquireForm) {
    acquireForm.addEventListener("submit", handleAcquireLock);
  }

  const releaseForm = document.getElementById("release-lock-form");
  if (releaseForm) {
    releaseForm.addEventListener("submit", handleReleaseLock);
  }

  // 7. Inspector button
  const inspectBtn = document.getElementById("inspect-btn");
  if (inspectBtn) {
    inspectBtn.addEventListener("click", handleInspectStatus);
  }

  // 8. Refresh button
  const refreshBtn = document.getElementById("refresh-locks-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", function() {
      loadActiveLocks();
      loadSystemSummary();
      loadResourceFiles();
      logActivity("Active locks refreshed manually.", "neutral");
    });
  }

  // 9. Alert close button
  const closeAlertBtn = document.getElementById("alert-close");
  if (closeAlertBtn) {
    closeAlertBtn.addEventListener("click", hideAlert);
  }

  logActivity("Mini ZooKeeper Resource Workspace ready.", "neutral");
});
