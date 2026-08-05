// Thin API client for the RADAR backend.
// In dev, Vite proxies /api to the FastAPI server (see vite.config.js).
// In production, set VITE_API_URL to the deployed backend origin.
const BASE = import.meta.env.VITE_API_URL || "";
const TOKEN_KEY = "radar_token";

// --- Session ---------------------------------------------------------------
// The JWT lives in localStorage so a refresh keeps you signed in. Every
// authenticated request attaches it as a bearer token.

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch (_) {
    return "";
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch (_) {
    /* private browsing — the session just won't survive a refresh */
  }
}

/** Listeners notified when the server rejects our token, so the UI can sign out. */
const expiryListeners = new Set();

export function onSessionExpired(fn) {
  expiryListeners.add(fn);
  return () => expiryListeners.delete(fn);
}

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function handle(res) {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (_) {
      /* ignore */
    }
    if (res.status === 401) {
      setToken("");
      expiryListeners.forEach((fn) => fn(detail));
    }
    throw new Error(detail);
  }
  return res.json();
}

function jsonRequest(method, body) {
  return {
    method,
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  };
}

// --- Accounts --------------------------------------------------------------

export async function signup({ email, password, name }) {
  return handle(
    await fetch(`${BASE}/api/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name: name || "" }),
    })
  );
}

export async function login({ email, password }) {
  return handle(
    await fetch(`${BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
  );
}

export async function getMe() {
  return handle(await fetch(`${BASE}/api/auth/me`, { headers: authHeaders() }));
}

export async function deleteAccount() {
  return handle(
    await fetch(`${BASE}/api/auth/me`, { method: "DELETE", headers: authHeaders() })
  );
}

export async function analyzeResume({ file, role, jobDescription }) {
  const form = new FormData();
  form.append("file", file);
  form.append("role", role || "");
  form.append("job_description", jobDescription || "");
  return handle(await fetch(`${BASE}/api/analyze`, { method: "POST", headers: authHeaders(), body: form }));
}

export async function rewriteBullet(bullet, variants = 3) {
  return handle(
    await fetch(`${BASE}/api/rewrite`, {
      ...jsonRequest("POST", { bullet, variants }),
    })
  );
}

// --- Interactive gap-fill interview ---------------------------------------

export async function getInterviewQuestions(analysisId) {
  return handle(
    await fetch(`${BASE}/api/interview/questions`, {
      ...jsonRequest("POST", { analysis_id: analysisId }),
    })
  );
}

export async function buildResume(analysisId, answers) {
  return handle(
    await fetch(`${BASE}/api/interview/build`, {
      ...jsonRequest("POST", { analysis_id: analysisId, answers }),
    })
  );
}

// --- Master profile --------------------------------------------------------

export async function getProfile() {
  return handle(await fetch(`${BASE}/api/profile`, { headers: authHeaders() }));
}

export async function saveProfile(profile) {
  return handle(
    await fetch(`${BASE}/api/profile`, {
      ...jsonRequest("PUT", { profile }),
    })
  );
}

export async function profileFromAnalysis(analysisId) {
  return handle(
    await fetch(`${BASE}/api/profile/from-analysis`, {
      ...jsonRequest("POST", { analysis_id: analysisId }),
    })
  );
}

// --- Job postings & application tracker -----------------------------------

export async function parseJob({ url, text }) {
  return handle(
    await fetch(`${BASE}/api/jobs/parse`, {
      ...jsonRequest("POST", { url: url || "", text: text || "" }),
    })
  );
}

export async function getApplications() {
  return handle(await fetch(`${BASE}/api/applications`, { headers: authHeaders() }));
}

export async function getApplication(id) {
  return handle(await fetch(`${BASE}/api/applications/${id}`, { headers: authHeaders() }));
}

export async function createApplication(payload) {
  return handle(
    await fetch(`${BASE}/api/applications`, {
      ...jsonRequest("POST", payload),
    })
  );
}

export async function updateApplication(id, changes) {
  return handle(
    await fetch(`${BASE}/api/applications/${id}`, {
      ...jsonRequest("PATCH", changes),
    })
  );
}

export async function retailorApplication(id) {
  return handle(
    await fetch(`${BASE}/api/applications/${id}/tailor`, { method: "POST", headers: authHeaders() })
  );
}

export async function writeCoverLetter(id) {
  return handle(
    await fetch(`${BASE}/api/applications/${id}/cover-letter`, {
      method: "POST",
      headers: authHeaders(),
    })
  );
}

export async function deleteApplication(id) {
  return handle(
    await fetch(`${BASE}/api/applications/${id}`, { method: "DELETE", headers: authHeaders() })
  );
}

/** Ask the backend to render the resume and trigger a browser download. */
export async function downloadResume(text, format, filename = "resume") {
  const res = await fetch(`${BASE}/api/export`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ text, format, filename }),
  });
  if (!res.ok) {
    let detail = `Export failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename.replace(/\.[^.]+$/, "")}.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function getHistory() {
  return handle(await fetch(`${BASE}/api/history`, { headers: authHeaders() }));
}

// --- Job feed --------------------------------------------------------------

export async function getPreferences() {
  return handle(await fetch(`${BASE}/api/preferences`, { headers: authHeaders() }));
}

export async function savePreferences(preferences) {
  return handle(
    await fetch(`${BASE}/api/preferences`, { ...jsonRequest("PUT", preferences) })
  );
}

export async function checkBoard({ source, token }) {
  return handle(
    await fetch(`${BASE}/api/feed/check`, { ...jsonRequest("POST", { source, token }) })
  );
}

export async function getFeed() {
  return handle(await fetch(`${BASE}/api/feed`, { headers: authHeaders() }));
}

export async function getSummary() {
  return handle(await fetch(`${BASE}/api/summary`, { headers: authHeaders() }));
}

export async function getHealth() {
  return handle(await fetch(`${BASE}/api/health`));
}
