// ---------- Auth guard ----------
const currentAuth = requireRole("student");
// requireRole already redirects to login.html if not a logged-in student.

const eventsList = document.getElementById("events-list");
const searchInput = document.getElementById("searchInput");
const filterButtons = document.querySelectorAll(".filter-btn");
const categoryTabs = document.querySelectorAll(".category-tab");

let allEvents = [];
let currentFilter = "all";
let currentCategory = "event";

// ---------- Load student profile (for greeting + faculty/grade context) ----------

async function loadProfile() {
  try {
    const res = await fetch(`${API_BASE_URL}/student/me`, { headers: authHeader() });
    if (!res.ok) throw new Error("profile fetch failed");
    const student = await res.json();
    document.getElementById("studentNameLabel").textContent = `${student.name} さん`;
  } catch (err) {
    console.error(err);
    // If the token is invalid/expired, bounce to login.
    logout();
  }
}

// ---------- Load events (filtered by category server-side) ----------

async function loadEvents() {
  eventsList.innerHTML = `<p class="text-muted">読み込み中...</p>`;
  try {
    const res = await fetch(`${API_BASE_URL}/events?category=${currentCategory}`);
    const events = await res.json();
    allEvents = events;
    renderEvents();
  } catch (err) {
    eventsList.innerHTML = `<p class="text-danger">イベントを読み込めませんでした。</p>`;
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
    return true;
  });

  if (allEvents.length === 0) {
    eventsList.innerHTML = `
      <div class="col-12">
        <div class="board-empty">
          <div class="board-empty-title">まだ何も掲示されていません</div>
          <div>このカテゴリーの投稿はまだありません。</div>
        </div>
      </div>`;
    return;
  }

  if (filtered.length === 0) {
    eventsList.innerHTML = `
      <div class="col-12">
        <div class="board-empty">
          <div class="board-empty-title">一致する結果がありません</div>
          <div>検索条件やフィルターを変えてみてください。</div>
        </div>
      </div>`;
    return;
  }

  eventsList.innerHTML = "";
  filtered.forEach((event) => {
    const col = document.createElement("div");
    col.className = "col-md-4 pin-card-wrap";
    const deadlinePassed = isDeadlinePassed(event);
    const deadlineText = event.deadline
      ? (deadlinePassed
          ? `締切済み`
          : `締切: ${new Date(event.deadline + "Z").toLocaleDateString("ja-JP", { month: "short", day: "numeric" })}`)
      : "締切なし";
    const isFull = event.max_participants != null && event.current_participants >= event.max_participants;
    const participantsText = event.max_participants != null
      ? `👥 ${event.current_participants} / ${event.max_participants} 人`
      : `👥 ${event.current_participants} 人参加中`;
    const remainingText = event.max_participants != null
      ? `残り${Math.max(0, event.max_participants - event.current_participants)}人`
      : "";
    col.innerHTML = `
      <div class="card h-100 pin-card" data-category="${event.category}">
        <div class="pin-dot"></div>
        <img src="${API_BASE_URL}/events/${event.id}/image"
             class="card-img-top event-image"
             alt="${escapeHtml(event.title)}"
             onerror="this.style.display='none'">
        <div class="card-body d-flex flex-column">
          <h5 class="card-title">${escapeHtml(event.title)}</h5>
          <p class="card-text">${escapeHtml(event.description || "")}</p>
          <div class="stamp-row">
            <span class="stamp stamp-size">${event.team_size}人チーム</span>
            <span class="stamp ${deadlinePassed ? "stamp-closed" : "stamp-open"}">${deadlineText}</span>
          </div>
          <div class="stamp-row">
            <span class="stamp ${isFull ? "stamp-closed" : "stamp-size"}">${participantsText}${remainingText ? ` · ${remainingText}` : ""}</span>
          </div>
          <div class="mt-auto d-flex gap-2">
            <button class="btn btn-primary btn-sm flex-fill apply-btn" ${(deadlinePassed || isFull) ? "disabled" : ""} data-event-id="${event.id}" data-event-title="${escapeHtml(event.title)}">${deadlinePassed ? "締切" : (isFull ? "定員に達しました" : "応募する")}</button>
            <button class="btn btn-outline-secondary btn-sm flex-fill teams-btn" data-event-id="${event.id}" data-event-title="${escapeHtml(event.title)}">チームを見る</button>
          </div>
          <button class="btn btn-outline-secondary btn-sm w-100 mt-2 comments-btn" data-event-id="${event.id}" data-event-title="${escapeHtml(event.title)}">💬 質問・コメント</button>
        </div>
      </div>
    `;
    eventsList.appendChild(col);
  });

  eventsList.querySelectorAll(".apply-btn").forEach((btn) => {
    btn.addEventListener("click", () => openApplyChoice(btn.dataset.eventId, btn.dataset.eventTitle, btn));
  });
  eventsList.querySelectorAll(".teams-btn").forEach((btn) => {
    btn.addEventListener("click", () => openTeamsModal(btn.dataset.eventId, btn.dataset.eventTitle));
  });
  eventsList.querySelectorAll(".comments-btn").forEach((btn) => {
    btn.addEventListener("click", () => openCommentsModal(btn.dataset.eventId, btn.dataset.eventTitle));
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- Apply: choice step (individual vs team) ----------

let pendingApplyButton = null; // so we can update its label/disabled state after either flow finishes

function openApplyChoice(eventId, title, buttonEl) {
  pendingApplyButton = buttonEl;
  document.getElementById("choiceEventTitle").textContent = title;

  const event = allEvents.find((e) => String(e.id) === String(eventId));

  const choiceModalEl = document.getElementById("applyChoiceModal");
  const choiceModal = new bootstrap.Modal(choiceModalEl);

  const individualBtn = document.getElementById("choiceIndividualBtn");
  const teamBtn = document.getElementById("choiceTeamBtn");

  // Replace with fresh clones each time to avoid stacking duplicate listeners.
  const newIndividualBtn = individualBtn.cloneNode(true);
  individualBtn.parentNode.replaceChild(newIndividualBtn, individualBtn);
  const newTeamBtn = teamBtn.cloneNode(true);
  teamBtn.parentNode.replaceChild(newTeamBtn, teamBtn);

  newIndividualBtn.addEventListener("click", () => {
    choiceModal.hide();
    applyIndividually(eventId, title);
  });

  newTeamBtn.addEventListener("click", () => {
    choiceModal.hide();
    openTeamApplyModal(eventId, title, event?.team_size || 1);
  });

  choiceModal.show();
}

// ---------- Apply: individual ----------

async function applyIndividually(eventId, title) {
  if (!confirm(`「${title}」に個人で応募しますか？`)) return;

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/apply`, {
      method: "POST",
      headers: authHeader(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "応募に失敗しました。");
    }

    alert("応募が完了しました！チームは締切後に自動編成されます。");
    if (pendingApplyButton) {
      pendingApplyButton.disabled = true;
      pendingApplyButton.textContent = "応募済み";
    }
  } catch (err) {
    alert(err.message);
    console.error(err);
  }
}

// ---------- Apply: as a team ----------

function openTeamApplyModal(eventId, title, teamSize) {
  document.getElementById("teamApplyEventId").value = eventId;
  document.getElementById("teamApplyEventTitle").textContent = title;
  document.getElementById("teamApplySizeLabel").textContent = teamSize;

  const teammateCount = Math.max(0, teamSize - 1);
  const inputsContainer = document.getElementById("teammateInputs");
  inputsContainer.innerHTML = "";
  for (let i = 0; i < teammateCount; i++) {
    const div = document.createElement("div");
    div.className = "mb-2";
    div.innerHTML = `
      <label class="form-label small">チームメイト ${i + 1} のユーザー名</label>
      <input type="text" class="form-control teammate-username-input" required placeholder="username">
    `;
    inputsContainer.appendChild(div);
  }

  if (teammateCount === 0) {
    inputsContainer.innerHTML = `<p class="text-muted">このイベントは1人チームです。個人応募を選んでください。</p>`;
  }

  new bootstrap.Modal(document.getElementById("teamApplyModal")).show();
}

const teamApplyFormEl = document.getElementById("teamApplyForm");
if (teamApplyFormEl) {
  teamApplyFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const eventId = document.getElementById("teamApplyEventId").value;

  const usernames = Array.from(document.querySelectorAll(".teammate-username-input"))
    .map((input) => input.value.trim())
    .filter(Boolean);

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/apply-team`, {
      method: "POST",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: JSON.stringify({ teammate_usernames: usernames }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "チーム応募に失敗しました。");
    }

    bootstrap.Modal.getInstance(document.getElementById("teamApplyModal")).hide();
    alert("チームでの応募が完了しました！");
    if (pendingApplyButton) {
      pendingApplyButton.disabled = true;
      pendingApplyButton.textContent = "応募済み";
    }
  } catch (err) {
    alert(err.message);
    console.error(err);
  }
  });
}

