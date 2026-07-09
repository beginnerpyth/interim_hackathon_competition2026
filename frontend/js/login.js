let selectedRole = "student";

const tabs = document.querySelectorAll(".login-tab");
tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    selectedRole = tab.dataset.role;
    document.getElementById("loginError").style.display = "none";
  });
});

// If already logged in, skip straight to the right page.
const existing = getAuth();
if (existing) {
  window.location.href = existing.role === "organizer" ? "organizer.html" : "index.html";
}

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorBox = document.getElementById("loginError");
  errorBox.style.display = "none";

  const username = document.getElementById("loginUsername").value;
  const password = document.getElementById("loginPassword").value;

  const endpoint = selectedRole === "organizer" ? "/organizer/login" : "/student/login";

  const formBody = new URLSearchParams();
  formBody.append("username", username);
  formBody.append("password", password);

  try {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formBody,
    });

    if (!res.ok) {
      throw new Error("ユーザー名またはパスワードが正しくありません。");
    }

    const data = await res.json();
    saveAuth(data.access_token, data.role);
    window.location.href = data.role === "organizer" ? "organizer.html" : "index.html";
  } catch (err) {
    errorBox.textContent = err.message || "ログインに失敗しました。";
    errorBox.style.display = "block";
    console.error(err);
  }
});