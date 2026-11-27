/**
 * frontend/js/booking-common.js
 * Common Utilities, Authentication State, Navbar Rendering, and API Helpers.
 * Matches exact UI specification from user's reference mockup.
 */

const API_BASE = "";

// --------------------------------------------------------------------------
// Theme State Management (Dark Mode & Warm Orange/Beige Light Mode)
// --------------------------------------------------------------------------
function getTheme() {
  return localStorage.getItem("minizoo_theme") || "dark";
}

function initTheme() {
  const theme = getTheme();
  document.documentElement.setAttribute("data-theme", theme);
  return theme;
}

function toggleTheme() {
  const current = getTheme();
  const nextTheme = current === "light" ? "dark" : "light";
  localStorage.setItem("minizoo_theme", nextTheme);
  document.documentElement.setAttribute("data-theme", nextTheme);

  // Update button icon & text if navbar is rendered
  const iconSpan = document.getElementById("themeToggleIcon");
  const textSpan = document.getElementById("themeToggleText");
  if (iconSpan) iconSpan.innerText = nextTheme === "light" ? "🌙" : "☀️";
  if (textSpan) textSpan.innerText = nextTheme === "light" ? "Dark Theme" : "Orange & Beige";

  // Notify page specific listeners (e.g., canvas redraw on organizer page)
  window.dispatchEvent(new CustomEvent("themechanged", { detail: { theme: nextTheme } }));
}

// Apply theme as early as possible
initTheme();

// --------------------------------------------------------------------------
// Auth State Management
// --------------------------------------------------------------------------
function getUser() {
  try {
    const raw = localStorage.getItem("minizoo_user");
    if (raw) return JSON.parse(raw);
  } catch (e) {}

  // Null by default when visitor has not logged in yet
  return null;
}

