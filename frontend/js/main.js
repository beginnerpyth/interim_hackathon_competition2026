const eventsList = document.getElementById("events-list");
const searchInput = document.getElementById("searchInput");
const filterButtons = document.querySelectorAll(".filter-btn");

let allEvents = [];       // full list fetched from backend
let currentFilter = "all"; // "all" | "open" | "closed"

async function loadEvents() {
  eventsList.innerHTML = `<p class="text-muted">Loading events...</p>`;
  try {
    const res = await fetch(`${API_BASE_URL}/events`);
    const events = await res.json();
    allEvents = events;
    renderEvents();
  } catch (err) {
    eventsList.innerHTML = `<p class="text-danger">Could not load events. Is the backend running?</p>`;
    console.error(err);
  }
}

function isDeadlinePassed(event) {
  return event.deadline && new Date(event.deadline + "Z") <= new Date();
}

function renderEvents() {
  const searchTerm = (searchInput?.value || "").trim().toLowerCase();

  let filtered = allEvents.filter((event) => {
    const matchesSearch =
      !searchTerm ||
      event.title.toLowerCase().includes(searchTerm) ||
      (event.description || "").toLowerCase().includes(searchTerm);

    if (!matchesSearch) return false;

    if (currentFilter === "open") return !isDeadlinePassed(event);
    if (currentFilter === "closed") return isDeadlinePassed(event);
    return true; // "all"
  });

  if (allEvents.length === 0) {
    eventsList.innerHTML = `<p class="text-muted">No events yet. Check back soon!</p>`;
    return;
  }

  if (filtered.length === 0) {
    eventsList.innerHTML = `<p class="text-muted">No events match your search/filter.</p>`;
    return;
  }

  eventsList.innerHTML = "";
  filtered.forEach((event) => {
    const col = document.createElement("div");
    col.className = "col-md-4";
    const deadlinePassed = isDeadlinePassed(event);
    const deadlineText = event.deadline
      ? (deadlinePassed
          ? `<span class="text-danger">Applications closed</span>`
          : `Apply by: ${new Date(event.deadline + "Z").toLocaleString()}`)
      : "";
    col.innerHTML = `
      <div class="card h-100 shadow-sm">
        <img src="${API_BASE_URL}/events/${event.id}/image"
             class="card-img-top event-image"
             alt="${escapeHtml(event.title)}"
             onerror="this.style.display='none'">
        <div class="card-body d-flex flex-column">
          <h5 class="card-title">${escapeHtml(event.title)}</h5>
          <p class="card-text">${escapeHtml(event.description || "")}</p>
          <p class="text-muted small">Team size: ${event.team_size}</p>
          <p class="small">${deadlineText}</p>
          <div class="mt-auto d-flex gap-2">
            <button class="btn btn-primary btn-sm flex-fill apply-btn" ${deadlinePassed ? "disabled" : ""} data-event-id="${event.id}" data-event-title="${escapeHtml(event.title)}">${deadlinePassed ? "Closed" : "Apply"}</button>
            <button class="btn btn-outline-secondary btn-sm flex-fill teams-btn" data-event-id="${event.id}" data-event-title="${escapeHtml(event.title)}">View Teams</button>
          </div>
        </div>
      </div>
    `;
    eventsList.appendChild(col);
  });

  // Wire up buttons after inserting into the DOM (avoids inline onclick +
  // avoids breaking on apostrophes/quotes in event titles).
  eventsList.querySelectorAll(".apply-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      openApplyModal(btn.dataset.eventId, btn.dataset.eventTitle);
    });
  });
  eventsList.querySelectorAll(".teams-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      openTeamsModal(btn.dataset.eventId, btn.dataset.eventTitle);
    });
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- Search + Filter wiring ----------

if (searchInput) {
  searchInput.addEventListener("input", renderEvents);
}

filterButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    filterButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    renderEvents();
  });
});

// ---------- Apply ----------

function openApplyModal(eventId, title) {
  document.getElementById("applyEventId").value = eventId;
  document.getElementById("applyEventTitle").textContent = title;
  document.getElementById("applyForm").reset();
  document.getElementById("applyEventId").value = eventId; // reset() clears hidden input too, so set again
  new bootstrap.Modal(document.getElementById("applyModal")).show();
}

document.getElementById("applyForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const eventId = document.getElementById("applyEventId").value;
  const payload = {
    name: document.getElementById("applyName").value,
    email: document.getElementById("applyEmail").value,
    grade: document.getElementById("applyGrade").value,
  };

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to apply");
    }

    bootstrap.Modal.getInstance(document.getElementById("applyModal")).hide();
    alert("Application submitted! Check back later to see your team.");
  } catch (err) {
    alert(err.message || "Something went wrong submitting your application.");
    console.error(err);
  }
});

// ---------- View Teams ----------

async function openTeamsModal(eventId, title) {
  document.getElementById("teamsEventTitle").textContent = title;
  const container = document.getElementById("teamsContainer");
  container.innerHTML = `<p class="text-muted">Loading teams...</p>`;
  new bootstrap.Modal(document.getElementById("teamsModal")).show();

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/teams`);
    const teams = await res.json();

    if (teams.length === 0) {
      container.innerHTML = `<p class="text-muted">Teams haven't been generated yet. Check back later!</p>`;
      return;
    }

    container.innerHTML = "";
    teams.forEach((team) => {
      const col = document.createElement("div");
      col.className = "col-md-6";
      const membersHtml = team.members
        .map((m) => `<li>${escapeHtml(m.name)} (${escapeHtml(m.grade || "—")})</li>`)
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

loadEvents();