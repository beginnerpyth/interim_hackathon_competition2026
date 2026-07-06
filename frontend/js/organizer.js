// Token is kept in localStorage so the organizer stays logged in across page reloads.
function getToken() {
  return localStorage.getItem("organizer_token");
}
function setToken(token) {
  localStorage.setItem("organizer_token", token);
}
function clearToken() {
  localStorage.removeItem("organizer_token");
}

function showDashboard() {
  document.getElementById("authSection").style.display = "none";
  document.getElementById("dashboardSection").style.display = "block";
  loadOrganizerEvents();
}
function showAuth() {
  document.getElementById("authSection").style.display = "flex";
  document.getElementById("dashboardSection").style.display = "none";
}

// On page load, if we already have a token, go straight to dashboard.
if (getToken()) {
  showDashboard();
}

// ---------- Login ----------

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("loginUsername").value;
  const password = document.getElementById("loginPassword").value;

  const formBody = new URLSearchParams();
  formBody.append("username", username);
  formBody.append("password", password);

  try {
    const res = await fetch(`${API_BASE_URL}/organizer/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formBody,
    });
    if (!res.ok) throw new Error("Login failed");
    const data = await res.json();
    setToken(data.access_token);
    showDashboard();
  } catch (err) {
    alert("Login failed. Check your username and password.");
    console.error(err);
  }
});

// ---------- Register ----------

document.getElementById("registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = document.getElementById("registerUsername").value;
  const password = document.getElementById("registerPassword").value;

  try {
    const res = await fetch(`${API_BASE_URL}/organizer/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    setToken(data.access_token);
    showDashboard();
  } catch (err) {
    alert(err.message);
    console.error(err);
  }
});

// ---------- Logout ----------

document.getElementById("logoutBtn").addEventListener("click", () => {
  clearToken();
  showAuth();
});

// ---------- Load organizer's events ----------

async function loadOrganizerEvents() {
  const container = document.getElementById("organizerEventsList");
  container.innerHTML = `<p class="text-muted">Loading events...</p>`;

  try {
    const res = await fetch(`${API_BASE_URL}/events`);
    const events = await res.json();

    if (events.length === 0) {
      container.innerHTML = `<p class="text-muted">No events yet. Create your first one!</p>`;
      return;
    }

    container.innerHTML = "";
    events.forEach((event) => {
      const col = document.createElement("div");
      col.className = "col-md-4";
      col.innerHTML = `
        <div class="card h-100 shadow-sm">
          <img src="${API_BASE_URL}/events/${event.id}/image"
               class="card-img-top event-image"
               alt="${event.title}"
               onerror="this.style.display='none'">
          <div class="card-body d-flex flex-column">
            <h5 class="card-title">${escapeHtml(event.title)}</h5>
            <p class="card-text">${escapeHtml(event.description || "")}</p>
            <p class="text-muted small">Team size: ${event.team_size}</p>
            <p class="text-muted small">${formatDeadline(event.deadline)}</p>
            <div class="mt-auto d-flex flex-column gap-2">
              <button class="btn btn-outline-primary btn-sm" onclick="viewApplications(${event.id})">View Applications</button>
              <button class="btn btn-success btn-sm" onclick="generateTeams(${event.id})">Generate Teams</button>
              <button class="btn btn-outline-secondary btn-sm" onclick="viewTeams(${event.id})">View Teams</button>
            </div>
          </div>
        </div>
      `;
      container.appendChild(col);
    });
  } catch (err) {
    container.innerHTML = `<p class="text-danger">Could not load events.</p>`;
    console.error(err);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatDeadline(deadline) {
  if (!deadline) return "No deadline set (generate teams manually)";
  const d = new Date(deadline + "Z"); // treat as UTC, matching backend storage
  const now = new Date();
  if (d <= now) {
    return `Deadline passed: ${d.toLocaleString()} — teams auto-generate within ~30s`;
  }
  return `Deadline: ${d.toLocaleString()}`;
}

// ---------- Create event ----------

document.getElementById("createEventForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const formData = new FormData();
  formData.append("title", document.getElementById("eventTitle").value);
  formData.append("description", document.getElementById("eventDescription").value);
  formData.append("team_size", document.getElementById("eventTeamSize").value);

  const deadlineValue = document.getElementById("eventDeadline").value;
  if (deadlineValue) {
    formData.append("deadline", deadlineValue);
  }

  const photoFile = document.getElementById("eventPhoto").files[0];
  if (photoFile) {
    formData.append("file", photoFile);
  }

  try {
    const res = await fetch(`${API_BASE_URL}/events`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: formData,
    });
    if (!res.ok) throw new Error("Failed to create event");

    bootstrap.Modal.getInstance(document.getElementById("createEventModal")).hide();
    document.getElementById("createEventForm").reset();
    loadOrganizerEvents();
  } catch (err) {
    alert("Something went wrong creating the event.");
    console.error(err);
  }
});

// ---------- View applications ----------

async function viewApplications(eventId) {
  const tbody = document.getElementById("applicationsTableBody");
  tbody.innerHTML = `<tr><td colspan="3">Loading...</td></tr>`;
  new bootstrap.Modal(document.getElementById("applicationsModal")).show();

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/applications`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error("Failed to load applications");
    const applications = await res.json();

    if (applications.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3">No applications yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = applications
      .map(
        (a) => `<tr><td>${escapeHtml(a.name)}</td><td>${escapeHtml(a.email)}</td><td>${escapeHtml(a.grade || "—")}</td></tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="3">Could not load applications.</td></tr>`;
    console.error(err);
  }
}

// ---------- Generate teams ----------

async function generateTeams(eventId) {
  if (!confirm("Generate random teams now? This will replace any existing teams for this event.")) {
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/generate-teams`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to generate teams");

    alert(data.message);
    viewTeams(eventId);
  } catch (err) {
    alert(err.message);
    console.error(err);
  }
}

// ---------- View teams ----------

async function viewTeams(eventId) {
  const container = document.getElementById("orgTeamsContainer");
  container.innerHTML = `<p class="text-muted">Loading teams...</p>`;
  new bootstrap.Modal(document.getElementById("orgTeamsModal")).show();

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/teams`);
    const teams = await res.json();

    if (teams.length === 0) {
      container.innerHTML = `<p class="text-muted">No teams generated yet.</p>`;
      return;
    }

    container.innerHTML = "";
    teams.forEach((team) => {
      const col = document.createElement("div");
      col.className = "col-md-6";
      const membersHtml = team.members
        .map((m) => `<li>${escapeHtml(m.name)} — ${escapeHtml(m.email)} (${escapeHtml(m.grade || "—")})</li>`)
        .join("");
      col.innerHTML = `
        <div class="card p-3">
          <h6>Team ${team.team_number}</h6>
          <ul class="mb-0">${membersHtml}</ul>
        </div>
      `;
      container.appendChild(col);
    });
  } catch (err) {
    container.innerHTML = `<p class="text-danger">Could not load teams.</p>`;
    console.error(err);
  }
}
