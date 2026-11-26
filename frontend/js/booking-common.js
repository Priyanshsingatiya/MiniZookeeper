/**
 * frontend/js/booking-common.js
 * Common Utilities, Authentication State, Navbar Rendering, and API Helpers.
 */

const API_BASE = "";

// --------------------------------------------------------------------------
// Auth State Management
// --------------------------------------------------------------------------
function getUser() {
  try {
    const raw = localStorage.getItem("minizoo_user");
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function getToken() {
  return localStorage.getItem("minizoo_token") || "";
}

function setUserSession(user, token) {
  if (user) {
    localStorage.setItem("minizoo_user", JSON.stringify(user));
  }
  if (token) {
    localStorage.setItem("minizoo_token", token);
  }
}

function logout() {
  localStorage.removeItem("minizoo_user");
  localStorage.removeItem("minizoo_token");
  window.location.href = "login.html";
}

// --------------------------------------------------------------------------
// Authenticated Fetch Helper
// --------------------------------------------------------------------------
async function authFetch(url, options = {}) {
  const token = getToken();
  const headers = options.headers || {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (!headers["Content-Type"] && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  options.headers = headers;
  return fetch(url, options);
}

// --------------------------------------------------------------------------
// Global Navigation Bar Rendering
// --------------------------------------------------------------------------
function renderNavbar(activePage = "") {
  const placeholder = document.getElementById("navbar-placeholder");
  if (!placeholder) return;

  const user = getUser();
  const isOrganizer = user && user.role === "ORGANIZER";

  let userSection = "";
  if (user) {
    userSection = `
      <div style="display: flex; align-items: center; gap: 0.75rem;">
        <span class="badge ${isOrganizer ? 'badge-primary' : 'badge-secondary'}" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;">
          ${user.role}
        </span>
        <span style="font-size: 0.85rem; color: #cbd5e1; font-weight: 500;">
          ${escapeHtml(user.name || user.email)}
        </span>
        <button onclick="logout()" class="btn btn-sm btn-secondary" style="padding: 0.2rem 0.6rem; font-size: 0.8rem;">
          Logout
        </button>
      </div>
    `;
  } else {
    userSection = `
      <a href="login.html" class="btn btn-sm btn-primary" style="padding: 0.35rem 0.8rem; font-size: 0.85rem;">
        Sign In
      </a>
    `;
  }

  placeholder.innerHTML = `
    <nav class="navbar">
      <div class="nav-container">
        <a href="events.html" class="nav-brand" style="text-decoration: none; color: #fff;">
          <span class="brand-icon">🎟️</span>
          <span>Mini ZooKeeper <span style="font-size: 0.8rem; font-weight: 400; color: #94a3b8;">Tickets</span></span>
        </a>
        <div class="nav-links">
          <a href="events.html" class="nav-link ${activePage === 'events' ? 'active' : ''}">Events</a>
          <a href="my-bookings.html" class="nav-link ${activePage === 'bookings' ? 'active' : ''}">My Tickets</a>
          ${isOrganizer ? `<a href="organizer.html" class="nav-link ${activePage === 'organizer' ? 'active' : ''}">Organizer Dashboard</a>` : ''}
          <a href="index.html" class="nav-link ${activePage === 'locks' ? 'active' : ''}">Lock Engine</a>
          <a href="analytics.html" class="nav-link ${activePage === 'analytics' ? 'active' : ''}">Telemetry</a>
        </div>
        ${userSection}
      </div>
    </nav>
  `;
}

// --------------------------------------------------------------------------
// Toast Notification
// --------------------------------------------------------------------------
function showToast(message, type = "info") {
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.style.position = "fixed";
    toastContainer.style.top = "20px";
    toastContainer.style.right = "20px";
    toastContainer.style.zIndex = "99999";
    toastContainer.style.display = "flex";
    toastContainer.style.flexDirection = "column";
    toastContainer.style.gap = "10px";
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement("div");
  const bg = type === "success" ? "#16a34a" : type === "danger" ? "#dc2626" : type === "warning" ? "#d97706" : "#2563eb";
  toast.style.background = bg;
  toast.style.color = "#ffffff";
  toast.style.padding = "0.75rem 1.25rem";
  toast.style.borderRadius = "6px";
  toast.style.boxShadow = "0 4px 6px -1px rgba(0, 0, 0, 0.2)";
  toast.style.fontSize = "0.9rem";
  toast.style.fontWeight = "500";
  toast.style.maxWidth = "360px";
  toast.style.transition = "all 0.3s ease";
  toast.innerText = message;

  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-10px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDate(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-US", {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  } catch (e) {
    return isoStr;
  }
}
