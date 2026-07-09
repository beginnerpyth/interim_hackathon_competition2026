// ---------- Auth guard ----------
requireRole("organizer");
// requireRole already redirects to login.html if not a logged-in organizer.

// ---------- Load organizer's events ----------

async function loadOrganizerEvents() {
  const container = document.getElementById("organizerEventsList");
  container.innerHTML = `<p class="text-muted">読み込み中...</p>`;

  try {
    const res = await fetch(`${API_BASE_URL}/events`);
    const events = await res.json();

    if (events.length === 0) {
      container.innerHTML = `<p class="text-muted">まだ何も作成されていません。最初の項目を作成しましょう。</p>`;
      return;
    }

    const categoryLabels = {
      event: "イベント",
      club: "部活・サークル",
      seminar: "ゼミ",
      research: "研究",
      career: "就職・インターンシップ",
    };

    container.innerHTML = "";
    events.forEach((event) => {
      const col = document.createElement("div");
      col.className = "col-md-4";
      col.innerHTML = `
        <div class="card h-100 shadow-sm">
          <img src="${API_BASE_URL}/events/${event.id}/image"
               class="card-img-top event-image"
               alt="${escapeHtml(event.title)}"
               onerror="this.style.display='none'">
          <div class="card-body d-flex flex-column">
            <span class="stamp stamp-size mb-2" style="align-self:flex-start;">${categoryLabels[event.category] || event.category}</span>
            <h5 class="card-title">${escapeHtml(event.title)}</h5>
            <p class="card-text">${escapeHtml(event.description || "")}</p>
            <p class="text-muted small">チーム人数: ${event.team_size}人</p>
            <p class="text-muted small">👥 ${event.current_participants}${event.max_participants ? ` / ${event.max_participants}` : ""} 人参加${event.max_participants ? `（残り${Math.max(0, event.max_participants - event.current_participants)}人）` : "（定員なし）"}</p>
            <p class="text-muted small">${formatDeadline(event.deadline)}</p>
            <div class="mt-auto d-flex flex-column gap-2">
              <button class="btn btn-outline-primary btn-sm view-apps-btn" data-event-id="${event.id}">応募者を見る</button>
              <button class="btn btn-success btn-sm generate-btn" data-event-id="${event.id}">チームを編成する</button>
              <button class="btn btn-outline-secondary btn-sm view-teams-btn" data-event-id="${event.id}">チームを見る</button>
              <button class="btn btn-outline-secondary btn-sm view-comments-btn" data-event-id="${event.id}">💬 質問・コメント</button>
            </div>
          </div>
        </div>
      `;
      container.appendChild(col);
    });

    container.querySelectorAll(".view-apps-btn").forEach((btn) => {
      btn.addEventListener("click", () => viewApplications(btn.dataset.eventId));
    });
    container.querySelectorAll(".generate-btn").forEach((btn) => {
      btn.addEventListener("click", () => generateTeams(btn.dataset.eventId));
    });
    container.querySelectorAll(".view-teams-btn").forEach((btn) => {
      btn.addEventListener("click", () => viewTeams(btn.dataset.eventId));
    });
    container.querySelectorAll(".view-comments-btn").forEach((btn) => {
      btn.addEventListener("click", () => openOrgComments(btn.dataset.eventId));
    });
  } catch (err) {
    container.innerHTML = `<p class="text-danger">読み込めませんでした。</p>`;
    console.error(err);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatDeadline(deadline) {
  if (!deadline) return "締切なし（手動でチーム編成してください）";
  const d = new Date(deadline + "Z");
  const now = new Date();
  if (d <= now) {
    return `締切済み: ${d.toLocaleString("ja-JP")} — 約30秒以内に自動編成されます`;
  }
  return `締切: ${d.toLocaleString("ja-JP")}`;
}

// ---------- Create event ----------

document.getElementById("createEventForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const formData = new FormData();
  formData.append("title", document.getElementById("eventTitle").value);
  formData.append("description", document.getElementById("eventDescription").value);
  formData.append("team_size", document.getElementById("eventTeamSize").value);
  formData.append("category", document.getElementById("eventCategory").value);

  const maxParticipantsValue = document.getElementById("eventMaxParticipants").value;
  if (maxParticipantsValue) {
    formData.append("max_participants", maxParticipantsValue);
  }

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
      headers: authHeader(),
      body: formData,
    });
    if (!res.ok) throw new Error("作成に失敗しました。");

    bootstrap.Modal.getInstance(document.getElementById("createEventModal")).hide();
    document.getElementById("createEventForm").reset();
    loadOrganizerEvents();
  } catch (err) {
    alert("作成中に問題が発生しました。");
    console.error(err);
  }
});

