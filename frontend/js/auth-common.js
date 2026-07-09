// Shared across login.html, index.html, organizer.html.
// Stores { token, role } in localStorage under one key so we always know
// which kind of account (student/organizer) is currently logged in.

const AUTH_STORAGE_KEY = "musashino_auth";

function saveAuth(token, role) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ token, role }));
}

function getAuth() {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function clearAuth() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}

function authHeader() {
  const auth = getAuth();
  return auth ? { Authorization: `Bearer ${auth.token}` } : {};
}

// Call at the top of a page that requires a specific role.
// Redirects to login.html if not logged in or wrong role.
function requireRole(expectedRole) {
  const auth = getAuth();
  if (!auth || auth.role !== expectedRole) {
    window.location.href = "login.html";
    return null;
  }
  return auth;
}

function logout() {
  clearAuth();
  window.location.href = "login.html";
}