function getToken() {
  return localStorage.getItem("minizoo_token") || null;
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

  const currentTheme = getTheme();
  const user = getUser();
  const isLoggedIn = !!user;
  const isOrganizer = user && user.role === "ORGANIZER";
  const displayName = user ? (user.name.split(" ")[0] || "User") : "";
  const displayRole = isOrganizer ? "(Approved Organizer)" : "(Customer)";
  const roleBadge = isOrganizer ? "ORGANIZER" : "CUSTOMER";

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
          ${isOrganizer ? `
            <a href="organizer.html" class="nav-link ${activePage === 'organizer' || activePage === 'host' || activePage === 'telemetry' ? 'active' : ''}">
              Host Dashboard
            </a>
          ` : ''}
        </nav>

        <!-- Right Controls: Theme Toggle & User Account -->
        <div class="nav-right-actions" style="display: flex; align-items: center; gap: 0.85rem;">
          <!-- Light/Dark Theme Switcher (Orange & Beige Contrast) -->
          <button id="themeToggleBtn" onclick="toggleTheme()" class="theme-toggle-btn" title="Toggle between Dark and Orange & Beige Light theme">
            <span id="themeToggleIcon">${currentTheme === 'light' ? '🌙' : '☀️'}</span>
            <span id="themeToggleText">${currentTheme === 'light' ? 'Dark Mode' : 'Orange & Beige'}</span>
          </button>

          ${isLoggedIn ? `
            <!-- Logged-in User Widget -->
            <div class="nav-user-container" style="position: relative; display: flex; align-items: center; gap: 0.75rem;">
              <div class="nav-user" onclick="toggleUserDropdown(event)" title="Account details">
                <div class="user-details" style="text-align: right; line-height: 1.2;">
                  <span class="user-role-sublabel" style="display: block; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.7px; color: ${isOrganizer ? 'var(--purple-primary)' : 'var(--text-muted)'}; text-transform: uppercase;">${roleBadge}</span>
                  <div style="display: flex; align-items: center; gap: 4px;">
                    <span class="user-name" style="font-size: 1rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(displayName)}</span>
                    <span class="user-role-tag" style="font-size: 0.8rem; color: var(--text-muted);">${displayRole}</span>
                  </div>
                </div>
                <div class="user-avatar" style="width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, var(--purple-primary), #4338ca); display: flex; align-items: center; justify-content: center; font-weight: 800; color: #fff; font-size: 0.95rem; margin-left: 4px;">
                  ${displayName.charAt(0).toUpperCase()}
                </div>
              </div>

              <!-- Direct Logout Button -->
              <button onclick="logout()" class="nav-logout-btn" title="Sign out" style="background: none; border: 1px solid var(--border-color); color: var(--text-muted); font-size: 0.85rem; font-weight: 600; padding: 0.4rem 0.8rem; border-radius: var(--radius-sm); cursor: pointer; transition: all 0.2s;">
                Logout
              </button>

              <!-- Dropdown Menu for role switching -->
              <div id="userDropdownMenu" style="display: none; position: absolute; right: 0; top: 120%; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; width: 250px; box-shadow: var(--shadow-md); z-index: 99999; padding: 0.5rem 0;">
                <div style="padding: 0.6rem 1rem; border-bottom: 1px solid var(--border-subtle); font-size: 0.8rem; color: var(--text-muted);">
                  Signed in as<br><strong style="color: var(--text-primary); font-size: 0.85rem;">${escapeHtml(user.email)}</strong>
                  <div style="margin-top: 4px;"><span class="badge ${isOrganizer ? 'badge-purple' : 'badge-muted'}" style="font-size: 0.72rem;">${roleBadge}</span></div>
                </div>
                ${isOrganizer ? `
                  <a href="organizer.html" style="display: flex; align-items: center; gap: 8px; padding: 0.6rem 1rem; font-size: 0.88rem; font-weight: 700; color: var(--purple-primary);">🎪 Host Dashboard</a>
                  <a href="analytics.html" style="display: flex; align-items: center; gap: 8px; padding: 0.55rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">📊 System Analytics</a>
                  <a href="activity.html" style="display: flex; align-items: center; gap: 8px; padding: 0.55rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">📋 Activity Audit Logs</a>
                  <div style="border-top: 1px solid var(--border-subtle); margin: 0.35rem 0;"></div>
                  <button onclick="switchToCustomer()" style="width: 100%; text-align: left; background: none; border: none; padding: 0.55rem 1rem; font-size: 0.85rem; color: var(--cyan-primary); font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 6px;">
                    👤 Switch to Customer Role
                  </button>
                ` : `
                  <a href="my-bookings.html" style="display: flex; align-items: center; gap: 8px; padding: 0.6rem 1rem; font-size: 0.88rem; color: var(--text-secondary);">🎟️ My Tickets</a>
                  <div style="border-top: 1px solid var(--border-subtle); margin: 0.35rem 0;"></div>
                  <button onclick="switchToOrganizer()" style="width: 100%; text-align: left; background: none; border: none; padding: 0.55rem 1rem; font-size: 0.85rem; color: var(--purple-primary); font-weight: 800; cursor: pointer; display: flex; align-items: center; gap: 6px;">
                    👑 Switch to Host Role
                  </button>
                `}
                <div style="border-top: 1px solid var(--border-subtle); margin: 0.35rem 0;"></div>
                <button onclick="logout()" style="width: 100%; text-align: left; background: none; border: none; padding: 0.55rem 1rem; font-size: 0.85rem; color: var(--red-primary); cursor: pointer; display: flex; align-items: center; gap: 6px;">🚪 Sign Out</button>
              </div>
            </div>
          ` : `
            <!-- Unauthenticated: Show Sign In Button -->
            <a href="login.html" class="btn btn-primary" style="padding: 0.45rem 1.15rem; font-size: 0.88rem; font-weight: 800; text-decoration: none; display: flex; align-items: center; gap: 6px;">
              <span>🔑</span> Sign In
            </a>
          `}
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

// --------------------------------------------------------------------------
// Quick Role Switchers for Demo & Viva Evaluation
// --------------------------------------------------------------------------
async function switchToOrganizer() {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "admin@zookeeper.com", name: "zookeeper" })
    });
    if (res.ok) {
      const data = await res.json();
      setUserSession(data.user, data.access_token);
      showToast("Signed in as Host / Organizer (zookeeper)!", "success");
      setTimeout(() => { window.location.href = "organizer.html"; }, 300);
      return;
    }
  } catch (e) {}
  setUserSession({ id: 1, name: "zookeeper", email: "admin@zookeeper.com", role: "ORGANIZER" }, "demo-organizer-token");
  window.location.href = "organizer.html";
}

async function switchToCustomer() {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "customer@example.com", name: "Alex Customer" })
    });
    if (res.ok) {
      const data = await res.json();
      setUserSession(data.user, data.access_token);
      showToast("Switched to Customer role!", "info");
      setTimeout(() => { window.location.href = "events.html"; }, 300);
      return;
    }
  } catch (e) {}
  setUserSession({ id: 2, name: "Alex Customer", email: "customer@example.com", role: "CUSTOMER" }, "demo-customer-token");
  window.location.href = "events.html";
}