// ---------- Category tabs ----------

categoryTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    categoryTabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentCategory = tab.dataset.category;
    loadEvents();
  });
});

// ---------- Search + Filter ----------

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

// ---------- View Teams ----------

async function openTeamsModal(eventId, title) {
  document.getElementById("teamsEventTitle").textContent = title;
  const container = document.getElementById("teamsContainer");
  container.innerHTML = `<p class="text-muted">読み込み中...</p>`;
  new bootstrap.Modal(document.getElementById("teamsModal")).show();

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/teams`);
    const teams = await res.json();

    if (teams.length === 0) {
      container.innerHTML = `<p class="text-muted">まだチームは編成されていません。締切後をお待ちください。</p>`;
      return;
    }

    container.innerHTML = "";
    teams.forEach((team) => {
      const col = document.createElement("div");
      col.className = "col-md-6";
      const membersHtml = team.members
        .map((m) => `<li>${escapeHtml(m.name)}（${escapeHtml(m.faculty || "—")} / ${escapeHtml(m.grade || "—")}年）</li>`)
        .join("");
      col.innerHTML = `
        <div class="card p-3 team-card">
          <h6>チーム ${team.team_number}${team.group_label ? ` — ${escapeHtml(team.group_label)}` : ""}</h6>
          <ul class="mb-0">${membersHtml}</ul>
        </div>
      `;
      container.appendChild(col);
    });
  } catch (err) {
    container.innerHTML = `<p class="text-danger">チームを読み込めませんでした。</p>`;
    console.error(err);
  }
}

// ---------- Logout ----------

document.getElementById("logoutBtn").addEventListener("click", logout);

// ---------- Comments (Q&A per event) ----------

async function openCommentsModal(eventId, title) {
  document.getElementById("commentsEventTitle").textContent = title;
  document.getElementById("commentEventId").value = eventId;
  await loadComments(eventId);
  new bootstrap.Modal(document.getElementById("commentsModal")).show();
}

async function loadComments(eventId) {
  const container = document.getElementById("commentsList");
  container.innerHTML = `<p class="text-muted">読み込み中...</p>`;

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/comments`);
    const comments = await res.json();

    if (comments.length === 0) {
      container.innerHTML = `<p class="text-muted">まだコメントはありません。最初の質問をしてみましょう。</p>`;
      return;
    }

    container.innerHTML = comments
      .map((c) => {
        const isOrganizer = c.author_type === "organizer";
        const when = new Date(c.created_at + "Z").toLocaleString("ja-JP");
        return `
          <div class="comment-item ${isOrganizer ? "comment-organizer" : ""}">
            <div class="comment-meta">
              <strong>${escapeHtml(c.author_name)}</strong>
              <span class="text-muted small">${when}</span>
            </div>
            <div class="comment-content">${escapeHtml(c.content)}</div>
          </div>
        `;
      })
      .join("");
  } catch (err) {
    container.innerHTML = `<p class="text-danger">コメントを読み込めませんでした。</p>`;
    console.error(err);
  }
}

const commentFormEl = document.getElementById("commentForm");
if (commentFormEl) {
  commentFormEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    const eventId = document.getElementById("commentEventId").value;
    const input = document.getElementById("commentInput");
    const content = input.value.trim();
    if (!content) return;

    try {
      const res = await fetch(`${API_BASE_URL}/events/${eventId}/comments`, {
        method: "POST",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "送信に失敗しました。");
      }
      input.value = "";
      loadComments(eventId);
    } catch (err) {
      alert(err.message);
      console.error(err);
    }
  });
}

// ---------- Init ----------

loadProfile();
loadEvents();