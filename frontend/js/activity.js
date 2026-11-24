/**
 * frontend/js/activity.js
 * Frontend B: Activity Logs Logic for Mini ZooKeeper
 *
 * Fetches actual lock activity records from Backend B using fetch()
 * and handles Loading, Error, Empty, and Success states.
 */

// API Base URL configuration:
// If page is served by the backend, use window.location.origin.
// If opened directly from disk (file://), fall back to local FastAPI server on port 8000.
const API_BASE_URL = window.location.origin.startsWith("http")
  ? window.location.origin
  : "http://127.0.0.1:8000";

// DOM Elements
const tableBody = document.getElementById("activity-table-body");
const loadingState = document.getElementById("loading-state");
const errorState = document.getElementById("error-state");
const errorMessage = document.getElementById("error-message");
const emptyState = document.getElementById("empty-state");
const tableContainer = document.getElementById("table-container");
const logCountBadge = document.getElementById("log-count-badge");
const lastUpdatedText = document.getElementById("last-updated-text");
const btnRefresh = document.getElementById("btn-refresh");
const btnRetry = document.getElementById("btn-retry");

/**
 * Returns a styled HTML status badge for the given status string.
 */
function getStatusBadge(status) {
  const normalized = (status || "").toLowerCase().trim();
  let badgeClass = "badge-failed";
  let displayLabel = "Failed";

  if (normalized === "requested") {
    badgeClass = "badge-requested";
    displayLabel = "Requested";
  } else if (normalized === "acquired") {
    badgeClass = "badge-acquired";
    displayLabel = "Acquired";
  } else if (normalized === "released") {
    badgeClass = "badge-released";
    displayLabel = "Released";
  } else if (normalized === "timed_out" || normalized === "timed out") {
    badgeClass = "badge-timed_out";
    displayLabel = "Timed Out";
  }

  return `<span class="status-badge ${badgeClass}">${displayLabel}</span>`;
}

/**
 * Formats ISO timestamp strings into clean, readable time (HH:MM:SS.mmm).
 */
function formatTime(isoString) {
  if (!isoString) return "-";
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return (
      date.toLocaleTimeString([], { hour12: false }) +
      "." +
      String(date.getMilliseconds()).padStart(3, "0")
    );
  } catch (e) {
    return isoString;
  }
}

/**
 * Shows or hides the loading spinner and disables the refresh button.
 */
function setLoading(isLoading) {
  if (isLoading) {
    loadingState.style.display = "block";
    errorState.style.display = "none";
    emptyState.style.display = "none";
    tableContainer.style.display = "none";
    if (btnRefresh) btnRefresh.disabled = true;
  } else {
    loadingState.style.display = "none";
    if (btnRefresh) btnRefresh.disabled = false;
  }
}

/**
 * Displays an error banner with a message and retry button.
 */
function showError(messageText) {
  loadingState.style.display = "none";
  emptyState.style.display = "none";
  tableContainer.style.display = "none";
  errorState.style.display = "block";
  errorMessage.textContent = messageText;
}

/**
 * Renders the fetched list of log records into the table.
 */
function renderLogs(logs) {
  tableBody.innerHTML = "";

  // Handle empty log list
  if (!logs || logs.length === 0) {
    tableContainer.style.display = "none";
    emptyState.style.display = "block";
    logCountBadge.textContent = "0 records";
    return;
  }

  // Display table and update count
  emptyState.style.display = "none";
  tableContainer.style.display = "block";
  logCountBadge.textContent = `${logs.length} records`;

  for (let i = 0; i < logs.length; i++) {
    const item = logs[i];
    const row = document.createElement("tr");

    const waitDisplay =
      item.wait_ms !== "" && item.wait_ms !== null && item.wait_ms !== undefined
        ? `${item.wait_ms} ms`
        : "-";

    const holdDisplay =
      item.hold_ms !== "" && item.hold_ms !== null && item.hold_ms !== undefined
        ? `${item.hold_ms} ms`
        : "-";

    row.innerHTML = `
      <td><span class="code-pill">${item.request_id || "-"}</span></td>
      <td><strong>${item.client_id || "-"}</strong></td>
      <td><code>${item.resource_name || "-"}</code></td>
      <td>${formatTime(item.requested_at)}</td>
      <td>${formatTime(item.acquired_at)}</td>
      <td>${formatTime(item.released_at)}</td>
      <td>${getStatusBadge(item.status)}</td>
      <td><span class="text-primary fw-semibold">${waitDisplay}</span></td>
      <td><span class="text-success fw-semibold">${holdDisplay}</span></td>
    `;
    tableBody.appendChild(row);
  }
}

/**
 * Fetches real activity logs from the Backend B API endpoint: GET /analytics/logs
 */
async function fetchActivityLogs() {
  setLoading(true);

  try {
    const url = `${API_BASE_URL}/analytics/logs?limit=50`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    setLoading(false);
    renderLogs(data);

    // Update timestamp
    const now = new Date();
    lastUpdatedText.textContent = `Updated at ${now.toLocaleTimeString()}`;
  } catch (err) {
    setLoading(false);
    showError(
      `Could not connect to Backend API at ${API_BASE_URL}. Ensure the server is running (python3 -m uvicorn src.lock_adapter:app --port 8000). Details: ${err.message}`
    );
  }
}

// Event Listeners
if (btnRefresh) {
  btnRefresh.addEventListener("click", fetchActivityLogs);
}

if (btnRetry) {
  btnRetry.addEventListener("click", fetchActivityLogs);
}

// Initial fetch when page loads
window.addEventListener("DOMContentLoaded", fetchActivityLogs);
