/**
 * frontend/js/analytics.js
 * Frontend B: Analytics Dashboard Logic for Mini ZooKeeper
 *
 * Fetches calculated metrics and performance summary from Backend B.
 * Updates KPI metric cards and displays backend Matplotlib charts.
 */

// API Base URL configuration:
// If page is served by the backend, use window.location.origin.
// If opened directly from disk (file://), fall back to local FastAPI server on port 8000.
const API_BASE_URL = window.location.origin.startsWith("http")
  ? window.location.origin
  : "http://127.0.0.1:8000";

// DOM Elements - Metrics
const valTotalRequests = document.getElementById("val-total-requests");
const valAcquisitions = document.getElementById("val-acquisitions");
const valReleased = document.getElementById("val-released");
const valTimeouts = document.getElementById("val-timeouts");
const valTimeoutRate = document.getElementById("val-timeout-rate");
const valAvgWait = document.getElementById("val-avg-wait");
const valAvgHold = document.getElementById("val-avg-hold");

// DOM Elements - Charts
const imgChartWait = document.getElementById("img-chart-wait");
const imgChartTimeouts = document.getElementById("img-chart-timeouts");
const imgChartHold = document.getElementById("img-chart-hold");

// DOM Elements - UI States
const loadingState = document.getElementById("loading-state");
const errorState = document.getElementById("error-state");
const errorMessage = document.getElementById("error-message");
const analyticsContent = document.getElementById("analytics-content");
const lastUpdatedText = document.getElementById("last-updated-text");
const btnRefresh = document.getElementById("btn-refresh");
const btnRetry = document.getElementById("btn-retry");

/**
 * Toggles the loading spinner and disables/enables the refresh button.
 */
function setLoading(isLoading) {
  if (isLoading) {
    loadingState.style.display = "block";
    errorState.style.display = "none";
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
  errorState.style.display = "block";
  errorMessage.textContent = messageText;
}

/**
 * Updates the 7 metric cards with values returned by the backend.
 */
function updateMetricCards(data) {
  valTotalRequests.textContent = data.total_requests ?? 0;
  valAcquisitions.textContent = data.successful_acquisitions ?? 0;
  valReleased.textContent = data.released_locks ?? 0;
  valTimeouts.textContent = data.timed_out_requests ?? 0;

  // Format percentage
  const rate = data.timeout_rate_pct !== undefined ? Number(data.timeout_rate_pct).toFixed(1) : "0.0";
  valTimeoutRate.textContent = `${rate}%`;

  // Format millisecond values
  const avgWait = data.avg_wait_ms !== undefined ? Number(data.avg_wait_ms).toFixed(1) : "0.0";
  valAvgWait.textContent = `${avgWait} ms`;

  const avgHold = data.avg_hold_ms !== undefined ? Number(data.avg_hold_ms).toFixed(1) : "0.0";
  valAvgHold.textContent = `${avgHold} ms`;
}

/**
 * Refreshes chart image sources with cache-busting timestamps.
 */
function updateCharts() {
  const timestamp = Date.now();
  if (imgChartWait) {
    imgChartWait.src = `${API_BASE_URL}/analytics/charts/chart_wait_time.png?t=${timestamp}`;
  }
  if (imgChartTimeouts) {
    imgChartTimeouts.src = `${API_BASE_URL}/analytics/charts/chart_timeouts.png?t=${timestamp}`;
  }
  if (imgChartHold) {
    imgChartHold.src = `${API_BASE_URL}/analytics/charts/chart_hold_time.png?t=${timestamp}`;
  }
}

/**
 * Fetches summary analytics from Backend B API endpoint: GET /analytics/summary
 */
async function fetchAnalytics() {
  setLoading(true);

  try {
    const url = `${API_BASE_URL}/analytics/summary`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    setLoading(false);
    updateMetricCards(data);
    updateCharts();

    const now = new Date();
    lastUpdatedText.textContent = `Updated at ${now.toLocaleTimeString()}`;
  } catch (err) {
    setLoading(false);
    showError(
      `Could not load analytics from ${API_BASE_URL}. Ensure the backend server is running (python3 -m uvicorn src.lock_adapter:app --port 8000). Details: ${err.message}`
    );
  }
}

// Event Listeners
if (btnRefresh) {
  btnRefresh.addEventListener("click", fetchAnalytics);
}

if (btnRetry) {
  btnRetry.addEventListener("click", fetchAnalytics);
}

// Initial fetch on page load
window.addEventListener("DOMContentLoaded", fetchAnalytics);