// ---------- View applications ----------

async function viewApplications(eventId) {
  const tbody = document.getElementById("applicationsTableBody");
  tbody.innerHTML = `<tr><td colspan="4">読み込み中...</td></tr>`;
  new bootstrap.Modal(document.getElementById("applicationsModal")).show();

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/applications`, {
      headers: authHeader(),
    });
    if (!res.ok) throw new Error("読み込みに失敗しました。");
    const applications = await res.json();

    if (applications.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4">まだ応募がありません。</td></tr>`;
      return;
    }

    tbody.innerHTML = applications
      .map(
        (a) => `<tr><td>${escapeHtml(a.name)}</td><td>${escapeHtml(a.email)}</td><td>${escapeHtml(a.faculty || "—")}</td><td>${escapeHtml(a.grade || "—")}</td></tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4">読み込めませんでした。</td></tr>`;
    console.error(err);
  }
}

// ---------- Generate teams ----------

async function generateTeams(eventId) {
  if (!confirm("チームを編成しますか？既存のチームは上書きされます。")) {
    return;
  }

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/generate-teams`, {
      method: "POST",
      headers: authHeader(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "編成に失敗しました。");

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
  container.innerHTML = `<p class="text-muted">読み込み中...</p>`;
  new bootstrap.Modal(document.getElementById("orgTeamsModal")).show();

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/teams`);
    const teams = await res.json();

    if (teams.length === 0) {
      container.innerHTML = `<p class="text-muted">まだチームは編成されていません。</p>`;
      return;
    }

    const teamOptions = teams
      .map((t) => `<option value="${t.id}">チーム ${t.team_number}${t.group_label ? ` (${escapeHtml(t.group_label)})` : ""}</option>`)
      .join("");

    container.innerHTML = "";
    teams.forEach((team) => {
      const col = document.createElement("div");
      col.className = "col-md-6";
      const membersHtml = team.members
        .map((m) => `
          <li class="d-flex justify-content-between align-items-center gap-2 mb-2">
            <span>${escapeHtml(m.name)} — ${escapeHtml(m.email)}（${escapeHtml(m.faculty || "—")} / ${escapeHtml(m.grade || "—")}年）</span>
            <span class="d-flex gap-1">
              <select class="form-select form-select-sm move-team-select" style="width:auto;" data-app-id="${m.application_id}">
                ${teamOptions}
              </select>
              <button class="btn btn-sm btn-outline-primary move-member-btn" data-app-id="${m.application_id}" data-event-id="${eventId}">移動</button>
            </span>
          </li>
        `)
        .join("");
      col.innerHTML = `
        <div class="card p-3 team-card">
          <h6>チーム ${team.team_number}${team.group_label ? ` — ${escapeHtml(team.group_label)}` : ""}</h6>
          <ul class="mb-0 list-unstyled">${membersHtml}</ul>
        </div>
      `;
      container.appendChild(col);
    });

    // Pre-select each member's current team in their dropdown.
    teams.forEach((team) => {
      team.members.forEach((m) => {
        const select = container.querySelector(`.move-team-select[data-app-id="${m.application_id}"]`);
        if (select) select.value = team.id;
      });
    });

    container.querySelectorAll(".move-member-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const applicationId = btn.dataset.appId;
        const evtId = btn.dataset.eventId;
        const select = container.querySelector(`.move-team-select[data-app-id="${applicationId}"]`);
        const targetTeamId = select.value;

        try {
          const moveRes = await fetch(`${API_BASE_URL}/teams/${targetTeamId}/move-member/${applicationId}`, {
            method: "PUT",
            headers: authHeader(),
          });
          if (!moveRes.ok) {
            const err = await moveRes.json().catch(() => ({}));
            throw new Error(err.detail || "移動に失敗しました。");
          }
          viewTeams(evtId); // refresh the modal to reflect the new arrangement
        } catch (err) {
          alert(err.message);
          console.error(err);
        }
      });
    });
  } catch (err) {
    container.innerHTML = `<p class="text-danger">読み込めませんでした。</p>`;
    console.error(err);
  }
}

