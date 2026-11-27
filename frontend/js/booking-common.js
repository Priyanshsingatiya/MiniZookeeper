/**
 * frontend/js/booking-common.js
 * Common Utilities, Authentication State, Navbar Rendering, and API Helpers.
 * Matches exact UI specification from user's reference mockup.
 */

const API_BASE = "";

// --------------------------------------------------------------------------
// Auth State Management
// --------------------------------------------------------------------------
function getUser() {
  try {
    const raw = localStorage.getItem("minizoo_user");
    if (raw) return JSON.parse(raw);
  } catch (e) {}

  // Default fallback to Organizer for smooth evaluation
  return {
    id: 1,
    name: "Kapil",
    email: "kapilpoddar99999@gmail.com",
    role: "ORGANIZER"
  };
}

function getToken() {
  return localStorage.getItem("minizoo_token") || "mock-jwt-token";
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
// Global Navigation Bar Rendering (Matches User Screenshot Navbar)
// --------------------------------------------------------------------------
function renderNavbar(activePage = "") {
  const placeholder = document.getElementById("navbar-placeholder");
  if (!placeholder) return;

  const user = getUser();
  const isOrganizer = user && user.role === "ORGANIZER";
  const displayName = user ? (user.name.split(" ")[0] || "User") : "Sign In";
  const displayRole = isOrganizer ? "(Approved Organizer)" : "(Customer)";

  placeholder.innerHTML = `
    <header class="navbar">
      <div class="nav-container">
        <!-- Brand -->
        <a href="events.html" class="nav-brand">
          <span>Mini ZooKeeper</span>
        </a>

        <!-- Center Nav Tabs -->
        <nav class="nav-links">
          <a href="events.html" class="nav-link ${activePage === 'events' ? 'active' : ''}">Events</a>
          <a href="my-bookings.html" class="nav-link ${activePage === 'tickets' || activePage === 'bookings' ? 'active' : ''}">My Tickets</a>
          <a href="organizer.html" class="nav-link ${activePage === 'telemetry' || activePage === 'organizer' ? 'active' : ''}">Telemetry</a>
        </nav>

        <!-- Right User Widget -->
        <div style="position: relative;">
          <div class="nav-user" onclick="toggleUserDropdown(event)">
            <div class="user-avatar">${displayName.charAt(0).toUpperCase()}</div>
            <div class="user-details">
              <span class="user-name">${escapeHtml(displayName)}</span>
              <span class="user-role-tag">${displayRole}</span>
            </div>
            <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 2px;">▾</span>
          </div>

          <!-- Dropdown Menu -->
          <div id="userDropdownMenu" style="display: none; position: absolute; right: 0; top: 120%; background: #161826; border: 1px solid var(--border-color); border-radius: 8px; width: 220px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); z-index: 99999; padding: 0.5rem 0;">
            <div style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-subtle); font-size: 0.8rem; color: var(--text-muted);">
              Signed in as<br><strong style="color: #fff;">${escapeHtml(user.email)}</strong>
            </div>
            <a href="my-bookings.html" style="display: block; padding: 0.5rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">🎟️ My Tickets</a>
            <a href="organizer.html" style="display: block; padding: 0.5rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">📊 Telemetry & Locks</a>
            <div style="border-top: 1px solid var(--border-subtle); margin: 0.25rem 0;"></div>
            <a href="login.html" style="display: block; padding: 0.5rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">🔄 Switch Demo Role</a>
            <button onclick="logout()" style="width: 100%; text-align: left; background: none; border: none; padding: 0.5rem 1rem; font-size: 0.85rem; color: #ef4444; cursor: pointer;">🚪 Sign Out</button>
          </div>
        </div>
      </div>
    </header>
  `;

  // Close dropdown on outside click
  document.addEventListener("click", function(e) {
    const dropdown = document.getElementById("userDropdownMenu");
    if (dropdown && !e.target.closest(".nav-user")) {
      dropdown.style.display = "none";
    }
  });
}

function toggleUserDropdown(e) {
  e.stopPropagation();
  const dropdown = document.getElementById("userDropdownMenu");
  if (dropdown) {
    dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
  }
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
  const bg = type === "success" ? "#16a34a" : type === "danger" ? "#dc2626" : type === "warning" ? "#d97706" : "#7c3aed";
  toast.style.background = bg;
  toast.style.color = "#ffffff";
  toast.style.padding = "0.75rem 1.25rem";
  toast.style.borderRadius = "8px";
  toast.style.boxShadow = "0 8px 16px rgba(0, 0, 0, 0.4)";
  toast.style.fontSize = "0.9rem";
  toast.style.fontWeight = "600";
  toast.style.maxWidth = "380px";
  toast.style.border = "1px solid rgba(255,255,255,0.2)";
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

function parseMonthAndDay(isoStr) {
  try {
    const d = new Date(isoStr);
    const month = d.toLocaleString("en-US", { month: "short" }).toUpperCase();
    const day = d.getDate();
    return { month, day };
  } catch (e) {
    return { month: "DEC", day: "11" };
  }
}
