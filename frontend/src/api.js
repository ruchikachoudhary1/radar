// Thin API client for the RADAR backend.
// In dev, Vite proxies /api to the FastAPI server (see vite.config.js).
// In production, set VITE_API_URL to the deployed backend origin.
const BASE = import.meta.env.VITE_API_URL || "";

async function handle(res) {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function analyzeResume({ file, role, jobDescription }) {
  const form = new FormData();
  form.append("file", file);
  form.append("role", role || "");
  form.append("job_description", jobDescription || "");
  return handle(await fetch(`${BASE}/api/analyze`, { method: "POST", body: form }));
}

export async function rewriteBullet(bullet, variants = 3) {
  return handle(
    await fetch(`${BASE}/api/rewrite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bullet, variants }),
    })
  );
}

// --- Interactive gap-fill interview ---------------------------------------

export async function getInterviewQuestions(analysisId) {
  return handle(
    await fetch(`${BASE}/api/interview/questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: analysisId }),
    })
  );
}

export async function buildResume(analysisId, answers) {
  return handle(
    await fetch(`${BASE}/api/interview/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: analysisId, answers }),
    })
  );
}

// --- Master profile --------------------------------------------------------

export async function getProfile() {
  return handle(await fetch(`${BASE}/api/profile`));
}

export async function saveProfile(profile) {
  return handle(
    await fetch(`${BASE}/api/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile }),
    })
  );
}

export async function profileFromAnalysis(analysisId) {
  return handle(
    await fetch(`${BASE}/api/profile/from-analysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: analysisId }),
    })
  );
}

// --- Job postings & application tracker -----------------------------------

export async function parseJob({ url, text }) {
  return handle(
    await fetch(`${BASE}/api/jobs/parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url || "", text: text || "" }),
    })
  );
}

export async function getApplications() {
  return handle(await fetch(`${BASE}/api/applications`));
}

export async function getApplication(id) {
  return handle(await fetch(`${BASE}/api/applications/${id}`));
}

export async function createApplication(payload) {
  return handle(
    await fetch(`${BASE}/api/applications`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function updateApplication(id, changes) {
  return handle(
    await fetch(`${BASE}/api/applications/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    })
  );
}

export async function retailorApplication(id) {
  return handle(
    await fetch(`${BASE}/api/applications/${id}/tailor`, { method: "POST" })
  );
}

export async function deleteApplication(id) {
  return handle(
    await fetch(`${BASE}/api/applications/${id}`, { method: "DELETE" })
  );
}

/** Ask the backend to render the resume and trigger a browser download. */
export async function downloadResume(text, format, filename = "resume") {
  const res = await fetch(`${BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
  return handle(await fetch(`${BASE}/api/history`));
}

export async function getHealth() {
  return handle(await fetch(`${BASE}/api/health`));
}