// ---------- AI 相談 (Gemini-powered chat, general only for organizers) ----------

let aiChatHistory = [];

function renderAiChatLog() {
  const log = document.getElementById("aiChatLog");
  if (aiChatHistory.length === 0) {
    log.innerHTML = `<p class="text-muted small">何でも質問してください。</p>`;
    return;
  }
  log.innerHTML = aiChatHistory
    .map((m) => `
      <div class="ai-msg ${m.role === "user" ? "ai-msg-user" : "ai-msg-bot"}">
        ${m.role === "bot" ? "🤖 " : ""}${escapeHtml(m.text)}
      </div>
    `)
    .join("");
  log.scrollTop = log.scrollHeight;
}

const aiChatFormEl = document.getElementById("aiChatForm");
if (aiChatFormEl) {
  aiChatFormEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("aiChatInput");
    const message = input.value.trim();
    if (!message) return;

    aiChatHistory.push({ role: "user", text: message });
    renderAiChatLog();
    input.value = "";
    input.disabled = true;

    try {
      const res = await fetch(`${API_BASE_URL}/ai/consult`, {
        method: "POST",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "AIとの通信に失敗しました。");
      }
      const data = await res.json();
      aiChatHistory.push({ role: "bot", text: data.reply });
    } catch (err) {
      aiChatHistory.push({ role: "bot", text: `⚠️ ${err.message}` });
    } finally {
      input.disabled = false;
      renderAiChatLog();
      input.focus();
    }
  });
}

const floatingAiBtnEl = document.getElementById("floatingAiBtn");
if (floatingAiBtnEl) {
  floatingAiBtnEl.addEventListener("click", () => {
    aiChatHistory = [];
    renderAiChatLog();
    new bootstrap.Modal(document.getElementById("aiConsultModal")).show();
  });
}

// ---------- Comments (Q&A) ----------

async function openOrgComments(eventId) {
  document.getElementById("orgCommentEventId").value = eventId;
  await loadOrgComments(eventId);
  new bootstrap.Modal(document.getElementById("orgCommentsModal")).show();
}

async function loadOrgComments(eventId) {
  const container = document.getElementById("orgCommentsList");
  container.innerHTML = `<p class="text-muted">読み込み中...</p>`;

  try {
    const res = await fetch(`${API_BASE_URL}/events/${eventId}/comments`);
    const comments = await res.json();

    if (comments.length === 0) {
      container.innerHTML = `<p class="text-muted">まだコメントはありません。</p>`;
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
    container.innerHTML = `<p class="text-danger">読み込めませんでした。</p>`;
    console.error(err);
  }
}

document.getElementById("orgCommentForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const eventId = document.getElementById("orgCommentEventId").value;
  const input = document.getElementById("orgCommentInput");
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
    loadOrgComments(eventId);
  } catch (err) {
    alert(err.message);
    console.error(err);
  }
});

// ---------- Logout ----------

document.getElementById("logoutBtn").addEventListener("click", logout);

// ---------- Init ----------

loadOrganizerEvents();